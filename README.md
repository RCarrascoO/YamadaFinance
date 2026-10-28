# YamadaFinance — AI-Powered Personal Finance & Multimodal Receipt OCR

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram_Bot_API-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![Google Gemini Flash](https://img.shields.io/badge/Google_Gemini-Flash_Vision-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

**YamadaFinance** es un asistente autónomo e inteligente de gestión de finanzas personales diseñado para Telegram. Combina la velocidad del registro en lenguaje natural con el poder del modelo multimodal **Gemini Flash** de Google para procesar boletas, recibos y facturas en tiempo real a partir de fotos o documentos PDF.

---

## ✨ Características Principales

- 🧾 **OCR Multimodal con Gemini Flash**: Envía una foto o documento PDF de cualquier comprobante o boleta de compra. El modelo extrae automáticamente el comercio, la fecha, los ítems y el monto total en segundos.
- 💬 **Registro Rápido en Lenguaje Natural**: Anota gastos al vuelo escribiendo directamente en el chat (por ejemplo: `4500 almuerzo` o `12990 bencina shell`).
- 📊 **Reportes y Analíticas Visuales**:
  - Resumen mensual y anual detallado.
  - Desglose por categoría y top de comercios más frecuentados.
  - Generación de gráficos y exportación completa a planillas Excel (`.xlsx`).
- 🎯 **Presupuestos Inteligentes**: Fija límites de gasto mensuales por categoría y monitorea el porcentaje consumido en tiempo real.
- 🔄 **Gestión de Suscripciones**: Controla servicios y pagos recurrentes (mensuales o anuales), calculando el impacto en tu flujo mensual.
- ⏰ **Recordatorios y Notificaciones Programadas**: Sistema de alertas automáticas para pagos y tareas pendientes mediante JobQueue.
- 🔒 **Privacidad Total y Auto-hospedado**: Todos los datos residen en tu propia instancia de PostgreSQL y tus credenciales nunca salen de tu servidor.
- 🎮 **Easter Eggs Geek**: Integración con divertidas respuestas de la cultura pop (HAL 9000, Matrix, JARVIS, Skynet, Yamada).

---

## 🏗️ Arquitectura del Sistema

El proyecto sigue principios de **Clean Architecture** para desacoplar la lógica de dominio, la persistencia y los canales de comunicación:

```text
src/
├── domain/                    # Entidades centrales y reglas de negocio puras
│   ├── receipt.py             # Modelo de dominio de comprobantes
│   └── parser.py              # Parser de lenguaje natural para gastos rápidos
├── infrastructure/            # Implementaciones concretas de infraestructura
│   ├── database/              # Conexión SQLAlchemy, modelos ORM y repositorio
│   ├── ocr/                   # Integración con Google GenAI SDK (Gemini Flash)
│   ├── telegram/              # Configuración y arranque del bot de Telegram
│   └── utils/                 # Generación de gráficos y exportadores a Excel
├── interface_adapters/        # Adaptadores y controladores de interacción
│   └── telegram/handlers/     # Handlers de gastos, presupuestos, reportes y suscripciones
└── main.py                    # Punto de entrada de la aplicación
```

---

## 🚀 Despliegue con Docker Compose (Recomendado)

### 1. Requisitos Previos

- [Docker Engine](https://docs.docker.com/engine/install/) (20.10+)
- [Docker Compose](https://docs.docker.com/compose/) (v2+)
- Un token de Bot de Telegram obtenido en [@BotFather](https://t.me/botfather).
- Una API Key de [Google AI Studio](https://aistudio.google.com/).

### 2. Clonar y Configurar

Clona el repositorio y crea tu archivo `.env` a partir de la plantilla:

```bash
git clone https://github.com/RCarrascoO/YamadaFinance.git
cd YamadaFinance
cp .env.example .env
```

Edita `.env` con tus claves:

```env
TELEGRAM_BOT_TOKEN=tu_token_de_botfather
GEMINI_API_KEY=tu_gemini_api_key
TIMEZONE=America/Santiago
```

### 3. Iniciar el Servicio

Levanta el contenedor de la base de datos PostgreSQL y el bot:

```bash
docker compose up -d --build
```

Revisa los logs del servicio para verificar el arranque:

```bash
docker compose logs -f bot
```

---

## 💻 Ejecución Local para Desarrollo

Si prefieres ejecutar el proyecto localmente sin Docker:

### Requisitos del Sistema
- Python 3.11+
- Instalar Poppler (necesario para convertir PDF a imágenes):
  - **Arch Linux / CachyOS**: `sudo pacman -S poppler`
  - **Ubuntu / Debian**: `sudo apt install poppler-utils`
  - **macOS**: `brew install poppler`
- Servidor PostgreSQL activo.

### Instalación

```bash
# Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# (Ajusta DATABASE_URL para que apunte a tu PostgreSQL local)

# Ejecutar el bot
python src/main.py
```

---

## ⚙️ Variables de Entorno

| Variable | Descripción | Valor por Defecto / Ejemplo |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Token del bot provisto por @BotFather | *Obligatorio* |
| `GEMINI_API_KEY` | Clave de API de Google AI Studio | *Obligatorio* |
| `DATABASE_URL` | URI de conexión a la base de datos | `postgresql://yamada_finance_user:yamada_finance_password@db:5432/yamada_finance_db` |
| `DB_USER` | Usuario de base de datos PostgreSQL | `yamada_finance_user` |
| `DB_PASSWORD` | Contraseña de base de datos PostgreSQL | `yamada_finance_password` |
| `DB_NAME` | Nombre de base de datos PostgreSQL | `yamada_finance_db` |
| `DB_HOST` | Host de base de datos | `db` |
| `TIMEZONE` / `TZ` | Zona horaria del bot | `America/Santiago` |

---

## 🤖 Comandos y Flujo de Uso

1. Inicia el bot enviando `/start` en Telegram.
2. Utiliza el teclado interactivo en pantalla:
   - **💸 Gasto Rápido**: Ingresa montos como `3500 café` o `12000 supermercado`.
   - **📜 Mis Boletas**: Consulta las últimas transacciones procesadas con OCR.
   - **📊 Reportes y Gastos**: Accede a métricas mensuales, anuales o descarga un Excel.
   - **💰 Presupuestos**: Define límites mensuales para no excederte en tus gastos.
   - **🔄 Suscripciones**: Da de alta cargos recurrentes como Netflix, Spotify o iCloud.
3. Envía una fotografía o archivo PDF de cualquier recibo o factura y YamadaFinance se encargará del resto.

---

## 🛡️ Licencia

Distribuido bajo la Licencia **MIT**. Consulta `LICENSE` para más detalles.
