# Chatbot Austral Road SPA v2.0

Chatbot conversacional con procesamiento de lenguaje natural (NLP) integrado a WhatsApp via Twilio y disponible como widget web.

## Novedades v2.0
- Procesamiento de lenguaje natural con spaCy (modelo español)
- Entiende mensajes en lenguaje libre, no solo opciones numeradas
- Deteccion de intenciones: horario, ubicacion, servicios, precios, siniestros, mecanica, agente
- Endpoint /chat-web para integracion con sitio web
- CORS habilitado para conexion desde australroadspa.cl

## Stack
- Python 3 + Flask
- spaCy (es_core_news_sm)
- Twilio WhatsApp Sandbox
- SQLAlchemy + SQLite
- Flask-CORS
- Render (deploy)

## Variables de entorno requeridas en Render
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN

## Endpoints
- POST /bot — webhook Twilio (WhatsApp)
- POST /chat-web — widget web (JSON)
- GET / — health check

## Instalacion local
pip install -r requirements.txt
python app.py

## Autor
Maria Jose Natacha Villarroel Linco — IACC 2024
