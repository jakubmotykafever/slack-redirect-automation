# Slack Redirect Automation

Automatiza el proceso de gestionar peticiones de redirecciones de URLs desde un canal de Slack, guardándolas en Google Sheets y ejecutando el flujo de N8N.

## Descripción

Este sistema lee mensajes del canal de Slack `#smn_redirect_requests`, extrae las URLs de redirección de diferentes formatos de mensaje, las guarda en Google Sheets y ejecuta automáticamente el webhook de N8N para procesar las redirecciones.

## Características

- **Parser inteligente**: Reconoce múltiples formatos de peticiones de redirección:
  - Formato `Old/New`
  - Formato `from/to`
  - Múltiples URLs viejas hacia una nueva
  - URLs en español (`vieja/nueva`)
  
- **Integración completa**:
  - Slack: Lee mensajes y marca como procesados con emoji
  - Google Sheets: Almacena todas las redirecciones
  - N8N: Ejecuta el flujo de redirección automáticamente

- **Despliegue en Cloud**: Configurado para Google Cloud Functions con Cloud Scheduler

## Requisitos

- Python 3.11+
- Cuenta de Google Cloud Platform
- Slack App con permisos de lectura del canal
- Flujo de N8N con webhook configurado
- Google Sheets API habilitada

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/slack-redirect-automation.git
cd slack-redirect-automation
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copia el archivo de ejemplo y configura tus credenciales:

```bash
cp .env.example .env
```

Edita `.env` con tus valores:

```env
SLACK_BOT_TOKEN=xoxb-tu-token-de-slack
SLACK_CHANNEL_ID=C0123456789
GOOGLE_SHEETS_ID=tu-id-de-google-sheets
N8N_WEBHOOK_URL=https://tu-n8n.com/webhook/tu-webhook-id
GOOGLE_CREDENTIALS_JSON=path/to/credentials.json
```

### 4. Configurar credenciales de Google

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un proyecto o selecciona uno existente
3. Habilita la API de Google Sheets
4. Crea una cuenta de servicio y descarga las credenciales JSON
5. Comparte tu Google Sheet con el email de la cuenta de servicio

### 5. Configurar Slack App

Tu Slack App necesita los siguientes permisos (OAuth Scopes):

- `channels:history` - Leer mensajes del canal
- `channels:read` - Ver información del canal
- `reactions:write` - Añadir reacciones (para marcar como procesado)
- `reactions:read` - Leer reacciones existentes

## Uso

### Ejecución local

```bash
python -m src.main
```

### Ejecutar tests

```bash
pytest tests/ -v
```

### Desplegar en Google Cloud

```bash
cd deploy
chmod +x deploy_gcloud.sh
./deploy_gcloud.sh
```

## Estructura del Proyecto

```
REDIRECTION/
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuración y variables de entorno
│   ├── slack_parser.py    # Parser de mensajes de Slack
│   ├── sheets_handler.py  # Integración con Google Sheets
│   ├── n8n_client.py      # Cliente para webhook de N8N
│   └── main.py            # Orquestador principal
├── tests/
│   ├── __init__.py
│   └── test_parser.py     # Tests unitarios
├── deploy/
│   ├── deploy_gcloud.sh   # Script de despliegue
│   └── scheduler_config.yaml
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Formatos de Mensaje Soportados

### Formato 1: Old/New

```
Old: https://example.com/old-url
New: https://example.com/new-url
```

### Formato 2: from/to

```
from: https://example.com/old
to: https://example.com/new
```

### Formato 3: Múltiples URLs viejas

```
Old ones: https://example.com/old1
https://example.com/old2
https://example.com/old3
New: https://example.com/new
```

## Flujo de Trabajo

```mermaid
sequenceDiagram
    participant Scheduler as Cloud Scheduler
    participant Function as Cloud Function
    participant Slack
    participant Sheets as Google Sheets
    participant N8N

    Scheduler->>Function: Trigger (cada 4 horas)
    Function->>Slack: Leer mensajes sin ✅
    Slack-->>Function: Lista de mensajes
    Function->>Function: Parsear URLs
    Function->>Sheets: Guardar redirecciones
    Function->>N8N: Ejecutar webhook
    N8N-->>Function: Respuesta
    Function->>Slack: Añadir emoji ✅
```

## Configuración del Scheduler

Por defecto, el sistema se ejecuta cada 4 horas. Puedes modificar la frecuencia en `deploy/scheduler_config.yaml` o durante el despliegue.

Ejemplos de schedules:
- Cada 2 horas: `0 */2 * * *`
- Tres veces al día: `0 9,13,17 * * *`
- Solo días laborables: `0 9-18 * * 1-5`

## Troubleshooting

### El parser no detecta las URLs

Asegúrate de que el mensaje contiene URLs válidas con `http://` o `https://`. El parser ignora URLs malformadas.

### Error de autenticación de Slack

Verifica que el `SLACK_BOT_TOKEN` es correcto y que la app tiene los permisos necesarios.

### Error de Google Sheets

1. Verifica que el ID del spreadsheet es correcto
2. Asegúrate de que la cuenta de servicio tiene acceso al documento
3. Comprueba que la API de Sheets está habilitada

## Contribuir

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Añade nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## Licencia

MIT License - ver [LICENSE](LICENSE) para más detalles.
