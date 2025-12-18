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
from interface_adapters.telegram.handlers.common import start, check_easter_eggs, show_main_menu
from interface_adapters.telegram.handlers.reports import (
    show_reports_menu, ask_year_selection, ask_month_selection,
    gastos_command, gastos_anual_command, gastos_categoria_command,
    gastos_marca_command, export_excel_command, ultimos_command,
    handle_report_callbacks
)
from interface_adapters.telegram.handlers.expenses import (
    handle_manual_entry, execute_ocr_and_save, show_receipt_options,
    process_file, handle_document, handle_photo, handle_expense_callbacks
)
from interface_adapters.telegram.handlers.budgets import (
    budgets_menu, handle_budget_callbacks, handle_budget_text_input
)
from interface_adapters.telegram.handlers.subscriptions import (
    subscriptions_menu, handle_subscription_callbacks, handle_subscription_text_input
)
from interface_adapters.telegram.handlers.reminders import (
    handle_reminder_callbacks, reminders_menu, ReminderActions
)
from interface_adapters.telegram.handlers.common import get_random_phrase, get_random_error_message

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

ocr_service = OCRService()

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los clics en los botones del menú principal (que envían texto)."""
    message = update.message or update.edited_message
    if not message:
        return
    text = message.text
    logging.info(f"Recibido mensaje de texto: '{text}'")
    
    # Verificar Easter Eggs y Comandos de Menú
    if await check_easter_eggs(update, context, text):
        logging.info("Handled by check_easter_eggs")
        return

    # --- PRIORIDAD: Comandos de Submenús (para evitar que se tomen como input de texto) ---
    if text == "🔙 Volver al Menú Principal" or text == "Volver al Menú Principal":
        # Limpiar cualquier estado pendiente al volver al menú
        context.user_data.clear()
        await show_main_menu(update, context)
        return
    elif text == "📅 Gastos Mes Actual":
        context.user_data.clear()
        await gastos_command(update, context)
        return
    elif text == "📅 Gastos Año Actual":
        context.user_data.clear()
        await gastos_anual_command(update, context)
        return
    elif text == "📂 Por Categoría (Mes)":
        context.user_data.clear()
        await gastos_categoria_command(update, context)
        return
    elif "Por Marca (Mes)" in text:
        context.user_data.clear()
        await gastos_marca_command(update, context)
        return
    elif "Exportar Excel" in text:
        context.user_data.clear()
        await export_excel_command(update, context)
        return
    elif "Cambiar Fecha" in text:
        context.user_data.clear()
        await ask_year_selection(update, context)
        return

    # --- LÓGICA DE ESTADOS (Solo si no es un comando) ---

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

    # Delegar input de presupuesto
    if await handle_budget_text_input(update, context):
        return

    # Delegar input de suscripciones
    if await handle_subscription_text_input(update, context):
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

    # Verificar si estamos editando mensaje de recordatorio
    if context.user_data.get('waiting_for_rem_edit_msg'):
        rem_id = context.user_data.pop('waiting_for_rem_edit_msg')
        new_msg = text.strip()
        
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        repo.update_reminder(rem_id, message=new_msg)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ ¡Recordatorio Actualizado! 🔔\n\nNuevo mensaje: **{new_msg}**",
            parse_mode='Markdown'
        )
        await reminders_menu(update, context)
        return

    # Verificar si estamos esperando mensaje de recordatorio
    if context.user_data.get('waiting_for_reminder_msg'):
        context.user_data.pop('waiting_for_reminder_msg')
        context.user_data['temp_rem_msg'] = text.strip()
        context.user_data['waiting_for_reminder_date'] = True
        
        # Ofrecer botones para fecha rápida
        keyboard = [
            [InlineKeyboardButton("En 1 hora", callback_data=f"{ReminderActions.QUICK_DATE}|1h"), InlineKeyboardButton("En 3 horas", callback_data=f"{ReminderActions.QUICK_DATE}|3h")],
            [InlineKeyboardButton("Mañana 9:00", callback_data=f"{ReminderActions.QUICK_DATE}|tmrw_9"), InlineKeyboardButton("Mañana 20:00", callback_data=f"{ReminderActions.QUICK_DATE}|tmrw_20")],
            [InlineKeyboardButton("En 2 días", callback_data=f"{ReminderActions.QUICK_DATE}|2d")],
            [InlineKeyboardButton("📅 Elegir Fecha", callback_data=ReminderActions.CUSTOM_DATE_PICKER)],
            [InlineKeyboardButton("🔙 Volver", callback_data=ReminderActions.MENU)]
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

            user_id = update.effective_user.id
            db_gen = get_db()
            db = next(db_gen)
            repo = ReceiptRepository(db)

            # Verificar si estamos editando
            editing_id = context.user_data.get('editing_reminder_id')
            if editing_id:
                repo.update_reminder(editing_id, remind_at=remind_at)
                context.user_data.pop('editing_reminder_id')
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"✅ ¡Fecha Actualizada! 🔔\n\nNueva Fecha: {remind_at.strftime('%d-%m-%Y %H:%M')}",
                    parse_mode='Markdown'
                )
                await reminders_menu(update, context)
                return

            msg = context.user_data.get('temp_rem_msg')
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

    # Intentar ingreso manual
    if await handle_manual_entry(update, context, text):
        return

    # --- SALUDOS (Al final, para no interferir con inputs) ---
    if text.lower() in ["hola", "hi", "hello", "buenos dias", "buenas tardes", "buenas noches", "holis"]:
        context.user_data.clear()
        await start(update, context)
        return
        
    # Si no es nada conocido
    error_phrase = get_random_phrase("error_user")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"{error_phrase} No entendí eso... ¿Intentabas decirme algo o solo probabas mis botones? 🤔\nUsa el menú de abajo 👇"
    )

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logging.info(f"CALLBACK RECEIVED: {data}")

    # Delegar a handlers modulares
    if await handle_expense_callbacks(update, context):
        logging.info("Handled by expense callbacks")
        return
    if await handle_report_callbacks(update, context):
        logging.info("Handled by report callbacks")
        return
    if await handle_budget_callbacks(update, context):
        logging.info("Handled by budget callbacks")
        return
    if await handle_subscription_callbacks(update, context):
        logging.info("Handled by subscription callbacks")
        return
    
    logging.info("Not handled by main modules, checking manual overrides...")

    if data.startswith("undo_sub_"):
        receipt_id = int(data.split("_")[2])
        
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        
        repo.delete_receipt(receipt_id)
        
        await query.edit_message_text(text=f"✅ El gasto de la suscripción ha sido eliminado correctamente. No se sumará a tus reportes.")
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

    logging.info("Checking reminder callbacks...")
    # Delegar a handlers de recordatorios
    if await handle_reminder_callbacks(update, context):
        logging.info("Handled by reminder callbacks")
        return

    logging.info("Not handled by any callback handler")

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

    # Lógica de selección de fecha
    if await handle_report_callbacks(update, context):
        return

    # Lógica de gastos (Delegada)
    if await handle_expense_callbacks(update, context):
        return

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    
    if isinstance(update, Update) and update.effective_chat:
        error_msg = get_random_error_message(str(context.error))
        # Escapar caracteres especiales de Markdown si es necesario, o no usar Markdown para el error
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=error_msg
            # parse_mode='Markdown'  <-- Quitamos esto para evitar errores de parseo en mensajes de error complejos
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
    presupuestos_handler = CommandHandler('presupuestos', budgets_menu)
    suscripciones_handler = CommandHandler('suscripciones', subscriptions_menu)
    
    # Handler para los botones del menú (texto)
    text_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message)
    
    doc_handler = MessageHandler(filters.Document.ALL, handle_document)
    photo_handler = MessageHandler(filters.PHOTO, handle_photo)
    
    # Handler para callbacks (botones inline)
    callback_handler = CallbackQueryHandler(category_callback)

    application.add_handler(start_handler)
    application.add_handler(gastos_handler)
    application.add_handler(ultimos_handler)
    application.add_handler(presupuestos_handler)
    application.add_handler(suscripciones_handler)
    application.add_handler(text_handler)
    application.add_handler(doc_handler)
    application.add_handler(photo_handler)
    application.add_handler(callback_handler)

    application.run_polling()
