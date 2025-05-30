# app.py
from flask import Flask, request, jsonify
import os
import logging
import json # <--- ¡AQUÍ ESTÁ LA CORRECCIÓN!

from services import bot_logic
from services import whatsapp

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")

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
        # Ahora json.dumps funcionará porque el módulo json está importado
        logger.info(f"Webhook POST: Datos recibidos: {json.dumps(data, indent=2)}")

        if data and data.get("object") == "whatsapp_business_account":
            try:
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        if change.get("field") == "messages":
                            value = change.get("value", {})
                            
                            for message_data in value.get("messages", []):
                                message_type_from_whatsapp = message_data.get("type") # Renombrado para evitar confusión con response_type
                                from_phone_number = message_data["from"]
                                
                                user_message_text = "" 

                                if message_type_from_whatsapp == "text":
                                    user_message_text = message_data["text"]["body"]
                                elif message_type_from_whatsapp == "interactive":
                                    interactive_response = message_data.get("interactive", {})
                                    interactive_type = interactive_response.get("type")
                                    
                                    if interactive_type == "button_reply":
                                        user_message_text = interactive_response["button_reply"]["id"]
                                        logger.info(f"Respuesta de botón recibida: ID='{user_message_text}'")
                                    elif interactive_type == "list_reply": 
                                        user_message_text = interactive_response["list_reply"]["id"]
                                        logger.info(f"Respuesta de lista recibida: ID='{user_message_text}'")
                                    else:
                                        logger.info(f"Tipo de respuesta interactiva '{interactive_type}' no manejada explícitamente.")
                                        continue
                                else:
                                    logger.info(f"Mensaje de tipo '{message_type_from_whatsapp}' ignorado.")
                                    continue

                                if not user_message_text: 
                                    logger.warning("No se pudo extraer texto o ID del mensaje del usuario.")
                                    continue

                                logger.info(f"Procesando entrada: '{user_message_text}' de {from_phone_number}")

                                bot_response_data = bot_logic.get_parsed_bot_response(user_message_text, user_id=from_phone_number)
                                
                                response_text_body = bot_response_data.get("text")
                                # 'response_type' es el tipo de mensaje que NUESTRO BOT quiere enviar
                                response_type = bot_response_data.get("message_type", "text") 
                                response_buttons = bot_response_data.get("buttons")
                                response_list_options = bot_response_data.get("list_options")

                                if response_text_body:
                                    if response_type == "list" and response_list_options:
                                        whatsapp.send_interactive_list_message(
                                            recipient_phone_number=from_phone_number,
                                            body_text=response_text_body,
                                            list_button_title=response_list_options.get("button_title", "Opciones"),
                                            sections=response_list_options.get("sections", []),
                                            header_text=response_list_options.get("header_text"),
                                            footer_text=response_list_options.get("footer_text")
                                        )
                                    elif response_type == "buttons" and response_buttons:
                                        whatsapp.send_interactive_buttons_message(
                                            recipient_phone_number=from_phone_number,
                                            body_text=response_text_body,
                                            buttons=response_buttons
                                        )
                                    else: 
                                        whatsapp.send_text_message(from_phone_number, response_text_body)
                                else:
                                    logger.warning("La respuesta del bot no contenía texto.")
            
            except Exception as e:
                logger.error(f"Error procesando el webhook: {e}", exc_info=True)

            return "OK", 200
        else:
            logger.warning("Webhook POST: Datos no son de una cuenta de WhatsApp Business o formato incorrecto.")
            return "Not a WhatsApp Business Account event or bad format", 400

    logger.warning(f"Método {request.method} no soportado.")
    return "Method not supported", 405

if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 5000)) # Cambiado para que coincida con tu log si es necesario, o usa 8080
    logger.info(f"Iniciando servidor Flask en el puerto {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False) # debug=False es mejor para pruebas con webhooks, True para desarrollo local puro