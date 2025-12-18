import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from infrastructure.database.repository import ReceiptRepository
from infrastructure.database.db_config import get_db

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
                    msg += f"   ⚠️ _¡Te pasaste por ${spent-limit:,.0f}!_\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Nuevo Presupuesto", callback_data="new_budget")],
        [InlineKeyboardButton("🔄 Actualizar", callback_data="refresh_budgets")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_budget_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Maneja los callbacks relacionados con presupuestos."""
    query = update.callback_query
    data = query.data
    
    if data == "new_budget":
        # Preguntar categoría para presupuesto
        keyboard = [
            [InlineKeyboardButton("🍔 Comida", callback_data="set_budget_Comida"), InlineKeyboardButton("🛒 Supermercado", callback_data="set_budget_Supermercado")],
            [InlineKeyboardButton("🚌 Transporte", callback_data="set_budget_Transporte"), InlineKeyboardButton("🎉 Ocio", callback_data="set_budget_Ocio")],
            [InlineKeyboardButton("🏠 Hogar", callback_data="set_budget_Hogar"), InlineKeyboardButton("📦 Otros", callback_data="set_budget_Otros")],
            [InlineKeyboardButton("🔙 Volver", callback_data="refresh_budgets")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="💰 **Elige la categoría para el presupuesto:**", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data.startswith("set_budget_"):
        category = data.split("_")[2]
        context.user_data['waiting_for_budget_cat'] = category
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="refresh_budgets")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text=f"💰 **Presupuesto para {category}:**\n\nEscribe el monto límite (ej: 150000):", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data == "refresh_budgets":
        try:
            await budgets_menu(update, context)
        except Exception as e:
            if "Message is not modified" in str(e):
                pass
            else:
                raise e
        return True
        
    return False

async def handle_budget_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Maneja la entrada de texto para definir el monto del presupuesto."""
    if not context.user_data.get('waiting_for_budget_cat'):
        return False
        
    category = context.user_data.pop('waiting_for_budget_cat')
    text = update.message.text
    
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
        return True
    except ValueError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Eso no es un número válido. Intenta de nuevo.")
        # Restaurar estado para que intente de nuevo
        context.user_data['waiting_for_budget_cat'] = category
        return True

async def check_budget_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Verifica si se ha excedido el presupuesto y envía una alerta."""
    user_id = update.effective_user.id
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    db_gen = get_db()
    db = next(db_gen)
    repo = ReceiptRepository(db)
    
    status = repo.get_budget_status(user_id, category, current_month, current_year)
    if not status:
        return
        
    spent, limit, pct = status
    
    if pct >= 100:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🚨 **¡ALERTA DE PRESUPUESTO!** 🚨\n\nHas gastado **${spent:,.0f}** en {category}, superando tu límite de ${limit:,.0f}.\n(Exceso: ${spent-limit:,.0f}) 💸",
            parse_mode='Markdown'
        )
    elif pct >= 80:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ **¡Cuidado!** Llevas el **{pct:.1f}%** de tu presupuesto de {category}.\n(${spent:,.0f} / ${limit:,.0f})",
            parse_mode='Markdown'
        )
