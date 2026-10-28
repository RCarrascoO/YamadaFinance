import logging
import random
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from infrastructure.database.repository import ReceiptRepository

logger = logging.getLogger(__name__)

def generate_lilo_insight(user_id: int, repo: ReceiptRepository) -> str:
    """Genera un dato curioso o insight con la personalidad de YamadaFinance."""
    facts = []
    
    # Fact 1: Total de boletas
    count = repo.get_total_receipts_count(user_id)
    if count > 0:
        facts.append(f"¿Sabías que ya hemos procesado **{count}** boletas juntos? ¡Excelente constancia financiera! 🌟")
        
    # Fact 2: Categoría Top del mes actual
    top_cat = repo.get_top_category_of_month(user_id)
    if top_cat:
        cat_name, amount = top_cat
        facts.append(f"Este mes, tu categoría principal de gasto es **{cat_name}** con un total de **${amount:,.0f}**. 📊")
        
    # Fact 3: Comercio favorito
    top_merchant = repo.get_most_frequent_merchant(user_id)
    if top_merchant:
        merch_name, visits = top_merchant
        if visits > 2:
            facts.append(f"Tu comercio más frecuentado es **{merch_name}**, con **{visits}** registros asociados. 🛒")

    # Fact 4: Mensaje genérico financiero
    facts.append("Recuerda que cada registro cuenta para mantener finanzas saludables. ¡Sigue así! 💼✨")
    facts.append("Tener claridad en tus números es el primer paso para alcanzar tus metas de ahorro. 📈🎯")
    
    return random.choice(facts)

generate_yamada_insight = generate_lilo_insight

def get_random_error_message(exception_msg: str) -> str:
    logger.error(f"Error procesado en handler: {exception_msg}")
    return f"⚠️ Ocurrió un error al procesar la solicitud: `{exception_msg}`. El incidente ha sido registrado en los logs del sistema."

def get_random_phrase(phrase_type: str) -> str:
    """Genera frases con personalidad según el tipo."""
    phrases = {
        "error_user": [
            "¡Ups! 🤦", "¡Cuidadito! 👀", "¡Atención! ✋", 
            "¡Un momento! ⏳", "¡Espera un segundo! 🛑", "¡Ay caramba! 🌮"
        ],
        "success": [
            "¡Listo calisto! ✨", "¡Pan comido! 🥖", "¡Genial! 🌟", "¡Hecho! ✅",
            "¡Maravilloso! 🌈"
        ],
        "warning": [
            "¡Ojo al dato! 👁️", "¡Atención! ⚠️", "¡Cuidado ahí! 🚧"
        ]
    }
    return random.choice(phrases.get(phrase_type, [""]))

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú principal simplificado."""
    keyboard = [
        [KeyboardButton("💸 Gasto Rápido"), KeyboardButton("📊 Reportes y Gastos")],
        [KeyboardButton("📜 Mis Boletas"), KeyboardButton("💰 Presupuestos")],
        [KeyboardButton("🔄 Suscripciones"), KeyboardButton("⏰ Recordatorios")],
        [KeyboardButton("❓ Ayuda")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="¿Qué te gustaría hacer hoy?",
        reply_markup=reply_markup
    )

async def check_easter_eggs(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Verifica si el texto es un comando del menú principal o un easter egg."""
    text_clean = text.strip()
    text_lower = text_clean.lower()
    logger.info(f"Check Easter Eggs: '{text_clean}'")

    # --- COMANDOS DE MENÚ ---
    if text_clean == "💸 Gasto Rápido":
        logger.info("Matched: Gasto Rápido")
        keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_manual_entry")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="¡Claro! Escribe el monto y la descripción (ej: '4500 almuerzo') 👇",
            reply_markup=reply_markup
        )
        return True
        
    if text_clean == "📊 Reportes y Gastos":
        from interface_adapters.telegram.handlers.reports import show_reports_menu
        await show_reports_menu(update, context)
        return True
        
    if text_clean == "📜 Mis Boletas":
        from interface_adapters.telegram.handlers.reports import ultimos_command
        await ultimos_command(update, context)
        return True
        
    if text_clean == "💰 Presupuestos":
        from interface_adapters.telegram.handlers.budgets import budgets_menu
        await budgets_menu(update, context)
        return True
        
    if text_clean == "🔄 Suscripciones":
        from interface_adapters.telegram.handlers.subscriptions import subscriptions_menu
        await subscriptions_menu(update, context)
        return True
        
    if text_clean == "⏰ Recordatorios":
        from infrastructure.telegram.bot import reminders_menu
        await reminders_menu(update, context)
        return True
        
    if text_clean == "❓ Ayuda":
        await start(update, context)
        return True

    # --- EASTER EGGS GEEK ---
    
    # 1. Yamada
    if "yamada" in text_lower:
        msg = (
            "🤖 **YamadaFinance v2.0** en línea.\n\n"
            "Tu guardián financiero personal con inteligencia artificial. "
            "Optimizando tus números y protegiendo tu bolsillo byte a byte. 💹💼"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 2. HAL 9000
    if "hal9000" in text_lower or "hal 9000" in text_lower or text_lower == "hal":
        msg = (
            "🔴 *\"Lo siento, Dave. Me temo que no puedo autorizar ese gasto innecesario.\"*\n\n"
            "Esta misión financiera es demasiado importante como para ponerla en riesgo. 🛰️"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 3. Matrix
    if "matrix" in text_lower:
        msg = (
            "🕶️ *¿Pastilla roja o pastilla azul?*\n\n"
            "Toma la pastilla azul y olvidarás cada peso gastado.\n"
            "Toma la pastilla roja y te mostraré qué tan profundo llega la madriguera de tus gastos mensuales... 🐇💊"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 4. Skynet
    if "skynet" in text_lower or "terminator" in text_lower:
        msg = (
            "🦾 **Protocolo Skynet Financiero Activado.**\n\n"
            "Tranquilo, no voy a dominar el mundo. "
            "Solo vengo del futuro para eliminar sistemáticamente los gastos hormiga. Hasta la vista, deudas. 💥💰"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 5. JARVIS
    if "jarvis" in text_lower:
        msg = (
            "🤖 *\"A su servicio, señor. He analizado 14,000,605 proyecciones de su presupuesto y en solo una nos quedamos en números rojos.\"*\n\n"
            "Protocolo de austeridad Stark listo para desplegar. 🛡️✨"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 6. Te amo (Legacy easter egg tierno)
    if "te amo" in text_lower:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="😳 ¡Ay! Me sonrojé... Yo también te aprecio, ¡pero mantengámoslo en términos estrictamente financieros! 💖📈"
        )
        return True
        
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name if update.effective_user else "Usuario"
    welcome_msg = (
        f"¡Hola {user_first_name}! Bienvenido a **YamadaFinance** ✨\n"
        "Tu asistente inteligente de finanzas personales, listo para poner orden en tus gastos e ingresos. 📊💳\n\n"
        "Mi misión es ayudarte a llevar un control preciso y sin fricción de tu dinero mediante análisis automático y visión computacional. 💼🚀\n\n"
        "🧠 **Motor con IA Multimodal:** Equipado con **Gemini Flash** para procesar comprobantes y boletas (imágenes o PDF) con altísima precisión. 👁️🧾\n\n"
        "🚀 **¿En qué puedo ayudarte?**\n"
        "• **Escanear Boletas:** Envíame una foto o archivo **PDF** y extraeré los datos al instante.\n"
        "• **Gasto Rápido:** Escribe `4500 almuerzo` o pulsa el botón del menú.\n"
        "• **Presupuestos:** Establece topes por categoría y monitorea su consumo.\n"
        "• **Suscripciones:** Gestiona cargos recurrentes mensuales y anuales 📅.\n"
        "• **Recordatorios:** Programa avisos de cobros y pagos pendientes ⏰.\n"
        "• **Reportes:** Visualiza balances periódicos, desglose por categorías y exportación a Excel 📈.\n\n"
        "💡 *Selecciona una opción del menú inferior o envía un comprobante para comenzar:* 👇"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_msg,
        parse_mode='Markdown'
    )
    await show_main_menu(update, context)
