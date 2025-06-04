# chatbot/services/db_manager.py
import os
import psycopg2
from psycopg2 import extras # Para usar RealDictCursor si lo deseas
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuración de la conexión a la base de datos
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    """Establece y devuelve una conexión a la base de datos."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        logger.error(f"Error al conectar a la base de datos: {e}")
        return None

def initialize_db():
    """Crea las tablas necesarias si no existen."""
    conn = get_db_connection()
    if not conn:
        logger.error("No se pudo conectar a la DB para inicializarla.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id SERIAL PRIMARY KEY,
                    whatsapp_user_id VARCHAR(255) UNIQUE NOT NULL,
                    status VARCHAR(50) DEFAULT 'active', -- 'active', 'closed'
                    control_mode VARCHAR(50) DEFAULT 'bot', -- 'bot', 'agent'
                    assigned_agent_id INTEGER NULL, -- ID del agente asignado
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    chat_id INTEGER NOT NULL REFERENCES chats(id),
                    sender_type VARCHAR(10) NOT NULL, -- 'user', 'bot', 'agent'
                    message_type VARCHAR(50) NOT NULL, -- 'text', 'interactive_button', 'interactive_list', etc.
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    chat_id INTEGER NOT NULL REFERENCES chats(id),
                    whatsapp_user_id VARCHAR(255) NOT NULL,
                    product_name VARCHAR(255) NOT NULL,
                    customer_name VARCHAR(255),
                    delivery_address TEXT,
                    payment_method VARCHAR(100),
                    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'confirmed', 'shipped', 'delivered', 'cancelled'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Tabla de agentes (para futura autenticación y asignación)
                CREATE TABLE IF NOT EXISTS agents (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            logger.info("Tablas de la base de datos verificadas/creadas exitosamente.")
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

def get_or_create_chat(whatsapp_user_id):
    """Obtiene un chat existente o crea uno nuevo para un usuario de WhatsApp."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, control_mode FROM chats WHERE whatsapp_user_id = %s", (whatsapp_user_id,))
            chat = cur.fetchone()
            if chat:
                # Actualizar el timestamp si el chat ya existe
                cur.execute("UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = %s", (chat[0],))
                conn.commit()
                return chat[0]
            else:
                cur.execute(
                    "INSERT INTO chats (whatsapp_user_id) VALUES (%s) RETURNING id",
                    (whatsapp_user_id,)
                )
                new_chat_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Nuevo chat creado para usuario {whatsapp_user_id} con ID {new_chat_id}")
                return new_chat_id
    except Exception as e:
        logger.error(f"Error al obtener o crear chat para {whatsapp_user_id}: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def save_message(chat_id, sender_type, message_type, content):
    """Guarda un mensaje en la base de datos."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (chat_id, sender_type, message_type, content) VALUES (%s, %s, %s, %s)",
                (chat_id, sender_type, message_type, content)
            )
            conn.commit()
            logger.info(f"Mensaje guardado (Chat ID: {chat_id}, Tipo: {sender_type})")
            return True
    except Exception as e:
        logger.error(f"Error al guardar mensaje: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def save_order(chat_id, whatsapp_user_id, order_details):
    """Guarda los detalles de un pedido en la base de datos."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orders (chat_id, whatsapp_user_id, product_name, customer_name, delivery_address, payment_method) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    chat_id,
                    whatsapp_user_id,
                    order_details.get("product"),
                    order_details.get("name"),
                    order_details.get("address"),
                    order_details.get("payment_method"),
                )
            )
            conn.commit()
            logger.info(f"Pedido guardado para el chat ID: {chat_id}")
            return True
    except Exception as e:
        logger.error(f"Error al guardar pedido: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_chat_control_mode(chat_id):
    """Obtiene el modo de control actual (bot/agente) para un chat."""
    conn = get_db_connection()
    if not conn:
        return 'bot' # Default a bot si hay error de DB
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT control_mode FROM chats WHERE id = %s", (chat_id,))
            result = cur.fetchone()
            if result:
                return result[0]
            return 'bot' # Default a bot si no se encuentra
    except Exception as e:
        logger.error(f"Error al obtener el modo de control para el chat {chat_id}: {e}")
        return 'bot'
    finally:
        if conn:
            conn.close()

def set_chat_control(whatsapp_user_id, control_mode, agent_id=None):
    """Establece el modo de control (bot/agente) para un chat."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chats SET control_mode = %s, assigned_agent_id = %s, updated_at = CURRENT_TIMESTAMP WHERE whatsapp_user_id = %s",
                (control_mode, agent_id, whatsapp_user_id)
            )
            conn.commit()
            logger.info(f"Modo de control de chat para {whatsapp_user_id} cambiado a '{control_mode}' por agente {agent_id if agent_id else 'N/A'}")
            return True
    except Exception as e:
        logger.error(f"Error al establecer el control del chat para {whatsapp_user_id}: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_chats(status=None, control_mode=None):
    """Obtiene una lista de chats con filtros opcionales."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            query = "SELECT id, whatsapp_user_id, status, control_mode, assigned_agent_id, created_at, updated_at FROM chats WHERE 1=1"
            params = []
            if status:
                query += " AND status = %s"
                params.append(status)
            if control_mode:
                query += " AND control_mode = %s"
                params.append(control_mode)
            query += " ORDER BY updated_at DESC"
            
            cur.execute(query, tuple(params))
            chats = cur.fetchall()
            return chats
    except Exception as e:
        logger.error(f"Error al obtener chats: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_messages_for_chat(chat_id):
    """Obtiene todos los mensajes para un chat específico."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, chat_id, sender_type, message_type, content, timestamp FROM messages WHERE chat_id = %s ORDER BY timestamp ASC",
                (chat_id,)
            )
            messages = cur.fetchall()
            return messages
    except Exception as e:
        logger.error(f"Error al obtener mensajes para el chat {chat_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_orders(status=None):
    """Obtiene una lista de pedidos con filtros opcionales."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            query = "SELECT id, chat_id, whatsapp_user_id, product_name, customer_name, delivery_address, payment_method, status, created_at, updated_at FROM orders WHERE 1=1"
            params = []
            if status:
                query += " AND status = %s"
                params.append(status)
            query += " ORDER BY created_at DESC"
            
            cur.execute(query, tuple(params))
            orders = cur.fetchall()
            return orders
    except Exception as e:
        logger.error(f"Error al obtener pedidos: {e}")
        return []
    finally:
        if conn:
            conn.close()