from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from infrastructure.database.repository import ReceiptRepository
from infrastructure.database.db_config import get_db_session
from infrastructure.utils.charts import generate_pie_chart, generate_bar_chart, generate_monthly_trend_chart
from infrastructure.utils.excel_exporter import generate_excel_report

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
    
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_date_selection")])
    
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
    
    keyboard.append([InlineKeyboardButton("🔙 Volver al Año", callback_data="back_to_year_selection")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📅 **Año {year} seleccionado.**\nAhora selecciona el **Mes**:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def gastos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Obtener fecha seleccionada o usar actual
    selected_year = context.user_data.get('report_year', datetime.now().year)
    selected_month = context.user_data.get('report_month', datetime.now().month)
    
    month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    period_name = f"{month_names[selected_month]} {selected_year}"

    with get_db_session() as db:
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
    
    with get_db_session() as db:
        repo = ReceiptRepository(db)
        total = repo.get_yearly_total(user_id, year=selected_year)
        breakdown = repo.get_yearly_expenses_breakdown(user_id, year=selected_year)
    
    # Construir mensaje de texto
    msg = f"📅 **Gran Resumen Anual {selected_year}** 🌟\n\n"
    msg += f"¡Wow! En todo el año has gastado: **${total:,.0f}** 💰\n\n"
    msg += "**📉 Así se ve mes a mes:**\n"
    
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
    
    with get_db_session() as db:
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
    
    with get_db_session() as db:
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
    
    with get_db_session() as db:
        repo = ReceiptRepository(db)
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
    with get_db_session() as db:
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

async def handle_report_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Maneja los callbacks relacionados con reportes (cambio de fecha)."""
    query = update.callback_query
    data = query.data
    
    if data.startswith("set_year_"):
        year = int(data.split("_")[2])
        await ask_month_selection(update, context, year)
        return True

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
        return True

    if data == "cancel_date_selection":
        await query.edit_message_text(text="❌ Selección de fecha cancelada.")
        return True

    if data == "back_to_year_selection":
        await ask_year_selection(update, context)
        return True
        
    return False
