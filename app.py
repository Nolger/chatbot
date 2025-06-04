# chatbot/app.py
from flask import Flask, request, jsonify
import os
import logging
import json

from services import bot_logic
from services import whatsapp
from services import db_manager # Importar el nuevo módulo de DB

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")

# Inicializar la base de datos al inicio de la aplicación
with app.app_context():
    db_manager.initialize_db()

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
            if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
                logger.warning("Webhook GET: Fallo de verificación del token.")
                return "Verification token mismatch", 403
            logger.info("Webhook GET: Verificación exitosa.")
            return request.args["hub.challenge"], 200
        logger.warning("Webhook GET: Solicitud inválida.")
        return "Invalid request", 400

    elif request.method == "POST":
        data = request.get_json()
        logger.info(f"Webhook POST: Datos recibidos: {json.dumps(data, indent=2)}")

        if data and data.get("object") == "whatsapp_business_account":
            try:
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        if change.get("field") == "messages":
                            value = change.get("value", {})
                            
                            for message_data in value.get("messages", []):
                                message_type_from_whatsapp = message_data.get("type") 
                                from_phone_number = message_data["from"]
                                
                                user_message_content = "" 
                                msg_db_type = "text" # Tipo para guardar en la DB

                                if message_type_from_whatsapp == "text":
                                    user_message_content = message_data["text"]["body"]
                                    msg_db_type = "text"
                                elif message_type_from_whatsapp == "interactive":
                                    interactive_response = message_data.get("interactive", {})
                                    interactive_type = interactive_response.get("type")
                                    
                                    if interactive_type == "button_reply":
                                        user_message_content = interactive_response["button_reply"]["id"]
                                        msg_db_type = "interactive_button"
                                        logger.info(f"Respuesta de botón recibida: ID='{user_message_content}'")
                                    elif interactive_type == "list_reply": 
                                        user_message_content = interactive_response["list_reply"]["id"]
                                        msg_db_type = "interactive_list"
                                        logger.info(f"Respuesta de lista recibida: ID='{user_message_content}'")
                                    else:
                                        logger.info(f"Tipo de respuesta interactiva '{interactive_type}' no manejada explícitamente y será ignorada.")
                                        continue # Ignorar otros tipos interactivos por ahora
                                else:
                                    logger.info(f"Mensaje de tipo '{message_type_from_whatsapp}' ignorado.")
                                    continue # Ignorar otros tipos de mensajes de WhatsApp (audio, imagen, etc.)

                                if not user_message_content: 
                                    logger.warning("No se pudo extraer contenido del mensaje del usuario.")
                                    continue

                                logger.info(f"Procesando entrada: '{user_message_content}' de {from_phone_number}")

                                # 1. Obtener o crear el chat en la base de datos
                                chat_id = db_manager.get_or_create_chat(from_phone_number)
                                if not chat_id:
                                    logger.error(f"No se pudo obtener/crear chat_id para {from_phone_number}. No se procesará el mensaje.")
                                    continue

                                # 2. Guardar el mensaje del usuario en la base de datos
                                db_manager.save_message(chat_id, 'user', msg_db_type, user_message_content)

                                # 3. Obtener la respuesta del bot (o indicar que está en modo agente)
                                bot_response_data = bot_logic.get_parsed_bot_response(user_message_content, user_id=from_phone_number)
                                
                                response_text_body = bot_response_data.get("text")
                                response_type = bot_response_data.get("message_type", "text") 
                                response_buttons = bot_response_data.get("buttons")
                                response_list_options = bot_response_data.get("list_options")

                                # Solo envía un mensaje si el bot_logic genera uno (no si está en modo agente)
                                if response_type != "none" and response_text_body: # 'none' es la nueva señal para no responder
                                    if response_type == "list" and response_list_options:
                                        whatsapp.send_interactive_list_message(
                                            recipient_phone_number=from_phone_number,
                                            body_text=response_text_body,
                                            list_button_title=response_list_options.get("button_title", "Opciones"),
                                            sections=response_list_options.get("sections", []),
                                            header_text=response_list_options.get("header_text"),
                                            footer_text=response_list_options.get("footer_text")
                                        )
                                        db_manager.save_message(chat_id, 'bot', 'interactive_list', response_text_body)
                                    elif response_type == "buttons" and response_buttons:
                                        whatsapp.send_interactive_buttons_message(
                                            recipient_phone_number=from_phone_number,
                                            body_text=response_text_body,
                                            buttons=response_buttons
                                        )
                                        db_manager.save_message(chat_id, 'bot', 'interactive_button', response_text_body)
                                    else: 
                                        whatsapp.send_text_message(from_phone_number, response_text_body)
                                        db_manager.save_message(chat_id, 'bot', 'text', response_text_body)
                                else:
                                    logger.info(f"Bot no generó respuesta para {from_phone_number} (modo agente o respuesta vacía).")
            
            except Exception as e:
                logger.error(f"Error procesando el webhook: {e}", exc_info=True)

            return "OK", 200
        else:
            logger.warning("Webhook POST: Datos no son de una cuenta de WhatsApp Business o formato incorrecto.")
            return "Not a WhatsApp Business Account event or bad format", 400

    logger.warning(f"Método {request.method} no soportado.")
    return "Method not supported", 405

# --- API para el Frontend de Administración ---

# Endpoint para obtener todos los chats
@app.route("/api/chats", methods=["GET"])
def get_all_chats():
    # En un entorno real, aquí se implementaría autenticación y autorización
    chats = db_manager.get_chats()
    return jsonify(chats), 200

# Endpoint para obtener mensajes de un chat específico
@app.route("/api/chats/<int:chat_id>/messages", methods=["GET"])
def get_chat_messages(chat_id):
    # En un entorno real, aquí se implementaría autenticación y autorización
    messages = db_manager.get_messages_for_chat(chat_id)
    return jsonify(messages), 200

# Endpoint para que un agente envíe un mensaje a un usuario
@app.route("/api/chats/<int:chat_id>/send_message", methods=["POST"])
def send_agent_message(chat_id):
    # En un entorno real, aquí se implementaría autenticación y autorización
    data = request.get_json()
    message_text = data.get("message")
    sender_whatsapp_id = data.get("whatsapp_user_id") # Necesario para enviar por WhatsApp

    if not message_text or not sender_whatsapp_id:
        return jsonify({"error": "Mensaje y ID de WhatsApp del remitente son requeridos."}), 400

    # Enviar el mensaje a WhatsApp
    response_whatsapp = whatsapp.send_text_message(sender_whatsapp_id, message_text)
    
    if response_whatsapp:
        # Guardar el mensaje del agente en la base de datos
        db_manager.save_message(chat_id, 'agent', 'text', message_text)
        return jsonify({"status": "success", "message": "Mensaje enviado y registrado."}), 200
    else:
        return jsonify({"error": "Fallo al enviar mensaje a WhatsApp."}), 500

# Endpoint para cambiar el modo de control del chat (bot/agente)
@app.route("/api/chats/<int:chat_id>/set_control", methods=["POST"])
def set_chat_control_api(chat_id):
    # En un entorno real, aquí se implementaría autenticación y autorización
    data = request.get_json()
    new_control_mode = data.get("control_mode") # 'bot' o 'agent'
    agent_id = data.get("agent_id") # Opcional: ID del agente que toma control

    if new_control_mode not in ['bot', 'agent']:
        return jsonify({"error": "Modo de control inválido. Debe ser 'bot' o 'agent'."}), 400

    # Obtener el whatsapp_user_id del chat_id
    conn = db_manager.get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión a la base de datos."}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT whatsapp_user_id FROM chats WHERE id = %s", (chat_id,))
            result = cur.fetchone()
            if not result:
                return jsonify({"error": "Chat no encontrado."}), 404
            whatsapp_user_id = result[0]
    except Exception as e:
        logger.error(f"Error al buscar whatsapp_user_id para chat_id {chat_id}: {e}")
        return jsonify({"error": "Error interno del servidor."}), 500
    finally:
        if conn:
            conn.close()

    if db_manager.set_chat_control(whatsapp_user_id, new_control_mode, agent_id):
        return jsonify({"status": "success", "message": f"Modo de control del chat cambiado a '{new_control_mode}'."}), 200
    else:
        return jsonify({"error": "Fallo al actualizar el modo de control del chat."}), 500

# Endpoint para obtener todos los pedidos
@app.route("/api/orders", methods=["GET"])
def get_all_orders():
    # En un entorno real, aquí se implementaría autenticación y autorización
    orders = db_manager.get_orders()
    return jsonify(orders), 200

# Endpoint para actualizar el estado de un pedido (ej. 'confirmed', 'shipped')
@app.route("/api/orders/<int:order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    # En un entorno real, aquí se implementaría autenticación y autorización
    data = request.get_json()
    new_status = data.get("status")

    if not new_status:
        return jsonify({"error": "Nuevo estado es requerido."}), 400

    conn = db_manager.get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión a la base de datos."}), 500
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id",
                (new_status, order_id)
            )
            updated_id = cur.fetchone()
            conn.commit()
            if updated_id:
                return jsonify({"status": "success", "message": f"Estado del pedido {order_id} actualizado a '{new_status}'."}), 200
            else:
                return jsonify({"error": "Pedido no encontrado."}), 404
    except Exception as e:
        logger.error(f"Error al actualizar el estado del pedido {order_id}: {e}")
        conn.rollback()
        return jsonify({"error": "Error interno del servidor."}), 500
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 5000))
    logger.info(f"Iniciando servidor Flask en el puerto {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True) # debug=True para desarrollo