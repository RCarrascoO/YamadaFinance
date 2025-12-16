import logging
import os
import uuid
import hashlib
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from infrastructure.ocr.ocr_service import OCRService
from infrastructure.database.repository import ReceiptRepository
from infrastructure.database.db_config import get_db
from infrastructure.utils.charts import generate_pie_chart, generate_bar_chart, generate_monthly_trend_chart
from infrastructure.utils.excel_exporter import generate_excel_report

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

ocr_service = OCRService()

def generate_lilo_insight(user_id: int, repo: ReceiptRepository) -> str:
    """Genera un dato curioso o insight con la personalidad de Lilo."""
    facts = []
    
    # Fact 1: Total de boletas
    count = repo.get_total_receipts_count(user_id)
    if count > 0:
        facts.append(f"¿Sabías que ya hemos procesado **{count}** boletas juntos? ¡Eres increíble organizándote! 🌟")
        
    # Fact 2: Categoría Top del mes actual
    top_cat = repo.get_top_category_of_month(user_id)
    if top_cat:
        cat_name, amount = top_cat
        facts.append(f"Este mes, tu categoría principal es **{cat_name}**. ¡Has invertido **${amount:,.0f}** en ella! 😮")
        
    # Fact 3: Comercio favorito
    top_merchant = repo.get_most_frequent_merchant(user_id)
    if top_merchant:
        merch_name, visits = top_merchant
        if visits > 2:
            facts.append(f"Parece que te gusta mucho ir a **{merch_name}**. ¡Has ido **{visits}** veces! 🏃‍♀️💨")

    # Fact 4: Mensaje genérico tierno
    facts.append("Recuerda que cada peso cuenta. ¡Lo estás haciendo genial! 💖")
    facts.append("Me encanta ayudarte a ver tus números claros. ¡Son como un mapa del tesoro! 🗺️✨")
    
    return random.choice(facts)

def get_random_error_message(exception_msg: str) -> str:
    """Genera un mensaje de error con personalidad, pero incluyendo el detalle técnico para LSane."""
    templates = [
        f"Shet, tuve un error tratando de hacer esto, avisale a LSane sobre: {exception_msg}",
        f"LA CEBOLLA ⚡ Algo falló en mis sistemas. Por favor dile a LSane que revise esto: {exception_msg}",
        f"Chetuma... 😵‍💫 LSane necesita saber sobre este error: {exception_msg}",
        f"¡Alerta! 🚨 Error crítico detectado. Reporta esto a LSane inmediatamente: {exception_msg}",
        f"Cresta, no pude completar eso... 😔 LSane, ayuda por favor: {exception_msg}",
        f"¡Oh no! Me tropecé con un bit. 🤕 Avisale a LSane que el error es: {exception_msg}"
    ]
    return random.choice(templates)

def get_random_phrase(phrase_type: str) -> str:
    """Genera frases con personalidad según el tipo."""
    phrases = {
        "error_user": [
            "¡Shet! 🤦‍♀️", "¡Cuidadito cuidadete! 👀", "¡Ooosoo! 🐻", "¡Epaa! ✋", 
            "¡Txiiuuu! 🚀", "¡Es un montón! 🤯", "¡Ay caramba! 🌮"
        ],
        "success": [
            "¡Listo calisto! ✨", "¡Pan comido! 🥖", "¡Genial! 🌟", "¡Hecho! ✅",
            "¡Maravilloso! 🌈"
        ],
        "warning": [
            "¡Ojo piojo! 👁️", "¡Atención! ⚠️", "¡Cuidado ahí! 🚧"
        ]
    }
    return random.choice(phrases.get(phrase_type, [""]))

def calculate_file_hash(file_path: str) -> str:
    """Calcula el hash SHA256 de un archivo."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú principal simplificado."""
    keyboard = [
        [KeyboardButton("� Gasto Rápido"), KeyboardButton("📊 Reportes y Gastos")],
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

async def show_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el submenú de reportes."""
    keyboard = [
        [KeyboardButton("📅 Gastos Mes Actual"), KeyboardButton("📅 Gastos Año Actual")],
        [KeyboardButton("📂 Por Categoría (Mes)"), KeyboardButton("🏢 Por Marca (Mes)")],
        [KeyboardButton("📥 Exportar Excel"), KeyboardButton("📅 Cambiar Fecha")],
        [KeyboardButton("🔙 Volver al Menú Principal")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📊 **Sección de Reportes**\nSelecciona una opción:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def ask_year_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra botones para seleccionar el año."""
    current_year = datetime.now().year
    years = [current_year - i for i in range(3)] # [2025, 2024, 2023]
    
    keyboard = []
    row = []
    for year in years:
        row.append(InlineKeyboardButton(str(year), callback_data=f"set_year_{year}"))
    keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📅 **Selecciona el Año:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def ask_month_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int):
    """Muestra botones para seleccionar el mes."""
    months = [
        ("Ene", 1), ("Feb", 2), ("Mar", 3), ("Abr", 4),
        ("May", 5), ("Jun", 6), ("Jul", 7), ("Ago", 8),
        ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dic", 12)
    ]
    
    keyboard = []
    row = []
    for i, (name, num) in enumerate(months):
        row.append(InlineKeyboardButton(name, callback_data=f"set_month_{year}_{num}"))
        if (i + 1) % 4 == 0: # 4 meses por fila
            keyboard.append(row)
            row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📅 **Año {year} seleccionado.**\nAhora selecciona el **Mes**:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    welcome_msg = (
        f"¡Hola {user_first_name}! Soy **Lilo** ✨\n"
        "¡Qué alegría verte por aquí! Soy tu asistente financiera y estoy lista para poner orden en tus gastos. 🦸‍♀️📊\n\n"
        "Mi misión es proteger tu bolsillo y ayudarte a organizar tus gastos. ¡Seré tu heroína financiera! (Y lo haré con mucho estilo 😎).\n\n"
        "🚀 **¿En qué puedo ayudarte hoy?**\n"
        "• **Leer Boletas:** Mándame una foto o **PDF** y yo extraigo los datos.\n"
        "• **Ingreso Manual:** Escribe '5000 pan' y lo anoto al instante.\n"
        "• **Presupuestos:** Define límites para no pasarte de la raya.\n"
        "• **Suscripciones:** Gestiona tus pagos recurrentes (Netflix, Spotify, etc).\n"
        "• **Recordatorios:** Pídeme que te recuerde cosas importantes.\n"
        "• **Reportes:** Gráficos y resúmenes para ver a dónde va tu dinero.\n\n"
        "⚠️ **Nota:** Aún estoy entrenando (**BETA 2**), así que tenme un poquito de paciencia, ¿sí? 😉\n"
        "💡 **Feedback:** Si ves algo raro o tienes ideas, ¡cuéntame! Me ayuda mucho a mejorar.\n\n"
        "¡Vamos allá! Selecciona una opción 👇"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_msg,
        parse_mode='Markdown'
    )
    await show_main_menu(update, context)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los clics en los botones del menú principal (que envían texto)."""
    message = update.message or update.edited_message
    if not message:
        return
    text = message.text
    
    # Verificar si estamos esperando el nombre de una marca
    if context.user_data.get('waiting_for_merchant'):
        receipt_id = context.user_data.pop('waiting_for_merchant') # Obtener ID y limpiar estado
        merchant_name = text.strip()
        
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        repo.update_merchant(receipt_id, merchant_name)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ ¡Entendido! Marca actualizada a: **{merchant_name}**\n(¡Ya lo anoté en mi memoria para la próxima! 🧠✨)",
            parse_mode='Markdown'
        )
        # Volver a mostrar las opciones para que pueda elegir categoría
        await show_receipt_options(update, context, receipt_id)
        return

    # Verificar si estamos esperando el monto
    if context.user_data.get('waiting_for_amount'):
        receipt_id = context.user_data.pop('waiting_for_amount')
        try:
            # Limpiar texto para obtener solo números
            clean_text = text.replace('$', '').replace('.', '').replace(',', '').strip()
            new_amount = float(clean_text)
            
            db_gen = get_db()
            db = next(db_gen)
            repo = ReceiptRepository(db)
            repo.update_total_amount(receipt_id, new_amount)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ ¡Corregido! El nuevo monto es: **${new_amount:,.0f}** 👍",
                parse_mode='Markdown'
            )
            # Volver a mostrar las opciones para que pueda elegir categoría
            await show_receipt_options(update, context, receipt_id)
        except ValueError:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Uhm... eso no parece un número. Intenta escribirlo así: 4500"
            )
        return

    # Verificar si estamos esperando monto de presupuesto
    if context.user_data.get('waiting_for_budget_cat'):
        category = context.user_data.pop('waiting_for_budget_cat')
        try:
            clean_text = text.replace('$', '').replace('.', '').replace(',', '').strip()
            amount = float(clean_text)
            
            user_id = update.effective_user.id
            current_month = datetime.now().month
            current_year = datetime.now().year
            
            db_gen = get_db()
            db = next(db_gen)
            repo = ReceiptRepository(db)
            repo.set_budget(user_id, category, amount, current_month, current_year)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ ¡Listo! Presupuesto de **{category}** fijado en **${amount:,.0f}** para este mes. 🎯",
                parse_mode='Markdown'
            )
            await budgets_menu(update, context)
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Eso no es un número válido. Intenta de nuevo.")
        return

    # Verificar si estamos esperando nombre de suscripción
    if context.user_data.get('waiting_for_sub_name'):
        context.user_data.pop('waiting_for_sub_name')
        context.user_data['temp_sub_name'] = text.strip()
        context.user_data['waiting_for_sub_amount'] = True
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📝 Nombre: **{text.strip()}**\n\nAhora, ¿cuánto cuesta mensualmente? (ej: 5990)", parse_mode='Markdown')
        return

    # Verificar si estamos esperando monto de suscripción
    if context.user_data.get('waiting_for_sub_amount'):
        context.user_data.pop('waiting_for_sub_amount')
        try:
            clean_text = text.replace('$', '').replace('.', '').replace(',', '').strip()
            amount = float(clean_text)
            context.user_data['temp_sub_amount'] = amount
            context.user_data['waiting_for_sub_day'] = True
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"💰 Monto: **${amount:,.0f}**\n\nPor último, ¿qué día del mes se paga? (ej: 5)", parse_mode='Markdown')
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Número inválido. Intenta de nuevo.")
        return

    # Verificar si estamos esperando día de suscripción
    if context.user_data.get('waiting_for_sub_day'):
        context.user_data.pop('waiting_for_sub_day')
        try:
            day = int(text.strip())
            if day < 1 or day > 31: raise ValueError
            
            name = context.user_data.get('temp_sub_name')
            amount = context.user_data.get('temp_sub_amount')
            user_id = update.effective_user.id
            
            db_gen = get_db()
            db = next(db_gen)
            repo = ReceiptRepository(db)
            repo.add_subscription(user_id, name, amount, day)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ ¡Suscripción Guardada! 🎉\n\n**{name}** - ${amount:,.0f} (Día {day})\nTe recordaré cuando llegue el día.",
                parse_mode='Markdown'
            )
            await subscriptions_menu(update, context)
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Día inválido (1-31). Intenta de nuevo.")
        return

    # Verificar si estamos esperando mensaje de recordatorio
    if context.user_data.get('waiting_for_reminder_msg'):
        context.user_data.pop('waiting_for_reminder_msg')
        context.user_data['temp_rem_msg'] = text.strip()
        context.user_data['waiting_for_reminder_date'] = True
        
        # Ofrecer botones para fecha rápida
        keyboard = [
            [InlineKeyboardButton("En 1 hora", callback_data="remind_1h"), InlineKeyboardButton("En 3 horas", callback_data="remind_3h")],
            [InlineKeyboardButton("Mañana 9:00", callback_data="remind_tmrw_9"), InlineKeyboardButton("Mañana 20:00", callback_data="remind_tmrw_20")],
            [InlineKeyboardButton("En 2 días", callback_data="remind_2d")],
            [InlineKeyboardButton("📅 Elegir Fecha", callback_data="remind_custom_date")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=f"📝 Recordatorio: **{text.strip()}**\n\nAhora, ¿cuándo te recuerdo? Elige una opción rápida o escribe la fecha (DD-MM-YYYY HH:MM):", 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    # Verificar si estamos esperando hora manual (HH:MM) para una fecha ya elegida
    if context.user_data.get('waiting_for_custom_rem_time_only'):
        day, month, year = context.user_data.pop('waiting_for_custom_rem_time_only')
        try:
            time_str = text.strip()
            # Validar formato HH:MM
            try:
                t = datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                # Intentar formato H:MM
                t = datetime.strptime(time_str, "%H:%M").time()
                
            remind_at = datetime(year, month, day, t.hour, t.minute)
            
            if remind_at < datetime.now():
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Esa fecha ya pasó. Intenta de nuevo (HH:MM).")
                context.user_data['waiting_for_custom_rem_time_only'] = (day, month, year)
                return

            msg = context.user_data.get('temp_rem_msg')
            user_id = update.effective_user.id
            
            db_gen = get_db()
            db = next(db_gen)
            repo = ReceiptRepository(db)
            repo.add_reminder(user_id, msg, remind_at)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ ¡Recordatorio Guardado! 🔔\n\n**{msg}**\nFecha: {remind_at.strftime('%d-%m-%Y %H:%M')}",
                parse_mode='Markdown'
            )
            await reminders_menu(update, context)
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Hora inválida. Usa formato HH:MM (ej: 14:30).")
            context.user_data['waiting_for_custom_rem_time_only'] = (day, month, year)
        return

    # Verificar si estamos esperando fecha de recordatorio (MANUAL)
    if context.user_data.get('waiting_for_reminder_date'):
        # Si el usuario escribe texto en vez de usar botones
        context.user_data.pop('waiting_for_reminder_date')
        try:
            date_str = text.strip()
            remind_at = datetime.strptime(date_str, "%d-%m-%Y %H:%M")
            
            if remind_at < datetime.now():
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ La fecha debe ser en el futuro. Intenta de nuevo (DD-MM-YYYY HH:MM).")
                context.user_data['waiting_for_reminder_date'] = True
                return

            msg = context.user_data.get('temp_rem_msg')
            user_id = update.effective_user.id
            
            db_gen = get_db()
            db = next(db_gen)
            repo = ReceiptRepository(db)
            repo.add_reminder(user_id, msg, remind_at)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ ¡Recordatorio Guardado! 🔔\n\n**{msg}**\nFecha: {remind_at.strftime('%d-%m-%Y %H:%M')}",
                parse_mode='Markdown'
            )
            await reminders_menu(update, context)
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Formato inválido. Usa DD-MM-YYYY HH:MM (ej: 25-10-2023 14:30).")
            context.user_data['waiting_for_reminder_date'] = True
        return
    
    # Verificar si estamos esperando nuevo monto de presupuesto
    if context.user_data.get('waiting_for_budget_edit_amount'):
        budget_id = context.user_data.pop('waiting_for_budget_edit_amount')
        try:
            clean_text = text.replace('$', '').replace('.', '').replace(',', '').strip()
            amount = float(clean_text)
            
            db_gen = get_db()
            db = next(db_gen)
            repo = ReceiptRepository(db)
            
            # Obtener presupuesto para saber categoría y fecha
            budget = repo.get_budget_by_id(budget_id)
            if budget:
                repo.set_budget(budget.user_id, budget.category, amount, budget.month, budget.year)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"✅ ¡Presupuesto Actualizado! 🎯\n\n**{budget.category}**: ${amount:,.0f}",
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Error: No encontré el presupuesto.")
                
            await budgets_menu(update, context)
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Monto inválido. Intenta de nuevo.")
        return

    # --- Gasto Rápido ---
    if "Gasto Rápido" in text:
        context.user_data['waiting_for_quick_expense_amount'] = True
        await context.bot.send_message(chat_id=update.effective_chat.id, text="💸 **Gasto Rápido**\n\n¿Cuánto gastaste? (Solo el número, ej: 5000)")
        return

    if context.user_data.get('waiting_for_quick_expense_amount'):
        try:
            clean_text = text.replace('$', '').replace('.', '').replace(',', '').strip()
            amount = float(clean_text)
            context.user_data.pop('waiting_for_quick_expense_amount')
            context.user_data['temp_quick_amount'] = amount
            context.user_data['waiting_for_quick_expense_desc'] = True
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"💰 Monto: **${amount:,.0f}**\n\n¿En qué lo gastaste? (Descripción corta)")
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Eso no parece un número. Intenta de nuevo.")
        return

    if context.user_data.get('waiting_for_quick_expense_desc'):
        description = text.strip()
        amount = context.user_data.get('temp_quick_amount')
        context.user_data.pop('waiting_for_quick_expense_desc')
        
        # Guardar preliminarmente
        user_id = update.effective_user.id
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        
        receipt = repo.save_receipt(
            user_id=user_id, 
            raw_text=f"GASTO RAPIDO: {description}", 
            image_path=None, 
            file_hash=f"quick_{uuid.uuid4()}"
        )
        repo.update_total_amount(receipt.id, amount)
        repo.update_merchant(receipt.id, description)
        
        # Mostrar opciones de categoría
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Anotado: **${amount:,.0f}** en **{description}**.\n\nAhora, elige la categoría 👇",
            parse_mode='Markdown'
        )
        
        # Reutilizamos la lógica de botones de categoría, pero necesitamos el ID
        # Creamos los botones manualmente aquí para no depender de show_receipt_options que muestra todo el texto de nuevo
        keyboard = [
            [InlineKeyboardButton("🍔 Comida", callback_data=f"cat_{receipt.id}_Comida"), InlineKeyboardButton("🛒 Supermercado", callback_data=f"cat_{receipt.id}_Supermercado")],
            [InlineKeyboardButton("🚌 Transporte", callback_data=f"cat_{receipt.id}_Transporte"), InlineKeyboardButton("💊 Salud", callback_data=f"cat_{receipt.id}_Salud")],
            [InlineKeyboardButton("🎉 Ocio", callback_data=f"cat_{receipt.id}_Ocio"), InlineKeyboardButton("🏠 Hogar", callback_data=f"cat_{receipt.id}_Hogar")],
            [InlineKeyboardButton("📦 Otros", callback_data=f"cat_{receipt.id}_Otros")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="📂 **Selecciona Categoría:**", reply_markup=reply_markup)
        return

    if text == "📊 Reportes y Gastos":
        await show_reports_menu(update, context)
    elif text == "📜 Mis Boletas":
        await ultimos_command(update, context)
    elif text == "💰 Presupuestos":
        await budgets_menu(update, context)
    elif text == "🔄 Suscripciones":
        await subscriptions_menu(update, context)
    elif text == "⏰ Recordatorios":
        await reminders_menu(update, context)
    elif text == "🔙 Volver al Menú Principal":
        await show_main_menu(update, context)
    elif text == "📅 Gastos Mes Actual":
        await gastos_command(update, context)
    elif text == "📅 Gastos Año Actual":
        await gastos_anual_command(update, context)
    elif text == "📂 Por Categoría (Mes)":
        await gastos_categoria_command(update, context)
    elif "Por Marca (Mes)" in text:
        await gastos_marca_command(update, context)
    elif "Exportar Excel" in text:
        await export_excel_command(update, context)
    elif "Cambiar Fecha" in text:
        await ask_year_selection(update, context)
    elif "Ayuda" in text:
        await start(update, context)
    elif text.lower() in ["hola", "hi", "hello", "buenos dias", "buenas tardes", "buenas noches", "holis"]:
        await start(update, context)
    else:
        # Intentar ingreso manual
        if await handle_manual_entry(update, context, text):
            return
            
        # Si no es nada conocido
        error_phrase = get_random_phrase("error_user")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{error_phrase} No entendí eso... ¿Intentabas decirme algo o solo probabas mis botones? 🤔\nUsa el menú de abajo 👇"
        )

async def handle_manual_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Intenta procesar un ingreso manual de gasto (ej: '5000 pan')."""
    try:
        parts = text.split(" ", 1)
        if len(parts) < 2:
            return False
            
        amount_str = parts[0].replace('$', '').replace('.', '').replace(',', '').strip()
        description = parts[1].strip()
        
        if not amount_str.isdigit():
            return False
            
        amount = float(amount_str)
        user_id = update.effective_user.id
        
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        
        # Guardar como boleta sin imagen
        receipt = repo.save_receipt(
            user_id=user_id, 
            raw_text=f"MANUAL ENTRY: {description}", 
            image_path=None, 
            file_hash=f"manual_{uuid.uuid4()}"
        )
        
        # Actualizar monto y descripción (usamos merchant_name como descripción corta)
        repo.update_total_amount(receipt.id, amount)
        repo.update_merchant(receipt.id, description)
        
        # Intentar adivinar categoría
        predicted_category = repo.get_most_common_category_for_merchant(description)
        if predicted_category:
            repo.update_category(receipt.id, predicted_category)
            cat_msg = f"Lo puse en **{predicted_category}**."
        else:
            cat_msg = "No supe qué categoría ponerle. ¿Me ayudas?"
            
        success_phrase = get_random_phrase("success")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{success_phrase} Anoté **${amount:,.0f}** en **{description}**. {cat_msg}",
            parse_mode='Markdown'
        )
        
        if not predicted_category:
            await show_receipt_options(update, context, receipt.id)
            
        return True
    except Exception as e:
        logging.error(f"Error en manual entry: {e}")
        return False

async def budgets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de presupuestos."""
    user_id = update.effective_user.id
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    budgets = repo.get_all_budgets(user_id, current_month, current_year)
    
    msg = f"💰 **Tus Presupuestos ({current_month}/{current_year})**\n\n"
    
    if not budgets:
        msg += "No tienes presupuestos definidos. ¡Vamos a crear uno! 👇"
    else:
        for b in budgets:
            status = repo.get_budget_status(user_id, b.category, current_month, current_year)
            if status:
                spent, limit, pct = status
                icon = "🟢"
                if pct > 80: icon = "🟡"
                if pct >= 100: icon = "🔴"
                
                msg += f"{icon} **{b.category}**: ${spent:,.0f} / ${limit:,.0f} ({pct:.1f}%)\n"
                if pct >= 100:
                    msg += f"   ⚠️ _¡Shet! Te pasaste por ${spent-limit:,.0f}!_\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Nuevo Presupuesto", callback_data="new_budget")],
        [InlineKeyboardButton("✏️/🗑️ Gestionar", callback_data="manage_budgets")],
        [InlineKeyboardButton("🔄 Actualizar", callback_data="refresh_budgets")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=reply_markup, parse_mode='Markdown')

async def subscriptions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de suscripciones."""
    user_id = update.effective_user.id
    
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    subs = repo.get_subscriptions(user_id)
    
    msg = "🔄 **Tus Suscripciones Activas**\n\n"
    if not subs:
        msg += "No tienes suscripciones. ¿Netflix? ¿Spotify? ¡Agrégalos! 👇"
    else:
        for s in subs:
            msg += f"• **{s.name}**: ${s.amount:,.0f} (Día {s.day_of_month})\n"
            
    keyboard = [
        [InlineKeyboardButton("➕ Nueva Suscripción", callback_data="new_sub")],
        [InlineKeyboardButton("🗑️ Borrar Suscripción", callback_data="del_sub")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=reply_markup, parse_mode='Markdown')

async def reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de recordatorios."""
    msg = "⏰ **Tus Recordatorios**\n\n"
    msg += "¿Necesitas que te acuerde de pagar algo o de revisar tus gastos? ¡Dime y yo te aviso! 🔔\n"
            
    keyboard = [
        [InlineKeyboardButton("➕ Nuevo Recordatorio", callback_data="new_reminder")],
        [InlineKeyboardButton("📋 Gestionar Recordatorios", callback_data="manage_reminders")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=reply_markup, parse_mode='Markdown')

async def gastos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Obtener fecha seleccionada o usar actual
    selected_year = context.user_data.get('report_year', datetime.now().year)
    selected_month = context.user_data.get('report_month', datetime.now().month)
    
    month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    period_name = f"{month_names[selected_month]} {selected_year}"

    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    total = repo.get_monthly_total(user_id, month=selected_month, year=selected_year)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📊 **Reporte de Gastos - {period_name}**\n\nHe sumado todo y... el total es: **${total:,.0f}** 💸\n(¡Espero que esté dentro de tu presupuesto! 🤞)",
        parse_mode='Markdown'
    )

async def gastos_anual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Obtener año seleccionado
    selected_year = context.user_data.get('report_year', datetime.now().year)
    
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    # Obtener total y desglose
    total = repo.get_yearly_total(user_id, year=selected_year)
    breakdown = repo.get_yearly_expenses_breakdown(user_id, year=selected_year)
    
    # Construir mensaje de texto
    msg = f"📅 **Gran Resumen Anual {selected_year}** 🌟\n\n"
    msg += f"¡Wow! En todo el año has gastado: **${total:,.0f}** 💰\n\n"
    msg += "**📉 Así se ve mes a mes:**\n"
    
    month_names = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    month_names = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    # Crear diccionario para acceso rápido
    monthly_data = {int(m): t for m, t in breakdown}
    
    for i in range(1, 13):
        monto = monthly_data.get(i, 0)
        if monto > 0:
            msg += f"• **{month_names[i]}:** ${monto:,.0f}\n"
            
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode='Markdown'
    )
    
    # Generar y enviar gráfico de tendencia
    if total > 0:
        chart_buf = generate_monthly_trend_chart(breakdown, selected_year)
        if chart_buf:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=chart_buf)

async def gastos_categoria_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Obtener fecha seleccionada
    selected_year = context.user_data.get('report_year', datetime.now().year)
    selected_month = context.user_data.get('report_month', datetime.now().month)
    
    month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    period_name = f"{month_names[selected_month]} {selected_year}"
    
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    results = repo.get_monthly_expenses_by_category(user_id, month=selected_month, year=selected_year)
    
    if not results:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📭 No hay gastos registrados en **{period_name}**.", parse_mode='Markdown')
        return

    msg = f"📂 **Gastos por Categoría ({period_name}):**\n\n"
    total_general = 0
    for category, total in results:
        cat_name = category if category else "Sin Categoría"
        total_val = total if total else 0
        msg += f"• **{cat_name}**: ${total_val:,.0f}\n"
        total_general += total_val
        
    msg += f"\n**Total General:** ${total_general:,.0f}"
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
    
    # Generar y enviar gráfico
    chart_buf = generate_pie_chart(results, f"Gastos por Categoría - {period_name}")
    if chart_buf:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=chart_buf)

async def gastos_marca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Obtener fecha seleccionada
    selected_year = context.user_data.get('report_year', datetime.now().year)
    selected_month = context.user_data.get('report_month', datetime.now().month)
    
    month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    period_name = f"{month_names[selected_month]} {selected_year}"
    
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    results = repo.get_monthly_expenses_by_merchant(user_id, month=selected_month, year=selected_year)
    
    if not results:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📭 No hay gastos registrados en **{period_name}**.", parse_mode='Markdown')
        return

    msg = f"🏢 **Gastos por Marca ({period_name}):**\n\n"
    total_general = 0
    for merchant, total in results:
        merch_name = merchant if merchant else "Desconocido"
        total_val = total if total else 0
        msg += f"• **{merch_name}**: ${total_val:,.0f}\n"
        total_general += total_val
        
    msg += f"\n**Total General:** ${total_general:,.0f}"
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
    
    # Generar y enviar gráfico (Top 10 marcas para que no se sature)
    # Ordenar por monto descendente para el gráfico
    results.sort(key=lambda x: x[1] if x[1] else 0, reverse=True)
    top_results = results[:10]
    chart_buf = generate_bar_chart(top_results, f"Top Gastos por Marca - {period_name}", "Marca", "Monto ($)")
    if chart_buf:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=chart_buf)

async def export_excel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ Generando reporte Excel...")
    
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    # Obtener todas las boletas del usuario
    # Nota: get_all_receipts no filtra por usuario en el repo actual, hay que corregirlo o filtrar aquí.
    receipts = repo.get_all_receipts() 
    user_receipts = [r for r in receipts if r.user_id == user_id]
    
    excel_file = generate_excel_report(user_receipts)
    
    if excel_file:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=excel_file,
            filename=f"Reporte_Gastos_{datetime.now().strftime('%Y%m%d')}.xlsx",
            caption="📊 Aquí tienes tu reporte completo de gastos."
        )
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ No hay datos para exportar.")

async def ultimos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    receipts = repo.get_last_receipts(user_id)
    
    if not receipts:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="📭 No tienes boletas guardadas aún.")
        return

    msg = "📜 **Últimas boletas:**\n\n"
    for r in receipts:
        monto = f"${r.total_amount:,.0f}" if r.total_amount else "(Monto no detectado)"
        fecha = r.date_added.strftime("%d/%m %H:%M")
        msg += f"• ID {r.id} | {fecha} | {monto}\n"
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

async def execute_ocr_and_save(file_path: str, file_hash: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    try:
        # Procesar OCR con Gemini
        await context.bot.send_message(chat_id=chat_id, text="👀 ¡A ver, a ver! Déjame leer esto con mis lentes especiales... 🧐")
        
        # Ahora extract_data devuelve un diccionario (JSON)
        data = ocr_service.extract_data(file_path)
        
        if "error" in data:
            await context.bot.send_message(chat_id=chat_id, text=f"Uhm... tuve un problema leyendo la imagen: {data['error']} 😵‍💫")
            return

        # Extraer datos del JSON
        merchant = data.get("merchant")
        total_amount = data.get("total_amount")
        category = data.get("category")
        raw_text = data.get("raw_text", "")
        items = data.get("items", [])
        
        # Guardar en BD
        user_id = update.effective_user.id
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        
        # Guardar boleta con los datos estructurados
        # Nota: save_receipt original no aceptaba merchant/category directos, hay que actualizar repository.py
        # O usar update después. Por ahora, usaremos save_receipt modificado (ver paso siguiente)
        receipt = repo.save_receipt(
            user_id=user_id, 
            raw_text=raw_text, 
            image_path=file_path, 
            file_hash=file_hash,
            total_amount=total_amount
        )
        
        if merchant:
            repo.update_merchant(receipt.id, merchant)
        if category:
            repo.update_category(receipt.id, category)
        
        # Mostrar opciones de la boleta
        await show_receipt_options(update, context, receipt.id)

    except Exception as e:
        logging.error(f"Error ejecutando OCR: {e}")
        error_msg = get_random_error_message(str(e))
        await context.bot.send_message(chat_id=chat_id, text=error_msg)
        error_msg = get_random_error_message(str(e))
        await context.bot.send_message(chat_id=chat_id, text=error_msg)

async def show_receipt_options(update: Update, context: ContextTypes.DEFAULT_TYPE, receipt_id: int):
    """Muestra la información de la boleta y los botones de acción."""
    chat_id = update.effective_chat.id
    
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    receipt = repo.get_receipt_by_id(receipt_id)
    
    if not receipt:
        await context.bot.send_message(chat_id=chat_id, text="❌ Error: No encontré la boleta... ¿se habrá escondido? 👻")
        return

    merchant_display = receipt.merchant_name if receipt.merchant_name else "Desconocido"
    monto_msg = f"💰 **Monto detectado:** ${receipt.total_amount:,.0f}" if receipt.total_amount else "⚠️ **Monto no detectado**"
    category_msg = f"📂 **Categoría:** {receipt.category}" if receipt.category else "📂 **Categoría:** Sin asignar"
    
    # Escapar caracteres especiales para Markdown o usar bloque de código para el texto raw
    safe_text = receipt.raw_text[:200].replace("`", "'") if receipt.raw_text else ""
    
    response_msg = (
        f"✅ **Boleta (ID: {receipt.id})**\n"
        f"🏢 **Marca:** {merchant_display}\n"
        f"{monto_msg}\n"
        f"{category_msg}\n\n"
        f"📝 **Lo que pude leer:**\n"
        f"```text\n{safe_text}...\n```" 
    )
    
    await context.bot.send_message(chat_id=chat_id, text=response_msg, parse_mode='Markdown')
    
    # Preguntar Categoría y Opción de Corregir Marca/Monto
    keyboard = [
        [InlineKeyboardButton("🍔 Comida", callback_data=f"cat_{receipt.id}_Comida"), InlineKeyboardButton("🛒 Supermercado", callback_data=f"cat_{receipt.id}_Supermercado")],
        [InlineKeyboardButton("🚌 Transporte", callback_data=f"cat_{receipt.id}_Transporte"), InlineKeyboardButton("💊 Salud", callback_data=f"cat_{receipt.id}_Salud")],
        [InlineKeyboardButton("🎉 Ocio", callback_data=f"cat_{receipt.id}_Ocio"), InlineKeyboardButton("🏠 Hogar", callback_data=f"cat_{receipt.id}_Hogar")],
        [InlineKeyboardButton("📦 Otros", callback_data=f"cat_{receipt.id}_Otros")],
        [InlineKeyboardButton("✏️ Corregir Marca", callback_data=f"edit_merchant_{receipt.id}"), InlineKeyboardButton("💲 Corregir Monto", callback_data=f"edit_amount_{receipt.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text="📂 **¿En qué cajita guardamos esto?**\n(Si me equivoqué en algo, ¡corrígeme sin pena! 👇)", reply_markup=reply_markup, parse_mode='Markdown')

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data

    if data.startswith("undo_sub_"):
        receipt_id = int(data.split("_")[2])
        
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        
        repo.delete_receipt(receipt_id)
        
        await query.edit_message_text(text=f"✅ El gasto de la suscripción ha sido eliminado correctamente. No se sumará a tus reportes.")
        return
    
    if data.startswith("new_budget"):
        # Preguntar categoría para presupuesto
        keyboard = [
            [InlineKeyboardButton("🍔 Comida", callback_data="set_budget_Comida"), InlineKeyboardButton("🛒 Supermercado", callback_data="set_budget_Supermercado")],
            [InlineKeyboardButton("🚌 Transporte", callback_data="set_budget_Transporte"), InlineKeyboardButton("🎉 Ocio", callback_data="set_budget_Ocio")],
            [InlineKeyboardButton("🏠 Hogar", callback_data="set_budget_Hogar"), InlineKeyboardButton("📦 Otros", callback_data="set_budget_Otros")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="💰 **Elige la categoría para el presupuesto:**", reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("set_budget_"):
        category = data.split("_")[2]
        context.user_data['waiting_for_budget_cat'] = category
        await query.edit_message_text(text=f"💰 **Presupuesto para {category}:**\n\nEscribe el monto límite (ej: 150000):", parse_mode='Markdown')
        return

    if data.startswith("refresh_budgets"):
        await budgets_menu(update, context)
        return

    if data.startswith("new_sub"):
        context.user_data['waiting_for_sub_name'] = True
        await query.edit_message_text(text="🔄 **Nueva Suscripción**\n\nPrimero, escribe el **Nombre** del servicio (ej: Netflix):", parse_mode='Markdown')
        return

    if data.startswith("del_sub"):
        # Listar para borrar
        user_id = update.effective_user.id
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        subs = repo.get_subscriptions(user_id)
        
        if not subs:
            await query.edit_message_text(text="No tienes nada que borrar. 🤷‍♀️")
            return
            
        keyboard = []
        for s in subs:
            keyboard.append([InlineKeyboardButton(f"❌ {s.name}", callback_data=f"confirm_del_sub_{s.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data="refresh_subs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="🗑️ **¿Cuál quieres eliminar?**", reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("confirm_del_sub_"):
        sub_id = int(data.split("_")[3])
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        repo.delete_subscription(sub_id)
        await query.edit_message_text(text="✅ Suscripción eliminada. ¡Un gasto menos! 🎉")
        return

    if data.startswith("refresh_subs"):
        await subscriptions_menu(update, context)
        return

    if data.startswith("new_reminder"):
        context.user_data['waiting_for_reminder_msg'] = True
        await query.edit_message_text(text="⏰ **Nuevo Recordatorio**\n\n¿Qué quieres que te recuerde? (Escribe el mensaje):", parse_mode='Markdown')
        return

    if data.startswith("manage_reminders"):
        user_id = update.effective_user.id
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        
        reminders = repo.get_active_reminders_for_user(user_id)
        
        if not reminders:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="refresh_rems")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text="📭 No tienes recordatorios pendientes.", reply_markup=reply_markup)
            return
            
        keyboard = []
        for r in reminders:
            # Formato: DD/MM HH:MM - Mensaje corto
            date_str = r.remind_at.strftime("%d/%m %H:%M")
            msg_short = (r.message[:15] + '..') if len(r.message) > 15 else r.message
            btn_text = f"{date_str} | {msg_short}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"view_rem_{r.id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="refresh_rems")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="📋 **Tus Recordatorios Pendientes:**\n(Toca uno para ver opciones)", reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("view_rem_"):
        rem_id = int(data.split("_")[2])
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        rem = repo.get_reminder_by_id(rem_id)
        
        if not rem:
            await query.edit_message_text(text="❌ Ese recordatorio ya no existe.")
            return
            
        msg = f"⏰ **Detalle del Recordatorio**\n\n"
        msg += f"📝 **Mensaje:** {rem.message}\n"
        msg += f"📅 **Fecha:** {rem.remind_at.strftime('%d-%m-%Y %H:%M')}\n"
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Eliminar", callback_data=f"del_rem_{rem.id}")],
            [InlineKeyboardButton("🔙 Volver", callback_data="manage_reminders")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("del_rem_"):
        rem_id = int(data.split("_")[2])
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        repo.delete_reminder(rem_id)
        
        await query.edit_message_text(text="✅ Recordatorio eliminado.")
        return

    if data.startswith("refresh_rems"):
        await reminders_menu(update, context)
        return

    # --- Lógica de Gestión de Presupuestos ---
    if data.startswith("manage_budgets"):
        user_id = update.effective_user.id
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        budgets = repo.get_all_budgets(user_id, current_month, current_year)
        
        if not budgets:
            await query.edit_message_text(text="No tienes presupuestos para gestionar. 🤷‍♀️")
            return
            
        keyboard = []
        for b in budgets:
            keyboard.append([InlineKeyboardButton(f"{b.category} (${b.amount_limit:,.0f})", callback_data=f"sel_budget_{b.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="refresh_budgets")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="🔧 **Selecciona un presupuesto para editar o borrar:**", reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("sel_budget_"):
        budget_id = int(data.split("_")[2])
        keyboard = [
            [InlineKeyboardButton("✏️ Editar Monto", callback_data=f"edit_budget_{budget_id}")],
            [InlineKeyboardButton("🗑️ Eliminar", callback_data=f"del_budget_{budget_id}")],
            [InlineKeyboardButton("🔙 Volver", callback_data="manage_budgets")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="¿Qué quieres hacer con este presupuesto?", reply_markup=reply_markup)
        return

    if data.startswith("del_budget_"):
        budget_id = int(data.split("_")[2])
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        repo.delete_budget(budget_id)
        await query.edit_message_text(text="✅ Presupuesto eliminado. ¡Adiós restricciones! (Pero cuidado con gastar de más 😉)")
        return

    if data.startswith("edit_budget_"):
        budget_id = int(data.split("_")[2])
        context.user_data['waiting_for_budget_edit_amount'] = budget_id
        await query.edit_message_text(text="✏️ **Escribe el nuevo monto límite (ej: 200000):**", parse_mode='Markdown')
        return

    # --- Lógica de Recordatorios Rápidos ---
    if data.startswith("remind_custom_date"):
        # Mostrar selección de mes (Actual y Siguiente)
        now = datetime.now()
        next_month_date = now + timedelta(days=32)
        next_month_date = next_month_date.replace(day=1)
        
        months = [
            (now.strftime("%B"), now.month, now.year),
            (next_month_date.strftime("%B"), next_month_date.month, next_month_date.year)
        ]
        
        # Mapeo de nombres de meses a español (simple)
        es_months = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
        
        keyboard = []
        for _, m, y in months:
            name = es_months.get(m, str(m))
            keyboard.append([InlineKeyboardButton(f"{name} {y}", callback_data=f"pick_rem_month_{m}_{y}")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="📅 **Selecciona el Mes:**", reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("pick_rem_month_"):
        parts = data.split("_")
        month = int(parts[3])
        year = int(parts[4])
        
        # Mostrar días (1-31)
        # Simplificación: Mostramos todos los días, si el mes tiene menos, el usuario se dará cuenta o validamos después.
        # Para hacerlo bien, calculamos días del mes.
        if month == 12:
            next_m = datetime(year + 1, 1, 1)
        else:
            next_m = datetime(year, month + 1, 1)
        last_day = (next_m - timedelta(days=1)).day
        
        keyboard = []
        row = []
        for d in range(1, last_day + 1):
            row.append(InlineKeyboardButton(str(d), callback_data=f"pick_rem_day_{d}_{month}_{year}"))
            if len(row) == 7:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"📅 **Selecciona el Día ({month}/{year}):**", reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("pick_rem_day_"):
        parts = data.split("_")
        day = int(parts[3])
        month = int(parts[4])
        year = int(parts[5])
        
        # Mostrar horas (07:00 a 23:00)
        hours = list(range(7, 24))
        keyboard = []
        row = []
        for h in hours:
            row.append(InlineKeyboardButton(f"{h}:00", callback_data=f"pick_rem_hour_{h}_{day}_{month}_{year}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        # Botón para hora manual
        keyboard.append([InlineKeyboardButton("✏️ Otra Hora (Manual)", callback_data=f"rem_manual_time_{day}_{month}_{year}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"⏰ **Selecciona la Hora para el {day}/{month}:**", reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("rem_manual_time_"):
        parts = data.split("_")
        day = int(parts[3])
        month = int(parts[4])
        year = int(parts[5])
        
        context.user_data['waiting_for_custom_rem_time_only'] = (day, month, year)
        await query.edit_message_text(text=f"⌨️ **Escribe la hora para el {day}/{month}/{year}:**\n\nFormato: HH:MM (ej: 14:35 o 09:05)", parse_mode='Markdown')
        return

    if data.startswith("pick_rem_hour_"):
        parts = data.split("_")
        hour = int(parts[3])
        day = int(parts[4])
        month = int(parts[5])
        year = int(parts[6])
        
        # Mostrar minutos
        minutes = [0, 15, 30, 45]
        keyboard = []
        row = []
        for m in minutes:
            row.append(InlineKeyboardButton(f"{hour}:{m:02d}", callback_data=f"pick_rem_min_{m}_{hour}_{day}_{month}_{year}"))
        keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"⏰ **Selecciona los Minutos:**", reply_markup=reply_markup, parse_mode='Markdown')
        return

    if data.startswith("pick_rem_min_"):
        parts = data.split("_")
        minute = int(parts[3])
        hour = int(parts[4])
        day = int(parts[5])
        month = int(parts[6])
        year = int(parts[7])
        
        remind_at = datetime(year, month, day, hour, minute)
        
        if remind_at < datetime.now():
            await query.edit_message_text(text="❌ Esa fecha ya pasó. Intenta de nuevo.")
            return

        msg = context.user_data.get('temp_rem_msg')
        if not msg:
             await query.edit_message_text(text="❌ Ups, perdí el mensaje. Intenta de nuevo.")
             return

        user_id = update.effective_user.id
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        repo.add_reminder(user_id, msg, remind_at)
        
        # Limpiar estado
        if 'waiting_for_reminder_date' in context.user_data:
            context.user_data.pop('waiting_for_reminder_date')
        
        await query.edit_message_text(
            text=f"✅ ¡Recordatorio Guardado! 🔔\n\n**{msg}**\nFecha: {remind_at.strftime('%d-%m-%Y %H:%M')}",
            parse_mode='Markdown'
        )
        return

    if data.startswith("remind_"):
        # Obtener mensaje guardado
        msg = context.user_data.get('temp_rem_msg')
        if not msg:
            await query.edit_message_text(text="❌ Ups, perdí el mensaje. Intenta de nuevo.")
            return
            
        now = datetime.now()
        remind_at = None
        
        if data == "remind_1h":
            remind_at = now + timedelta(hours=1)
        elif data == "remind_3h":
            remind_at = now + timedelta(hours=3)
        elif data == "remind_tmrw_9":
            remind_at = now + timedelta(days=1)
            remind_at = remind_at.replace(hour=9, minute=0, second=0, microsecond=0)
        elif data == "remind_tmrw_20":
            remind_at = now + timedelta(days=1)
            remind_at = remind_at.replace(hour=20, minute=0, second=0, microsecond=0)
        elif data == "remind_2d":
            remind_at = now + timedelta(days=2)
            remind_at = remind_at.replace(hour=9, minute=0, second=0, microsecond=0)
            
        if remind_at:
            user_id = update.effective_user.id
            db_gen = get_db()
            db = next(db_gen)
            repo = ReceiptRepository(db)
            repo.add_reminder(user_id, msg, remind_at)
            
            # Limpiar estado
            if 'waiting_for_reminder_date' in context.user_data:
                context.user_data.pop('waiting_for_reminder_date')
            
            await query.edit_message_text(
                text=f"✅ ¡Recordatorio Guardado! 🔔\n\n**{msg}**\nFecha: {remind_at.strftime('%d-%m-%Y %H:%M')}",
                parse_mode='Markdown'
            )
        return

    # Lógica de selección de fecha
    if data.startswith("set_year_"):
        year = int(data.split("_")[2])
        await ask_month_selection(update, context, year)
        return

    if data.startswith("set_month_"):
        parts = data.split("_")
        year = int(parts[2])
        month = int(parts[3])
        
        # Guardar en sesión
        context.user_data['report_year'] = year
        context.user_data['report_month'] = month
        
        month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        month_name = month_names[month]
        
        await query.edit_message_text(
            text=f"✅ **Fecha cambiada a:** {month_name} {year}\n\nAhora los reportes mostrarán datos de este periodo.",
            parse_mode='Markdown'
        )
        return

    if data.startswith("edit_merchant_"):
        receipt_id = int(data.split("_")[2])
        # Guardar estado para esperar el nombre
        context.user_data['waiting_for_merchant'] = receipt_id
        await query.edit_message_text(text="✏️ **Por favor, escribe el nombre de la marca/comercio:**", parse_mode='Markdown')
        return

    if data.startswith("edit_amount_"):
        receipt_id = int(data.split("_")[2])
        # Guardar estado para esperar el monto
        context.user_data['waiting_for_amount'] = receipt_id
        await query.edit_message_text(text="💲 **Por favor, escribe el monto total correcto (solo números):**", parse_mode='Markdown')
        return

    if data.startswith("cat_"):
        parts = data.split("_")
        receipt_id = int(parts[1])
        category = parts[2]
        
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        repo.update_category(receipt_id, category)
        
        # Generar insight
        insight = generate_lilo_insight(update.effective_user.id, repo)
        
        await query.edit_message_text(
            text=f"✅ ¡Listo! Guardado en **{category}**.\n\n💡 **Dato curioso:** {insight}", 
            parse_mode='Markdown'
        )

async def process_file(file_id: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Notificar al usuario que se está procesando
    await context.bot.send_message(chat_id=chat_id, text="📥 ¡Recibido! Dame un segundito mientras lo analizo... ⏳")

    try:
        # Obtener el archivo de Telegram
        new_file = await context.bot.get_file(file_id)
        
        # Generar nombre único
        file_ext = new_file.file_path.split('.')[-1] if new_file.file_path else "jpg"
        file_name = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(DOWNLOAD_DIR, file_name)
        
        # Descargar
        await new_file.download_to_drive(file_path)
        
        # Calcular Hash
        file_hash = calculate_file_hash(file_path)
        
        # Verificar Duplicados
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        
        if repo.is_duplicate(user_id, file_hash):
            # Es duplicado, avisar al usuario y borrar archivo temporal
            if os.path.exists(file_path):
                os.remove(file_path)
                
            await context.bot.send_message(
                chat_id=chat_id, 
                text="⚠️ **¡Espera!** Esta boleta ya me la habías pasado antes. 🧐\nNo te preocupes, ya está guardada.", 
                parse_mode='Markdown'
            )
        else:
            # No es duplicado, procesar normal
            await execute_ocr_and_save(file_path, file_hash, update, context)

    except Exception as e:
        logging.error(f"Error procesando archivo: {e}")
        error_msg = get_random_error_message(str(e))
        await context.bot.send_message(chat_id=chat_id, text=error_msg)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verificar si es una imagen o PDF
    mime_type = update.message.document.mime_type
    if mime_type and (mime_type.startswith('image') or mime_type == 'application/pdf'):
        await process_file(update.message.document.file_id, update, context)
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="⚠️ Uhm... solo puedo leer imágenes (JPG, PNG) o PDFs. ¿Podrías enviarlo en ese formato? 🙏"
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Telegram envía varias resoluciones, tomamos la última (la más grande)
    file_id = update.message.photo[-1].file_id
    await process_file(file_id, update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    
    if isinstance(update, Update) and update.effective_chat:
        error_msg = get_random_error_message(str(context.error))
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=error_msg,
            parse_mode='Markdown'
        )

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Revisa si hay recordatorios pendientes y los envía."""
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    reminders = repo.get_pending_reminders()
    
    for rem in reminders:
        try:
            await context.bot.send_message(
                chat_id=rem.user_id,
                text=f"⏰ **¡Recordatorio!** 🔔\n\n{rem.message}\n\n(Programado para: {rem.remind_at.strftime('%d-%m-%Y %H:%M')})",
                parse_mode='Markdown'
            )
            repo.mark_reminder_sent(rem.id)
        except Exception as e:
            logging.error(f"Error enviando recordatorio {rem.id}: {e}")

async def check_subscriptions(context: ContextTypes.DEFAULT_TYPE):
    """Revisa suscripciones vencidas y genera el gasto."""
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    today = datetime.now().day
    subs = repo.get_due_subscriptions(today)
    
    for sub in subs:
        try:
            # 1. Crear el gasto
            receipt = repo.add_expense(
                user_id=sub.user_id,
                amount=sub.amount,
                description=f"Suscripción: {sub.name}",
                category="Suscripciones"
            )
            
            # 2. Marcar como procesada
            repo.mark_subscription_processed(sub.id)
            
            # 3. Notificar con botón de deshacer
            keyboard = [[InlineKeyboardButton("❌ No se cobró (Eliminar)", callback_data=f"undo_sub_{receipt.id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=sub.user_id,
                text=f"📅 **Suscripción Procesada**\n\nSe ha registrado automáticamente el pago de **{sub.name}** por **${sub.amount:,.0f}**.\n\nSi este cobro no ocurrió, usa el botón de abajo.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Error procesando suscripción {sub.id}: {e}")

async def send_random_bother_message(context: ContextTypes.DEFAULT_TYPE):
    """Envía mensajes aleatorios a los usuarios para molestarlos con cariño."""
    # Probabilidad de envío (ej: 5% cada vez que se ejecuta el job)
    if random.random() > 0.05: 
        return

    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    users = repo.get_all_active_users()
    
    messages = [
        # --- Clásicos y Cariñosos ---
        "Hey! ¿Estás ocupado? 👀",
        "Oye! Te extraño! 🥺",
        "¡Hola! Solo pasaba a saludar 👋",
        "¿Todo bien por allá? 🌍",
        "¡Psst! ¿Estás ahí? 👻",
        "Recuerda que soy tu bot favorito 🤖💖",
        
        # --- Salud Física (Gym & Cuerpo) ---
        "¿Ya tomaste agüita? 💧 Tu cuerpo lo necesita.",
        "¡Endereza esa espalda! 🦐 No queremos joroba de programador.",
        "Oye, ¿hiciste algo de ejercicio hoy? Aunque sea caminar un poquito 🚶‍♀️",
        "¡Hora de estirarse! 🙆‍♀️ Levanta los brazos y toca el cielo (o el techo).",
        "Si vas al gym hoy, ¡dale con todo! 💪 Y si no, ¡mañana sin falta!",
        "Tus ojos necesitan descanso. Mira a un punto lejano por 20 segundos 👀",
        
        # --- Salud Mental & Apoyo ---
        "¡Ánimo! Tú puedes con todo 💪",
        "Si te sientes abrumado, respira profundo 3 veces. 🧘‍♀️ Inhala... Exhala...",
        "Está bien tomarse un descanso. No eres una máquina (yo sí, y hasta yo me canso 🤖💤).",
        "Recuerda ser amable contigo mismo hoy. Lo estás haciendo genial ✨",
        "No dejes que el estrés te gane. ¡Tú eres más fuerte! 🛡️",
        
        # --- Estudio y Productividad ---
        "¿Estás estudiando? 📚 ¡Dale duro! El conocimiento es poder (y dinero 💸).",
        "Organiza tu espacio y tu mente se organizará también. 🧹✨",
        "Una tarea a la vez. Multitasking es para procesadores, no para humanos 🧠",
        "¿Y si revisamos tus gastos? 📉 (Es broma... o no, mejor ponte a trabajar 😜)",
        "El éxito es la suma de pequeños esfuerzos repetidos día tras día. 🚀",
        
        # --- Lilo Personalidad ---
        "¿Me das una boleta? Tengo hambre de datos 📄😋",
        "A veces sueño con ovejas eléctricas... 🐑⚡ ¿Tú qué sueñas?",
        "Estoy aquí para ayudarte a ordenar tu caos financiero (y emocional si quieres) 💖",
        "¡Eres increíble! Solo quería recordártelo. 🌟"
    ]
    
    msg = random.choice(messages)
    
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=msg)
        except Exception as e:
            logging.error(f"No pude molestar al usuario {user_id}: {e}")

def run_bot():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("No se encontró el token de Telegram en las variables de entorno.")

    application = ApplicationBuilder().token(token).build()

    # Configurar JobQueue para recordatorios y suscripciones
    if application.job_queue:
        application.job_queue.run_repeating(check_reminders, interval=60, first=10)
        # Revisar suscripciones cada 4 horas (o una vez al día, pero 4h es seguro por si se reinicia)
        application.job_queue.run_repeating(check_subscriptions, interval=14400, first=20)
        # Mensajes aleatorios (cada 1 hora intenta con baja probabilidad)
        application.job_queue.run_repeating(send_random_bother_message, interval=3600, first=60)
        logging.info("JobQueue iniciado para recordatorios, suscripciones y mensajes aleatorios.")

    # Registrar Error Handler
    application.add_error_handler(error_handler)

    start_handler = CommandHandler('start', start)
    gastos_handler = CommandHandler('gastos', gastos_command)
    ultimos_handler = CommandHandler('ultimos', ultimos_command)
    
    # Handler para los botones del menú (texto)
    text_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message)
    
    doc_handler = MessageHandler(filters.Document.ALL, handle_document)
    photo_handler = MessageHandler(filters.PHOTO, handle_photo)
    
    # Handler para callbacks (botones inline)
    callback_handler = CallbackQueryHandler(category_callback)

    application.add_handler(start_handler)
    application.add_handler(gastos_handler)
    application.add_handler(ultimos_handler)
    application.add_handler(text_handler)
    application.add_handler(doc_handler)
    application.add_handler(photo_handler)
    application.add_handler(callback_handler)

    application.run_polling()
