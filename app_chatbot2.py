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

# Cargar modelo spaCy
try:
    nlp = spacy.load("es_core_news_sm")
except:
    nlp = None

estado_usuarios = {}

MENU = (
    "Hola, bienvenido a Austral Road SPA. ¿En qué puedo ayudarte?\n"
    "1. Horario de atención\n"
    "2. Ubicación\n"
    "3. Servicios\n"
    "4. Contacto\n"
    "5. Hablar con un agente"
)

SUBMENU = (
    "\n\n¿En qué más puedo ayudarte?\n"
    "1. Horario de atención\n"
    "2. Ubicación\n"
    "3. Servicios\n"
    "4. Contacto\n"
    "5. Hablar con un agente"
)

SERVICIOS = (
    "Nuestros servicios:\n"
    "3.1 Revisiones técnicas a domicilio — $45.000 (básica) / $75.000 (completa)\n"
    "3.2 Asesoría de siniestros para aseguradoras — desde $65.000\n"
    "3.3 Mecánica para empresas — desde $55.000 por vehículo\n\n"
    "Escribe el número del servicio para más información."
)

# Palabras clave por intencion
INTENCIONES = {
    'saludo': ['hola', 'buenas', 'buen día', 'buenos días', 'buenas tardes', 'inicio', 'menu', 'ayuda', 'start', 'comenzar'],
    'horario': ['horario', 'hora', 'cuando', 'atienden', 'abren', 'cierran', 'disponible', 'abierto'],
    'ubicacion': ['donde', 'ubicación', 'dirección', 'lugar', 'como llegar', 'están', 'queda', 'localización'],
    'servicios': ['servicio', 'que hacen', 'que ofrecen', 'revisión', 'mecánica', 'siniestro', 'peritaje', 'mantención', 'diagnóstico', 'informe'],
    'contacto': ['contacto', 'teléfono', 'correo', 'email', 'llamar', 'comunicar', 'número', 'mail'],
    'agente': ['agente', 'persona', 'humano', 'hablar con alguien', 'ejecutivo', 'asesor', 'ayuda personalizada'],
    'precio': ['precio', 'costo', 'cuanto', 'valor', 'cobran', 'tarifa', 'cuánto cuesta'],
    'revision': ['revisión técnica', 'revisar', 'inspección', 'chequeo', 'domicilio'],
    'siniestro': ['siniestro', 'accidente', 'seguro', 'aseguradora', 'peritaje', 'daño', 'choque'],
    'mecanica': ['mecánica', 'mecánico', 'empresa', 'flota', 'mantención', 'reparación'],
}

def detectar_intencion(texto):
    texto_lower = texto.lower()

    # Numeros directos
    if texto_lower.strip() in ['1']: return 'horario'
    if texto_lower.strip() in ['2']: return 'ubicacion'
    if texto_lower.strip() in ['3']: return 'servicios'
    if texto_lower.strip() in ['4']: return 'contacto'
    if texto_lower.strip() in ['5']: return 'agente'
    if texto_lower.strip() in ['3.1']: return 'revision'
    if texto_lower.strip() in ['3.2']: return 'siniestro'
    if texto_lower.strip() in ['3.3']: return 'mecanica'

    # NLP con spaCy si está disponible
    if nlp:
        doc = nlp(texto_lower)
        lemmas = [token.lemma_ for token in doc]
        texto_analizado = ' '.join(lemmas)
    else:
        texto_analizado = texto_lower

    # Buscar intencion por palabras clave
    for intencion, palabras in INTENCIONES.items():
        for palabra in palabras:
            if palabra in texto_analizado or palabra in texto_lower:
                return intencion

    return 'desconocido'

def generar_respuesta(intencion, usuario=None):
    if intencion == 'saludo':
        return MENU, 'saludo'
    elif intencion == 'horario':
        return 'Atendemos de lunes a viernes de 9:00 a 18:00 horas.' + SUBMENU, 'horario'
    elif intencion == 'ubicacion':
        return 'Estamos en Villa Rucahue 600, Puerto Montt.' + SUBMENU, 'ubicacion'
    elif intencion == 'servicios':
        return SERVICIOS, 'servicios'
    elif intencion == 'contacto':
        return 'Teléfono: 555-1234\nCorreo: comercialaustralroad@gmail.com' + SUBMENU, 'contacto'
    elif intencion == 'agente':
        if usuario:
            estado_usuarios[usuario] = 'esperando_nombre'
        return '¿Cuál es tu nombre para conectarte con un agente?', 'agente'
    elif intencion == 'precio':
        return ('Nuestros precios:\n'
                '• Revisión básica: $45.000\n'
                '• Revisión completa: $75.000\n'
                '• Peritaje básico: $65.000\n'
                '• Peritaje completo: $120.000\n'
                '• Informe aseguradora: $100.000\n'
                '• Mantención empresa: $55.000\n'
                '• Diagnóstico domicilio: $70.000\n'
                '• Mecánica correctiva: $110.000' + SUBMENU, 'precio')
    elif intencion == 'revision':
        return ('Revisiones técnicas a domicilio:\n'
                '• Básica (particular): $45.000\n'
                '• Completa (particular): $75.000\n'
                '• Vehículo de carga: $95.000\n\n'
                'Coordinamos la visita en el horario que te acomode.' + SUBMENU, 'revision')
    elif intencion == 'siniestro':
        return ('Asesoría de siniestros para aseguradoras:\n'
                '• Peritaje básico: $65.000\n'
                '• Peritaje completo: $120.000\n'
                '• Informe técnico oficial: $100.000\n\n'
                'Incluye documentación fotográfica y respaldo legal.' + SUBMENU, 'siniestro')
    elif intencion == 'mecanica':
        return ('Mecánica para empresas:\n'
                '• Mantención preventiva: $55.000 por vehículo\n'
                '• Diagnóstico con escáner OBD: $70.000\n'
                '• Mecánica correctiva básica: $110.000\n\n'
                'Atendemos flotas empresariales en toda la región.' + SUBMENU, 'mecanica')
    else:
        return ('No entendí bien tu consulta. Puedes escribir en lenguaje natural o elegir una opción:\n'
                '1. Horario  2. Ubicación  3. Servicios  4. Contacto  5. Agente', 'desconocido')

def procesar_mensaje(texto, usuario='web'):
    # Flujo especial: esperando nombre para agente
    if estado_usuarios.get(usuario) == 'esperando_nombre':
        nombre = texto.strip()
        estado_usuarios.pop(usuario)
        nueva_solicitud = SolicitudAgente(usuario=usuario, nombre=nombre)
        try:
            session.add(nueva_solicitud)
            session.commit()
        except:
            session.rollback()
        return (f'Gracias, {nombre}. Un agente de Austral Road SPA se comunicará contigo pronto.' + SUBMENU, 'nombre_agente')

    intencion = detectar_intencion(texto)
    return generar_respuesta(intencion, usuario)

# ENDPOINT WHATSAPP (Twilio)
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
        print("Error DB:", e)
        return str(MessagingResponse().message("Error interno. Intenta nuevamente."))
    except Exception as e:
        print("Error:", e)
        return str(MessagingResponse().message("Error inesperado. Intenta nuevamente."))

# ENDPOINT WEB
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
        print("Error:", e)
        return jsonify({'response': 'Error de conexión. Intenta nuevamente.'}), 500

@app.route("/")
def index():
    return "Chatbot Austral Road SPA v2.0 activo ✅"

if __name__ == "__main__":
    app.run(port=5000, debug=True)
