import logging
from enum import Enum
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from infrastructure.database.db_config import get_db
from infrastructure.database.repository import ReceiptRepository

class ReminderActions(str, Enum):
    NEW = "REM_NEW"
    LIST = "REM_LIST"
    VIEW = "REM_VIEW"
    EDIT_MENU = "REM_EDIT_MENU"
    EDIT_MSG = "REM_EDIT_MSG"
    EDIT_DATE = "REM_EDIT_DATE"
    DELETE = "REM_DEL"
    QUICK_DATE = "REM_Q_DATE" # 1h, 3h, etc.
    CUSTOM_DATE_PICKER = "REM_C_DATE"
    PICK_MONTH = "REM_P_MONTH"
    PICK_DAY = "REM_P_DAY"
    PICK_HOUR = "REM_P_HOUR"
    PICK_MIN = "REM_P_MIN"
    MANUAL_TIME = "REM_MAN_TIME"
    MENU = "REM_MENU"
    DATE_MENU = "REM_DATE_MENU"

async def reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de recordatorios."""
    msg = "⏰ **Tus Recordatorios**\n\n"
    msg += "¿Necesitas que te acuerde de pagar algo o de revisar tus gastos? ¡Dime y yo te aviso! 🔔\n"
            
    keyboard = [
        [InlineKeyboardButton("➕ Nuevo Recordatorio", callback_data=ReminderActions.NEW.value)],
        [InlineKeyboardButton("📋 Gestionar Recordatorios", callback_data=ReminderActions.LIST.value)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Si viene de un callback (botón volver), editamos. Si es comando, enviamos nuevo.
    if update.callback_query:
        await update.callback_query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_reminder_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data
    
    # Fix for Enum string representation issue
    if data.startswith("ReminderActions."):
        # Extract the member name (e.g., QUICK_DATE) and map it to value
        try:
            parts = data.split("|")
            enum_str = parts[0] # ReminderActions.QUICK_DATE
            member_name = enum_str.split(".")[1] # QUICK_DATE
            # Get the actual value from the Enum
            real_value = getattr(ReminderActions, member_name).value
            # Reconstruct data with the correct value
            data = f"{real_value}|{'|'.join(parts[1:])}"
            logging.info(f"Fixed malformed callback data: {query.data} -> {data}")
        except Exception as e:
            logging.error(f"Failed to fix malformed callback data: {e}")
            return False

    # Verificar si es una acción de recordatorios
    if not data.startswith("REM_"):
        return False

    parts = data.split("|")
    action = parts[0]
    args = parts[1:]
    
    logging.info(f"REMINDER ACTION: {action}, ARGS: {args}")

    if action == ReminderActions.NEW:
        context.user_data['waiting_for_reminder_msg'] = True
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=ReminderActions.MENU.value)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="⏰ **Nuevo Recordatorio**\n\n¿Qué quieres que te recuerde? (Escribe el mensaje):", reply_markup=reply_markup, parse_mode='Markdown')
        
    elif action == ReminderActions.MENU:
        await reminders_menu(update, context)

    elif action == ReminderActions.DATE_MENU:
        rem_id = context.user_data.get('editing_reminder_id')
        await show_date_selection_menu(query, rem_id)

    elif action == ReminderActions.LIST:
        await list_reminders(query, update.effective_user.id)
        
    elif action == ReminderActions.VIEW:
        try:
            await view_reminder(query, int(args[0]))
        except Exception as e:
            await query.edit_message_text(text=f"❌ Error al abrir recordatorio: {str(e)}\nData: {data}")
        
    elif action == ReminderActions.EDIT_MENU:
        await show_edit_menu(query, int(args[0]))
        
    elif action == ReminderActions.EDIT_MSG:
        rem_id = int(args[0])
        context.user_data['waiting_for_rem_edit_msg'] = rem_id
        await query.edit_message_text(text="✏️ **Escribe el nuevo mensaje para el recordatorio:**", parse_mode='Markdown')
        
    elif action == ReminderActions.EDIT_DATE:
        rem_id = int(args[0])
        context.user_data['editing_reminder_id'] = rem_id
        await show_date_selection_menu(query, rem_id)
        
    elif action == ReminderActions.DELETE:
        await delete_reminder(query, int(args[0]))
        
    elif action == ReminderActions.QUICK_DATE:
        try:
            logging.info(f"Processing QUICK_DATE with args: {args}")
            await handle_quick_date(query, context, update.effective_user.id, args[0])
        except Exception as e:
            logging.error(f"ERROR in QUICK_DATE: {e}", exc_info=True)
            try:
                await query.edit_message_text(text=f"❌ Error en fecha rápida: {str(e)}")
            except:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error crítico en fecha rápida: {str(e)}")
        
    elif action == ReminderActions.CUSTOM_DATE_PICKER:
        try:
            await show_month_picker(query, context)
        except Exception as e:
            await query.edit_message_text(text=f"❌ Error en selector de fecha: {str(e)}")
        
    elif action == ReminderActions.PICK_MONTH:
        try:
            await show_day_picker(query, context, int(args[0]), int(args[1]))
        except Exception as e:
            await query.edit_message_text(text=f"❌ Error al elegir mes: {str(e)}")
        
    elif action == ReminderActions.PICK_DAY:
        try:
            await show_hour_picker(query, context, int(args[0]), int(args[1]), int(args[2]))
        except Exception as e:
            await query.edit_message_text(text=f"❌ Error al elegir día: {str(e)}")
        
    elif action == ReminderActions.PICK_HOUR:
        try:
            await show_minute_picker(query, context, int(args[0]), int(args[1]), int(args[2]), int(args[3]))
        except Exception as e:
            await query.edit_message_text(text=f"❌ Error al elegir hora: {str(e)}")
        
    elif action == ReminderActions.PICK_MIN:
        try:
            await finalize_reminder_date(query, context, update.effective_user.id, int(args[0]), int(args[1]), int(args[2]), int(args[3]), int(args[4]))
        except Exception as e:
            await query.edit_message_text(text=f"❌ Error al finalizar fecha: {str(e)}")
        
    elif action == ReminderActions.MANUAL_TIME:
        day, month, year = int(args[0]), int(args[1]), int(args[2])
        context.user_data['waiting_for_custom_rem_time_only'] = (day, month, year)
        await query.edit_message_text(text=f"⌨️ **Escribe la hora para el {day}/{month}/{year}:**\n\nFormato: HH:MM (ej: 14:35 o 09:05)", parse_mode='Markdown')

    else:
        # Catch-all para depuración
        await query.edit_message_text(text=f"⚠️ Acción desconocida: '{action}'\nData completa: {data}")

    return True

async def list_reminders(query, user_id):
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    reminders = repo.get_active_reminders_for_user(user_id)
    
    if not reminders:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=ReminderActions.MENU.value)]]
        await query.edit_message_text(text="📭 No tienes recordatorios pendientes.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for rem in reminders:
        # Mostrar fecha y primeros 20 chars del mensaje
        btn_text = f"{rem.remind_at.strftime('%d/%m %H:%M')} - {rem.message[:20]}..."
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"{ReminderActions.VIEW.value}|{rem.id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data=ReminderActions.MENU.value)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text="📋 **Tus Recordatorios Activos:**", reply_markup=reply_markup, parse_mode='Markdown')

# --- Helper Functions ---

async def view_reminder(query, rem_id):
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    rem = repo.get_reminder_by_id(rem_id)
    
    if not rem:
        await query.edit_message_text(text="❌ Ese recordatorio ya no existe.")
        return
        
    msg = f"⏰ **Detalle del Recordatorio**\n\n"
    # Limpiar mensaje de caracteres que rompen Markdown
    safe_msg = rem.message.replace("*", "").replace("_", "").replace("`", "").replace("[", "")
    msg += f"📝 **Mensaje:** {safe_msg}\n"
    msg += f"📅 **Fecha:** {rem.remind_at.strftime('%d-%m-%Y %H:%M')}\n"
    
    keyboard = [
        [InlineKeyboardButton("✏️ Editar", callback_data=f"{ReminderActions.EDIT_MENU.value}|{rem.id}")],
        [InlineKeyboardButton("🗑️ Eliminar", callback_data=f"{ReminderActions.DELETE.value}|{rem.id}")],
        [InlineKeyboardButton("🔙 Volver", callback_data=ReminderActions.LIST.value)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')

async def show_edit_menu(query, rem_id):
    keyboard = [
        [InlineKeyboardButton("📝 Editar Mensaje", callback_data=f"{ReminderActions.EDIT_MSG.value}|{rem_id}")],
        [InlineKeyboardButton("📅 Editar Fecha/Hora", callback_data=f"{ReminderActions.EDIT_DATE.value}|{rem_id}")],
        [InlineKeyboardButton("🔙 Volver", callback_data=f"{ReminderActions.VIEW.value}|{rem_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="¿Qué quieres modificar de este recordatorio?", reply_markup=reply_markup)

async def delete_reminder(query, rem_id):
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    repo.delete_reminder(rem_id)
    await query.edit_message_text(text="✅ Recordatorio eliminado.")

async def show_date_selection_menu(query, rem_id=None):
    # Si rem_id existe, es edición. Si no, es nuevo (pero el flujo nuevo guarda el msg en user_data y luego pide fecha)
    # El botón "Volver" depende del contexto.
    
    back_callback = f"{ReminderActions.VIEW.value}|{rem_id}" if rem_id else ReminderActions.MENU.value
    
    keyboard = [
        [InlineKeyboardButton("En 1 hora", callback_data=f"{ReminderActions.QUICK_DATE.value}|1h"), InlineKeyboardButton("En 3 horas", callback_data=f"{ReminderActions.QUICK_DATE.value}|3h")],
        [InlineKeyboardButton("Mañana 9:00", callback_data=f"{ReminderActions.QUICK_DATE.value}|tmrw_9"), InlineKeyboardButton("Mañana 20:00", callback_data=f"{ReminderActions.QUICK_DATE.value}|tmrw_20")],
        [InlineKeyboardButton("En 2 días", callback_data=f"{ReminderActions.QUICK_DATE.value}|2d")],
        [InlineKeyboardButton("📅 Elegir Fecha", callback_data=ReminderActions.CUSTOM_DATE_PICKER.value)],
    ]
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data=back_callback)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"📅 **Elige la fecha:**", 
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_quick_date(query, context, user_id, code):
    now = datetime.now()
    remind_at = None
    
    logging.info(f"Calculating date for code: {code}")

    if code == "1h": remind_at = now + timedelta(hours=1)
    elif code == "3h": remind_at = now + timedelta(hours=3)
    elif code == "tmrw_9": remind_at = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    elif code == "tmrw_20": remind_at = (now + timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
    elif code == "2d": remind_at = (now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
    
    if remind_at is None:
        logging.error(f"Invalid quick date code: {code}")
        await query.edit_message_text(text=f"❌ Código de fecha inválido: {code}")
        return

    logging.info(f"Date calculated: {remind_at}")
    await save_or_update_reminder(query, context, user_id, remind_at)

async def show_month_picker(query, context):
    now = datetime.now()
    next_month_date = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    
    months = [
        (now.strftime("%B"), now.month, now.year),
        (next_month_date.strftime("%B"), next_month_date.month, next_month_date.year)
    ]
    
    es_months = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
    
    keyboard = []
    for _, m, y in months:
        name = es_months.get(m, str(m))
        keyboard.append([InlineKeyboardButton(f"{name} {y}", callback_data=f"{ReminderActions.PICK_MONTH.value}|{m}|{y}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data=ReminderActions.DATE_MENU.value)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="📅 **Selecciona el Mes:**", reply_markup=reply_markup, parse_mode='Markdown')

async def show_day_picker(query, context, month, year):
    if month == 12: next_m = datetime(year + 1, 1, 1)
    else: next_m = datetime(year, month + 1, 1)
    last_day = (next_m - timedelta(days=1)).day
    
    keyboard = []
    row = []
    for d in range(1, last_day + 1):
        row.append(InlineKeyboardButton(str(d), callback_data=f"{ReminderActions.PICK_DAY.value}|{d}|{month}|{year}"))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data=ReminderActions.CUSTOM_DATE_PICKER.value)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=f"📅 **Selecciona el Día ({month}/{year}):**", reply_markup=reply_markup, parse_mode='Markdown')

async def show_hour_picker(query, context, day, month, year):
    hours = list(range(7, 24))
    keyboard = []
    row = []
    for h in hours:
        row.append(InlineKeyboardButton(f"{h}:00", callback_data=f"{ReminderActions.PICK_HOUR.value}|{h}|{day}|{month}|{year}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("✏️ Otra Hora (Manual)", callback_data=f"{ReminderActions.MANUAL_TIME.value}|{day}|{month}|{year}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data=f"{ReminderActions.PICK_MONTH.value}|{month}|{year}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=f"⏰ **Selecciona la Hora para el {day}/{month}:**", reply_markup=reply_markup, parse_mode='Markdown')

async def show_minute_picker(query, context, hour, day, month, year):
    minutes = [0, 15, 30, 45]
    keyboard = []
    row = []
    for m in minutes:
        row.append(InlineKeyboardButton(f"{hour}:{m:02d}", callback_data=f"{ReminderActions.PICK_MIN.value}|{m}|{hour}|{day}|{month}|{year}"))
    keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data=f"{ReminderActions.PICK_DAY.value}|{day}|{month}|{year}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=f"⏰ **Selecciona los Minutos:**", reply_markup=reply_markup, parse_mode='Markdown')

async def finalize_reminder_date(query, context, user_id, minute, hour, day, month, year):
    remind_at = datetime(year, month, day, hour, minute)
    if remind_at < datetime.now():
        await query.edit_message_text(text="❌ Esa fecha ya pasó. Intenta de nuevo.")
        return
    await save_or_update_reminder(query, context, user_id, remind_at)

async def save_or_update_reminder(query, context, user_id, remind_at):
    try:
        logging.info(f"Saving reminder for user {user_id} at {remind_at}")
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)

        editing_id = context.user_data.get('editing_reminder_id')
        if editing_id:
            logging.info(f"Updating existing reminder {editing_id}")
            repo.update_reminder(editing_id, remind_at=remind_at)
            context.user_data.pop('editing_reminder_id')
            await query.edit_message_text(
                text=f"✅ ¡Fecha Actualizada! 🔔\n\nNueva Fecha: {remind_at.strftime('%d-%m-%Y %H:%M')}",
                parse_mode='Markdown'
            )
            return

        msg = context.user_data.get('temp_rem_msg')
        logging.info(f"New reminder message: {msg}")
        
        if not msg:
            logging.warning("Message not found in user_data")
            await query.edit_message_text(text="❌ Ups, perdí el mensaje. Intenta de nuevo.")
            return

        repo.add_reminder(user_id, msg, remind_at)
        logging.info("Reminder saved to DB")
        
        if 'waiting_for_reminder_date' in context.user_data:
            context.user_data.pop('waiting_for_reminder_date')
        
        # Sanitize msg for Markdown
        safe_msg = msg.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
        
        try:
            await query.edit_message_text(
                text=f"✅ ¡Recordatorio Guardado! 🔔\n\n**{safe_msg}**\nFecha: {remind_at.strftime('%d-%m-%Y %H:%M')}",
                parse_mode='Markdown'
            )
        except Exception as edit_error:
            logging.error(f"Error editing message: {edit_error}")
            # Fallback if edit fails
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ ¡Recordatorio Guardado! 🔔\n\n**{safe_msg}**\nFecha: {remind_at.strftime('%d-%m-%Y %H:%M')}",
                parse_mode='Markdown'
            )

    except Exception as e:
        logging.error(f"ERROR in save_or_update_reminder: {e}", exc_info=True)
        try:
            await query.edit_message_text(text=f"❌ Error al guardar: {str(e)}")
        except:
            await context.bot.send_message(chat_id=user_id, text=f"❌ Error al guardar: {str(e)}")
