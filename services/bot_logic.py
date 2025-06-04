# chatbot/services/bot_logic.py
import json
import re
import logging
from services import db_manager # Importar db_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# user_states se mantiene en memoria para el flujo conversacional.
# El estado de control (bot/agente) se maneja en la DB.
user_states = {} 

def get_bot_response_from_engine(user_message, user_id="default_user"):
    response_text = "Lo siento, no entendí tu solicitud. 🤔 Escribe 'hola' para ver las opciones."
    message_type = "text" 
    buttons = None
    list_options = None
    
    processed_message = user_message.lower().strip()
    current_state = user_states.get(user_id)

    # Lógica de pedido en curso
    if current_state and current_state.get("action") == "collecting_order_data":
        step = current_state["step"]
        order_details = current_state["order_details"]
        message_type = "text" 

        if step == "awaiting_name":
            order_details["product"] = "Kit Óscar Camarra"
            order_details["name"] = user_message
            response_text = f"¡Gracias, {user_message}! 😊 Ahora, por favor, indícame tu dirección completa para el envío. 🚚"
            current_state["step"] = "awaiting_address"
            buttons = None

        elif step == "awaiting_address":
            order_details["address"] = user_message
            response_text = (
                "Perfecto. 👍 El Kit Óscar Camarra tiene un costo de [PRECIO DEL KIT]. "
                "Puedes pagar contraentrega o por transferencia bancaria. ¿Cuál prefieres?"
            )
            current_state["step"] = "awaiting_payment_method"
            message_type = "buttons" 
            buttons = [ 
                {"type": "reply", "reply": {"id": "payment_contraentrega", "title": "Contraentrega 💳"}},
                {"type": "reply", "reply": {"id": "payment_transferencia", "title": "Transferencia 🏦"}}
            ]

        elif step == "awaiting_payment_method":
            if processed_message == "payment_contraentrega":
                order_details["payment_method"] = "Contraentrega"
            elif processed_message == "payment_transferencia":
                order_details["payment_method"] = "Transferencia Bancaria"
            else: 
                order_details["payment_method"] = user_message # Si el usuario escribe algo diferente

            # Aquí se guarda el pedido en la base de datos
            chat_id = db_manager.get_or_create_chat(user_id) # Asegurarse de tener el chat_id
            if chat_id:
                db_manager.save_order(chat_id, user_id, order_details) # Guardar el pedido
            else:
                logger.error(f"No se pudo obtener/crear chat_id para {user_id} al guardar el pedido.")
            
            response_text = (
                "¡Tu pedido del Kit Óscar Camarra ha sido registrado! 🎉\n\n"
                "Resumen de tu pedido:\n"
                f"👤 Nombre: {order_details.get('name')}\n"
                f"🏠 Dirección: {order_details.get('address')}\n"
                f"💳 Método de Pago: {order_details.get('payment_method')}\n"
                f"🛍️ Producto: {order_details.get('product')}\n\n"
                "Nos pondremos en contacto contigo en breve para confirmar los últimos detalles y coordinar la entrega. ¡Gracias por tu compra!"
            )
            
            logger.info(f"--- NUEVO PEDIDO REGISTRADO (Usuario: {user_id}) ---")
            logger.info(f"  Nombre: {order_details.get('name')}")
            logger.info(f"  Dirección: {order_details.get('address')}")
            logger.info(f"  Método de Pago: {order_details.get('payment_method')}")
            logger.info(f"  Producto: {order_details.get('product')}")
            logger.info(f"  Teléfono (WhatsApp ID): {user_id}")
            logger.info("-------------------------------------------------")

            del user_states[user_id] # Finaliza el estado del pedido
            message_type = "buttons"
            buttons = [
                {"type": "reply", "reply": {"id": "menu_principal", "title": "Menú Principal 🏠"}}
            ]
        
        # Guardar el estado actualizado si la conversación continúa
        if user_id in user_states: 
             user_states[user_id] = current_state
    
    # Lógica de menú principal y opciones
    else:
        if processed_message in ["hola", "menú", "menu", "inicio", "menu_principal", "menu_principal_parte1"]:
            message_type = "list" 
            response_text = ( 
                "¡Hola! 👋 Bienvenido al Chat Oficial de Carlos Piña Viste y Vive.\n"
                "Tu estilo comienza aquí. ✨\n\n"
                "Soy tu asistente virtual y estoy para ayudarte. 😊 Selecciona una opción:"
            )
            list_options = {
                "button_title": "Ver Opciones 👇", 
                "header_text": "MENÚ PRINCIPAL", 
                "sections": [
                    {
                        "rows": [
                            {"id": "opt_kit_oscar", "title": "👕 Kit Óscar Camarra"}, 
                            {"id": "opt_catalogo", "title": "📚 Ver Catálogo"},
                            {"id": "opt_personalizar", "title": "🎨 Personalizar Producto"}, 
                            {"id": "opt_consultar_pedido", "title": "🚚 Consultar Pedido"},
                            {"id": "opt_hablar_asesor", "title": "💬 Hablar con Asesor"}
                        ]
                    }
                ]
            }
            buttons = None 

        elif processed_message == "opt_kit_oscar":
            message_type = "buttons"
            response_text = (
                "🌟 ¡Descubre el exclusivo Kit de Lanzamiento de Óscar Camarra! 🌟\n"
                "Un conjunto diseñado para destacar tu estilo con clase y autenticidad.\n\n"
                "Incluye:\n"
                "👕 Una camisa edición especial\n"
                "🧢 Una gorra bordada\n"
                "🎁 Empaque de lujo\n\n"
                "🚚 La entrega se realiza en un día hábil (sujeto a disponibilidad).\n"
                "💳 Puedes pagar contraentrega o por transferencia.\n\n"
                "¿Te gustaría hacer tu pedido ahora?"
            )
            buttons = [
                {"type": "reply", "reply": {"id": "pedir_kit_oscar_si", "title": "Sí, pedir ahora 👍"}},
                {"type": "reply", "reply": {"id": "menu_principal", "title": "Menú Principal 🏠"}}
            ]

        elif processed_message == "pedir_kit_oscar_si":
            user_states[user_id] = {
                "action": "collecting_order_data",
                "step": "awaiting_name",
                "order_details": {} 
            }
            message_type = "text"
            response_text = "¡Perfecto! Para tomar tu pedido del Kit Óscar Camarra, necesitaré algunos datos. 😊\n\nPrimero, ¿cuál es tu nombre completo?"
            buttons = None

        elif processed_message == "opt_catalogo":
            message_type = "buttons" 
            response_text = (
                "🛍️ Nuestro Catálogo de Prendas 🧥\n\n"
                "Descubre nuestra amplia variedad de camisas, camisetas, gorras, trajes y más. "
                "Para ver el catálogo completo y actualizado, por favor visita el siguiente enlace:\n\n"
                "🔗 [Aquí va tu enlace al catálogo en WhatsApp o web]\n\n" 
                "Si algo te interesa, puedes indicarme el nombre del artículo o su código. 😉"
            )
            buttons = [
                {"type": "reply", "reply": {"id": "menu_principal", "title": "Menú Principal 🏠"}}
            ]

        # MODIFICACIÓN: Estas opciones ahora transfieren el control a un agente
        elif processed_message == "opt_personalizar":
            db_manager.set_chat_control(user_id, 'agent') # Cambia el control a agente
            message_type = "text"
            response_text = (
                "🎨 ¿Quieres una prenda única? ¡Genial!\n"
                "Para personalizar un producto, te conectaré con uno de nuestros asesores expertos. "
                "Ellos te guiarán en el proceso. 🧑‍🎨\n\n"
                "Por favor, espera un momento."
            )
            buttons = None 

        elif processed_message == "opt_consultar_pedido":
            db_manager.set_chat_control(user_id, 'agent') # Cambia el control a agente
            message_type = "text"
            response_text = (
                "🚚 Para consultar el estado de tu pedido, un asesor te atenderá en breve.\n\n"
                "Ten en cuenta que, dependiendo de la hora de tu solicitud y la disponibilidad, "
                "la entrega puede ser en horas o al día siguiente hábil.\n\n"
                "Un asesor se comunicará contigo por este chat. ⏳"
            )
            buttons = None 

        elif processed_message == "opt_hablar_asesor":
            db_manager.set_chat_control(user_id, 'agent') # Cambia el control a agente
            message_type = "text" 
            response_text = (
                "💬 ¡Claro! Estoy conectándote con un asesor para que pueda atender tu solicitud personalmente.\n\n"
                "Por favor, espera unos momentos. Agradecemos tu paciencia. 🙏"
            )
            buttons = None 
        
    return {
        "message_type": message_type,
        "text": response_text,
        "buttons": buttons,
        "list_options": list_options
    }

def get_parsed_bot_response(user_message, user_id="default_user"):
    logger.info(f"Procesando mensaje/botón ID: '{user_message}' para usuario '{user_id}'")
    
    # Primero, verificar si el chat está en modo agente
    chat_id = db_manager.get_or_create_chat(user_id) # Asegura que el chat_id exista
    if chat_id:
        control_mode = db_manager.get_chat_control_mode(chat_id)
        if control_mode == 'agent':
            logger.info(f"Chat para {user_id} está en modo agente. El bot no responderá.")
            # Si está en modo agente, el bot no debe generar una respuesta automática.
            # En su lugar, el mensaje debe ser visible para el agente en el panel.
            return {
                "message_type": "none", # Un tipo que indica que el bot no debe responder
                "text": "",
                "buttons": None,
                "list_options": None
            }

    # Si no está en modo agente, proceder con la lógica del bot
    structured_response = get_bot_response_from_engine(user_message, user_id)
    logger.info(f"Respuesta estructurada generada: {structured_response}")
    return structured_response