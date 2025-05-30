# services/whatsapp.py
import requests
import json
import os
import logging

logger = logging.getLogger(__name__)

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v19.0") # O la versión que uses

def send_whatsapp_message_payload(recipient_phone_number, message_payload):
    """
    Envía un payload de mensaje genérico a través de la API de WhatsApp Cloud.
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WHATSAPP_TOKEN o WHATSAPP_PHONE_NUMBER_ID no están configurados.")
        return None

    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        logger.debug(f"Enviando a {recipient_phone_number} payload: {json.dumps(message_payload, indent=2)}")
        response = requests.post(url, headers=headers, data=json.dumps(message_payload))
        response.raise_for_status() 
        logger.info(f"Mensaje enviado a {recipient_phone_number}. Respuesta: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error enviando mensaje a {recipient_phone_number}: {e}")
        if e.response is not None:
            logger.error(f"Detalles del error: {e.response.text}")
        return None

def send_text_message(recipient_phone_number, text):
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone_number,
        "type": "text",
        "text": {"body": text},
    }
    return send_whatsapp_message_payload(recipient_phone_number, payload)

def send_interactive_buttons_message(recipient_phone_number, body_text, buttons, header_text=None, footer_text=None):
    if not buttons or len(buttons) == 0:
        logger.warning("Se intentó enviar un mensaje de botones sin botones. Enviando solo texto.")
        return send_text_message(recipient_phone_number, body_text)
        
    if len(buttons) > 3:
        logger.warning("WhatsApp solo soporta hasta 3 botones de respuesta. Se usarán los primeros 3.")
        buttons = buttons[:3]

    interactive_payload_content = {
        "type": "button",
        "body": {"text": body_text},
        "action": {"buttons": buttons},
    }

    if header_text:
        interactive_payload_content["header"] = {"type": "text", "text": header_text}
    if footer_text:
        interactive_payload_content["footer"] = {"text": footer_text}

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone_number,
        "type": "interactive",
        "interactive": interactive_payload_content,
    }
    return send_whatsapp_message_payload(recipient_phone_number, payload)

def send_interactive_list_message(recipient_phone_number, body_text, list_button_title, sections, header_text=None, footer_text=None):
    """
    Envía un mensaje de lista interactiva.
    'sections' es una lista de diccionarios de sección, cada uno con "title" (opcional) y "rows".
    Cada "row" es un dict con "id", "title" (max 24 chars), y "description" (opcional, max 72 chars).
    Máximo 10 filas en total en todas las secciones.
    """
    if not sections or not any(sec.get("rows") for sec in sections):
        logger.error("Se intentó enviar un mensaje de lista sin secciones o filas. No se enviará.")
        return None

    interactive_payload_content = {
        "type": "list",
        "body": {"text": body_text},
        "action": {
            "button": list_button_title, # Texto del botón que despliega la lista
            "sections": sections
        }
    }

    if header_text:
        interactive_payload_content["header"] = {"type": "text", "text": header_text}
    if footer_text:
        interactive_payload_content["footer"] = {"text": footer_text}
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone_number,
        "type": "interactive",
        "interactive": interactive_payload_content
    }
    return send_whatsapp_message_payload(recipient_phone_number, payload)


if __name__ == "__main__":
    test_recipient_phone = os.getenv("TEST_WHATSAPP_RECIPIENT") 
    if not test_recipient_phone:
        print("Configura TEST_WHATSAPP_RECIPIENT para probar el envío.")
    else:
        print(f"Intentando enviar mensajes de prueba a: {test_recipient_phone}")
        
        # send_text_message(test_recipient_phone, "Hola desde mi bot de Python!")

        # example_buttons = [
        #     {"type": "reply", "reply": {"id": "btn_1", "title": "Opción 1"}},
        #     {"type": "reply", "reply": {"id": "btn_2", "title": "Opción 2"}},
        # ]
        # send_interactive_buttons_message(
        #     test_recipient_phone,
        #     "Este es un mensaje con botones.",
        #     example_buttons,
        #     header_text="Encabezado de Botones"
        # )

        example_list_sections = [
            {
                "title": "Elige una Opción",
                "rows": [
                    {"id": "item_1", "title": "Opción de Lista 1", "description": "Descripción opcional 1"},
                    {"id": "item_2", "title": "Opción de Lista 2", "description": "Descripción opcional 2"},
                    {"id": "item_3", "title": "Otra Opción Más Larga", "description": "Esta es una descripción más detallada de la opción tres."}
                ]
            }
        ]
        # send_interactive_list_message(
        #     test_recipient_phone,
        #     body_text="Este es un mensaje con una lista de opciones. Por favor, elige una:",
        #     list_button_title="Ver Opciones",
        #     sections=example_list_sections,
        #     header_text="Encabezado de Lista",
        #     footer_text="Pie de página de Lista"
        # )
        print("Descomenta las llamadas de ejemplo para probar.")