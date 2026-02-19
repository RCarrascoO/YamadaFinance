import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from infrastructure.database.repository import ReceiptRepository
from infrastructure.database.db_config import get_db_session

async def subscriptions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de suscripciones."""
    user_id = update.effective_user.id
    
    with get_db_session() as db:
        repo = ReceiptRepository(db)
        subs = repo.get_subscriptions(user_id)
    
    msg = "🔄 **Tus Suscripciones Activas**\n\n"
    if not subs:
        msg += "No tienes suscripciones. ¿Netflix? ¿Spotify? ¡Agrégalos! 👇"
    else:
        month_names = ["", "Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
        for s in subs:
            interval_icon = "📅" if (s.interval == "mensual" or not s.interval) else "📆"
            if s.interval == "anual" and s.month_of_year:
                freq = f"{month_names[s.month_of_year]}/año, día {s.day_of_month}"
            else:
                freq = f"Día {s.day_of_month}/mes"
            msg += f"• {interval_icon} **{s.name}**: ${s.amount:,.0f} ({freq})\n"
            
    keyboard = [
        [InlineKeyboardButton("➕ Nueva Suscripción", callback_data="new_sub")],
        [InlineKeyboardButton("✏️/🗑️ Gestionar", callback_data="manage_subs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_subscription_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Maneja los callbacks relacionados con suscripciones."""
    query = update.callback_query
    data = query.data
    
    if data == "new_sub":
        context.user_data['waiting_for_sub_name'] = True
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="refresh_subs")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text="🔄 **Nueva Suscripción**\n\nPrimero, escribe el **Nombre** del servicio (ej: Netflix):", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data == "manage_subs":
        # Listar para gestionar (editar o borrar)
        user_id = update.effective_user.id
        with get_db_session() as db:
            repo = ReceiptRepository(db)
            subs = repo.get_subscriptions(user_id)
        
        if not subs:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="refresh_subs")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text="No tienes suscripciones para gestionar. 🤷‍♀️", reply_markup=reply_markup)
            return True
            
        keyboard = []
        for s in subs:
            keyboard.append([InlineKeyboardButton(f"{s.name} (${s.amount:,.0f})", callback_data=f"sel_sub_{s.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="refresh_subs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="🔧 **Selecciona una suscripción para editar o borrar:**", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data.startswith("sel_sub_"):
        sub_id = int(data.split("_")[2])
        keyboard = [
            [InlineKeyboardButton("✏️ Editar Monto", callback_data=f"edit_sub_amount_{sub_id}")],
            [InlineKeyboardButton("📅 Editar Día", callback_data=f"edit_sub_day_{sub_id}")],
            [InlineKeyboardButton("🗑️ Eliminar", callback_data=f"confirm_del_sub_{sub_id}")],
            [InlineKeyboardButton("🔙 Volver", callback_data="manage_subs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="¿Qué quieres hacer con esta suscripción?", reply_markup=reply_markup)
        return True

    if data.startswith("edit_sub_amount_"):
        sub_id = int(data.split("_")[3])
        context.user_data['waiting_for_edit_sub_amount'] = sub_id
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"sel_sub_{sub_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text="✏️ **Escribe el nuevo monto mensual (ej: 12990):**", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data.startswith("edit_sub_day_"):
        sub_id = int(data.split("_")[3])
        context.user_data['waiting_for_edit_sub_day'] = sub_id
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"sel_sub_{sub_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text="📅 **Escribe el nuevo día de pago (1-31):**", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data == "del_sub":
        # Listar para borrar
        user_id = update.effective_user.id
        with get_db_session() as db:
            repo = ReceiptRepository(db)
            subs = repo.get_subscriptions(user_id)
        
        if not subs:
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="refresh_subs")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text="No tienes nada que borrar. 🤷‍♀️", reply_markup=reply_markup)
            return True
            
        keyboard = []
        for s in subs:
            keyboard.append([InlineKeyboardButton(f"❌ {s.name}", callback_data=f"confirm_del_sub_{s.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data="refresh_subs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="🗑️ **¿Cuál quieres eliminar?**", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data.startswith("confirm_del_sub_"):
        sub_id = int(data.split("_")[3])
        with get_db_session() as db:
            repo = ReceiptRepository(db)
            repo.delete_subscription(sub_id)
        
        # Volver al menú
        await subscriptions_menu(update, context)
        return True

    if data == "refresh_subs":
        try:
            await subscriptions_menu(update, context)
        except Exception as e:
            if "Message is not modified" in str(e):
                pass # Ignorar si no hay cambios
            else:
                raise e
        return True

    if data == "sub_interval_mensual":
        context.user_data['temp_sub_interval'] = "mensual"
        context.user_data['waiting_for_sub_day'] = True
        await query.edit_message_text(
            text="📅 **Mensual**\n\n¿Qué día del mes se paga? (ej: 5):",
            parse_mode='Markdown'
        )
        return True

    if data == "sub_interval_anual":
        context.user_data['temp_sub_interval'] = "anual"
        month_names = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
        keyboard = []
        row = []
        for i, name in enumerate(month_names):
            row.append(InlineKeyboardButton(name, callback_data=f"sub_anual_month_{i+1}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="📆 **Anual**\n\n¿En qué mes se cobra?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return True

    if data.startswith("sub_anual_month_"):
        month_num = int(data.split("_")[3])
        month_names = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        context.user_data['temp_sub_month'] = month_num
        context.user_data['waiting_for_sub_day'] = True
        await query.edit_message_text(
            text=f"📆 Mes: **{month_names[month_num]}**\n\n¿Qué día de ese mes se paga? (ej: 15):",
            parse_mode='Markdown'
        )
        return True

    return False

async def handle_subscription_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Maneja la entrada de texto para crear o editar suscripciones."""
    text = update.message.text
    chat_id = update.effective_chat.id

    # --- Edición de Monto ---
    if context.user_data.get('waiting_for_edit_sub_amount'):
        sub_id = context.user_data.pop('waiting_for_edit_sub_amount')
        try:
            clean_text = text.replace('$', '').replace('.', '').replace(',', '').strip()
            amount = float(clean_text)
            
            with get_db_session() as db:
                repo = ReceiptRepository(db)
                repo.update_subscription(sub_id, amount=amount)
            
            await context.bot.send_message(chat_id=chat_id, text=f"✅ Monto actualizado a **${amount:,.0f}**.", parse_mode='Markdown')
            await subscriptions_menu(update, context)
        except ValueError:
            await context.bot.send_message(chat_id=chat_id, text="❌ Número inválido. Intenta de nuevo.")
            context.user_data['waiting_for_edit_sub_amount'] = sub_id
        return True

    # --- Edición de Día ---
    if context.user_data.get('waiting_for_edit_sub_day'):
        sub_id = context.user_data.pop('waiting_for_edit_sub_day')
        try:
            day = int(text.strip())
            if day < 1 or day > 31: raise ValueError
            
            with get_db_session() as db:
                repo = ReceiptRepository(db)
                repo.update_subscription(sub_id, day=day)
            
            await context.bot.send_message(chat_id=chat_id, text=f"✅ Día de pago actualizado al **{day}** de cada mes.", parse_mode='Markdown')
            await subscriptions_menu(update, context)
        except ValueError:
            await context.bot.send_message(chat_id=chat_id, text="❌ Día inválido (1-31). Intenta de nuevo.")
            context.user_data['waiting_for_edit_sub_day'] = sub_id
        return True

    # Paso 1: Nombre
    if context.user_data.get('waiting_for_sub_name'):
        context.user_data.pop('waiting_for_sub_name')
        context.user_data['temp_sub_name'] = text.strip()
        context.user_data['waiting_for_sub_amount'] = True
        await context.bot.send_message(chat_id=chat_id, text=f"📝 Nombre: **{text.strip()}**\n\nAhora, ¿cuánto cuesta mensualmente? (ej: 5990)", parse_mode='Markdown')
        return True

    # Paso 2: Monto
    if context.user_data.get('waiting_for_sub_amount'):
        context.user_data.pop('waiting_for_sub_amount')
        try:
            clean_text = text.replace('$', '').replace('.', '').replace(',', '').strip()
            amount = float(clean_text)
            context.user_data['temp_sub_amount'] = amount
            keyboard = [
                [InlineKeyboardButton("📅 Mensual", callback_data="sub_interval_mensual"),
                 InlineKeyboardButton("📆 Anual", callback_data="sub_interval_anual")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"💰 Monto: **${amount:,.0f}**\n\n¿Con qué frecuencia se cobra?",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except ValueError:
            await context.bot.send_message(chat_id=chat_id, text="❌ Número inválido. Intenta de nuevo.")
            context.user_data['waiting_for_sub_amount'] = True
        return True

    # Paso 3: Día
    if context.user_data.get('waiting_for_sub_day'):
        context.user_data.pop('waiting_for_sub_day')
        try:
            day = int(text.strip())
            if day < 1 or day > 31: raise ValueError
            
            name = context.user_data.get('temp_sub_name')
            amount = context.user_data.get('temp_sub_amount')
            interval = context.user_data.pop('temp_sub_interval', 'mensual')
            month_of_year = context.user_data.pop('temp_sub_month', None)
            user_id = update.effective_user.id
            
            with get_db_session() as db:
                repo = ReceiptRepository(db)
                repo.add_subscription(user_id, name, amount, day, interval, month_of_year)
            
            month_names = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
            if interval == "anual" and month_of_year:
                freq_msg = f"Cada año en **{month_names[month_of_year]}**, día {day}"
            else:
                freq_msg = f"Todos los meses, día {day}"
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ ¡Suscripción Guardada! 🎉\n\n**{name}** - ${amount:,.0f}\n📅 {freq_msg}\nTe recordaré cuando llegue el día.",
                parse_mode='Markdown'
            )
            await subscriptions_menu(update, context)
        except ValueError:
            await context.bot.send_message(chat_id=chat_id, text="❌ Día inválido (1-31). Intenta de nuevo.")
            # Mantener estado
            context.user_data['waiting_for_sub_day'] = True
        return True
        
    return False
