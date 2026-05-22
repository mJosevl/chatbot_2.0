import os
import spacy
from flask import Flask, request, jsonify
from flask_cors import CORS
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

engine = create_engine('sqlite:///chatbot_db.sqlite')
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

class Mensaje(Base):
    __tablename__ = 'mensajes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    opcion = Column(String(50))
    respuesta = Column(String(500))
    fecha = Column(DateTime, default=datetime.utcnow)

class HistorialInteracciones(Base):
    __tablename__ = 'historial_interacciones'
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario = Column(String(50))
    mensaje = Column(String(255))
    respuesta = Column(String(500))
    fecha = Column(DateTime, default=datetime.utcnow)

class SolicitudAgente(Base):
    __tablename__ = 'solicitudes_agente'
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario = Column(String(50))
    nombre = Column(String(100))
    fecha = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Cargar modelo spaCy de procesamiento lingüístico
try:
    nlp = spacy.load("es_core_news_sm")
except:
    nlp = None

estado_usuarios = {}

MENU = (
    "Hola, bienvenido a Austral Road SPA. ¿En qué puedo ayudarte?\n\n"
    "1. Horario de atención 🕐\n"
    "2. Ubicación 📍\n"
    "3. Catálogo de Servicios y Precios 🛠️\n"
    "4. Información de Contacto 📞\n"
    "5. Hablar con un agente humano 👤"
)

SUBMENU = (
    "\n\n¿En qué más puedo ayudarte?\n"
    "1. Horario · 2. Ubicación · 3. Servicios · 4. Contacto · 5. Agente"
)

# Estructura expandida con los 9 subservicios de la empresa (Austral Road SPA)
SERVICIOS_COMPLETOS = (
    "🛠️ *CATÁLOGO OFICIAL DE SERVICIOS (Austral Road SPA)*\n\n"
    "👉 *1. REVISIONES TÉCNICAS A DOMICILIO*\n"
    "• [1.1] Revisión Básica Particular: $45.000\n"
    "• [1.2] Revisión Completa Particular: $75.000\n"
    "• [1.3] Inspección Vehículos de Carga: $95.000\n\n"
    "👉 *2. ASESORÍA DE SINIESTROS*\n"
    "• [2.1] Peritaje Técnico Daños Menores: $65.000\n"
    "• [2.2] Peritaje Técnico Daños Mayores: $120.000\n"
    "• [2.3] Informe Técnico Oficial Aseguradora: $100.000\n\n"
    "👉 *3. MECÁNICA PARA EMPRESAS Y FLOTAS*\n"
    "• [3.1] Mantención Preventiva Flotas: $55.000\n"
    "• [3.2] Diagnóstico Completo con Escáner OBD: $70.000\n"
    "• [3.3] Mecánica Correctiva Avanzada: $110.000\n\n"
    "📍 *Cobertura:* Desde Frutillar hasta la Carretera Austral.\n"
    "Escribe el código numérico del servicio para iniciar su agendamiento automático."
)

# Palabras clave y entidades léxicas por intención (Base del NLP)
INTENCIONES = {
    'saludo': ['hola', 'buenas', 'buen día', 'buenos días', 'buenas tardes', 'inicio', 'menu', 'ayuda', 'start', 'comenzar'],
    'horario': ['horario', 'hora', 'cuando', 'atienden', 'abren', 'cierran', 'disponible', 'abierto', 'días', 'atención'],
    'ubicacion': ['donde', 'ubicación', 'dirección', 'lugar', 'como llegar', 'están', 'queda', 'localización', 'mapa', 'puerto montt', 'rucahue'],
    'servicios': ['servicio', 'que hacen', 'que ofrecen', 'catálogo', 'menú de servicios', 'opciones', 'prestaciones'],
    'contacto': ['contacto', 'teléfono', 'correo', 'email', 'llamar', 'comunicar', 'número', 'mail', 'whatsapp', 'fono'],
    'agente': ['agente', 'persona', 'humano', 'hablar con alguien', 'ejecutivo', 'asesor', 'ayuda personalizada', 'asistencia', 'operador'],
    'precio': ['precio', 'costo', 'cuanto', 'valor', 'cobran', 'tarifa', 'cuánto cuesta', 'presupuesto', 'cotización', 'valores', 'dinero'],
    'revision_1': ['1.1', 'revisión básica', 'básica particular'],
    'revision_2': ['1.2', 'revisión completa', 'completa particular'],
    'revision_3': ['1.3', 'vehículos de carga', 'inspección carga', 'camión'],
    'siniestro_1': ['2.1', 'peritaje menor', 'daños menores'],
    'siniestro_2': ['2.2', 'peritaje mayor', 'daños mayores'],
    'siniestro_3': ['2.3', 'informe técnico', 'aseguradora', 'informe oficial', 'seguro'],
    'mecanica_1': ['3.1', 'mantención preventiva', 'flotas', 'mantención empresa'],
    'mecanica_2': ['3.2', 'diagnóstico escáner', 'escáner obd', 'escaner'],
    'mecanica_3': ['3.3', 'mecánica correctiva', 'correctiva avanzada', 'reparación avanzada'],
}

def detectar_intencion(texto):
    texto_lower = texto.lower().strip()

    # Mapeo directo de opciones del menú principal
    if texto_lower == '1': return 'horario'
    if texto_lower == '2': return 'ubicacion'
    if texto_lower == '3' or texto_lower == 'servicios': return 'servicios'
    if texto_lower == '4': return 'contacto'
    if texto_lower == '5': return 'agente'
    
    # Mapeo directo de subservicios numéricos del catálogo extendido
    if texto_lower in ['1.1']: return 'revision_1'
    if texto_lower in ['1.2']: return 'revision_2'
    if texto_lower in ['1.3']: return 'revision_3'
    if texto_lower in ['2.1']: return 'siniestro_1'
    if texto_lower in ['2.2']: return 'siniestro_2'
    if texto_lower in ['2.3']: return 'siniestro_3'
    if texto_lower in ['3.1']: return 'mecanica_1'
    if texto_lower in ['3.2']: return 'mecanica_2'
    if texto_lower in ['3.3']: return 'mecanica_3'

    # Lógica NLP adaptativa con spaCy
    if nlp:
        doc = nlp(texto_lower)
        lemmas = [token.lemma_ for token in doc]
        texto_analizado = ' '.join(lemmas)
    else:
        texto_analizado = texto_lower

    # Clasificador basado en matching semántico por palabras clave
    for intencion, palabras in INTENCIONES.items():
        for palabra in palabras:
            if palabra in texto_analizado or palabra in texto_lower:
                return intencion

    return 'desconocido'

def generar_respuesta(intencion, usuario=None):
    if intencion == 'saludo':
        return MENU, 'saludo'
    elif intencion == 'horario':
        return 'Nuestro horario de atención oficial es de lunes a viernes de 9:00 a 18:00 horas. Sábados y domingos cerrados.' + SUBMENU, 'horario'
    elif intencion == 'ubicacion':
        return 'Nuestras instalaciones centrales y base operativa se ubican en Villa Rucahue 600, Puerto Montt, Región de Los Lagos.' + SUBMENU, 'ubicacion'
    elif intencion == 'servicios' or intencion == 'precio':
        return SERVICIOS_COMPLETOS, 'servicios'
    elif intencion == 'contacto':
        return 'Puedes contactarnos directamente vía Teléfono corporativo al: +56 9 5808 4231 o escribirnos al Correo: comercialaustralroad@gmail.com' + SUBMENU, 'contacto'
    elif intencion == 'agente':
        if usuario:
            estado_usuarios[usuario] = 'esperando_nombre'
        # IMPORTANTE: Aquí NO concatenamos el SUBMENU para no arruinar el flujo conversacional.
        return 'Perfecto. Para asignarte un ejecutivo de atención personalizada, ¿cuál es tu nombre completo?', 'agente'
    
    # RESPUESTAS DETALLADAS DE AGENDAMIENTO PARA LOS 9 SUBSERVICIOS
    elif intencion == 'revision_1':
        return "📋 *Solicitud iniciada:* REVISIÓN BÁSICA PARTICULAR ($45.000).\nIncluye inspección visual de frenos, niveles de fluidos, luces y neumáticos a domicilio. Nuestro sistema procesará tu agenda con la base de datos." + SUBMENU, 'revision_1'
    elif intencion == 'revision_2':
        return "📋 *Solicitud iniciada:* REVISIÓN COMPLETA PARTICULAR ($75.000).\nInspección a fondo del tren delantero, suspensión, motorización y reporte completo pre-compra o preventivo a domicilio." + SUBMENU, 'revision_2'
    elif intencion == 'revision_3':
        return "📋 *Solicitud iniciada:* INSPECCIÓN VEHÍCULOS DE CARGA ($95.000).\nDiseñado para camiones y furgones comerciales en ruta. Verificación de sistemas neumáticos y de torque operacional." + SUBMENU, 'revision_3'
    elif intencion == 'siniestro_1':
        return "📋 *Solicitud iniciada:* PERITAJE TÉCNICO DAÑOS MENORES ($65.000).\nEvaluación de carrocería, ópticos y abolladuras leves con reporte digital para cotización de repuestos." + SUBMENU, 'siniestro_1'
    elif intencion == 'siniestro_2':
        return "📋 *Solicitud iniciada:* PERITAJE TÉCNICO DAÑOS MAYORES ($120.000).\nMedición estructural de chasis, evaluación mecánica post-colisión severa y estimación de pérdida." + SUBMENU, 'siniestro_2'
    elif intencion == 'siniestro_3':
        return "📋 *Solicitud iniciada:* INFORME TÉCNICO OFICIAL ASEGURADORA ($100.000).\nConfección de dossier legal con registro fotográfico de alta definición y firmas necesarias para la liquidación del seguro." + SUBMENU, 'siniestro_3'
    elif intencion == 'mecanica_1':
        return "📋 *Solicitud iniciada:* MANTENCION PREVENTIVA FLOTAS ($55.000 por unidad).\nCambios de filtros, aceites y pautas kilométricas de mantención programada para empresas con operaciones activas." + SUBMENU, 'mecanica_1'
    elif intencion == 'mecanica_2':
        return "📋 *Solicitud iniciada:* DIAGNÓSTICO COMPLETO CON ESCÁNER OBD ($70.000).\nLectura en tiempo real de códigos de falla (DTC) del computador del vehículo, borrado de alertas e informe de sensores." + SUBMENU, 'mecanica_2'
    elif intencion == 'mecanica_3':
        return "📋 *Solicitud iniciada:* MECÁNICA CORRECTIVA AVANZADA ($110.000).\nIntervención directa en componentes de motor, distribución, embragues o sistemas de transmisión compleja a domicilio." + SUBMENU, 'mecanica_3'
    
    else:
        return ('No logré identificar la solicitud en lenguaje natural. Puedes intentar reformular tu frase o seleccionar una opción digital marcando del 1 al 5.' + SUBMENU, 'desconocido')

def procesar_mensaje(texto, usuario='web'):
    # Intercepción prioritaria del flujo: Capturar nombre para el agente de soporte
    if estado_usuarios.get(usuario) == 'esperando_nombre':
        nombre_cliente = texto.strip()
        estado_usuarios.pop(usuario) # Liberamos el estado de bloqueo de este usuario
        
        # Persistencia atómica de la solicitud del ejecutivo en la base de datos relacional
        nueva_solicitud = SolicitudAgente(usuario=usuario, nombre=nombre_cliente)
        try:
            session.add(nueva_solicitud)
            session.commit()
        except Exception as e:
            session.rollback()
            print("Error al guardar solicitud de agente:", e)
            
        return (f'Muchas gracias, {nombre_cliente}. Hemos registrado tu solicitud en nuestra base de datos. Un ejecutivo comercial de Austral Road SPA tomará el control de esta ventana para continuar la atención personalizada.' + SUBMENU, 'nombre_agente')

    intencion = detectar_intencion(texto)
    return generar_respuesta(intencion, usuario)

# ENDPOINT AUTOMÁTICO DE WHATSAPP (Integración Twilio)
@app.route("/bot", methods=['POST'])
def bot():
    try:
        incoming_msg = request.values.get('Body', '').strip()
        usuario = request.values.get('From', '').lower()
        resp = MessagingResponse()
        msg = resp.message()

        nuevo_historial = HistorialInteracciones(usuario=usuario, mensaje=incoming_msg)
        session.add(nuevo_historial)
        session.commit()

        respuesta_texto, opcion = procesar_mensaje(incoming_msg, usuario)
        msg.body(respuesta_texto)

        session.add(Mensaje(opcion=opcion, respuesta=respuesta_texto))
        session.commit()

        return str(resp)

    except SQLAlchemyError as e:
        session.rollback()
        print("Error en Capa de Persistencia DB:", e)
        return str(MessagingResponse().message("Error en el servidor de base de datos. Intente nuevamente."))
    except Exception as e:
        print("Error General:", e)
        return str(MessagingResponse().message("Error inesperado en la pasarela. Intente nuevamente."))

# ENDPOINT DE DESPLIEGUE WEB (Consola interactiva)
@app.route("/chat-web", methods=['POST'])
def chat_web():
    try:
        data = request.get_json()
        incoming_msg = data.get('message', '').strip()
        usuario = 'web'

        nuevo_historial = HistorialInteracciones(usuario=usuario, mensaje=incoming_msg)
        session.add(nuevo_historial)
        session.commit()

        respuesta_texto, opcion = procesar_mensaje(incoming_msg, usuario)

        session.add(Mensaje(opcion=opcion, respuesta=respuesta_texto))
        session.commit()

        return jsonify({'response': respuesta_texto})

    except Exception as e:
        print("Error en API Web:", e)
        return jsonify({'response': 'Error de comunicación con el clúster. Intente nuevamente.'}), 500

@app.route("/")
def index():
    return "Chatbot Austral Road SPA v2.0 - Capa Corporativa e Inteligencia Artificial Activa ✅"

if __name__ == "__main__":
    app.run(port=5000, debug=True)
