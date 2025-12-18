import os
import uuid
import hashlib
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from infrastructure.ocr.ocr_service import OCRService
from infrastructure.database.repository import ReceiptRepository
from infrastructure.database.db_config import get_db
from interface_adapters.telegram.handlers.common import get_random_phrase, get_random_error_message, generate_lilo_insight
from interface_adapters.telegram.handlers.budgets import check_budget_alert

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

ocr_service = OCRService()

def calculate_file_hash(file_path: str) -> str:
    """Calcula el hash SHA256 de un archivo."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

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
            await check_budget_alert(update, context, predicted_category)
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
        f"```\n{safe_text}...\n```"
    )
    
    keyboard = []
    
    # Si ya tiene categoría, mostrar botón para cambiarla
    if receipt.category:
        keyboard.append([InlineKeyboardButton("📂 Cambiar Categoría", callback_data=f"change_cat_{receipt.id}")])
    else:
        # Si no tiene categoría, mostrar opciones
        keyboard = [
            [InlineKeyboardButton("🍔 Comida", callback_data=f"cat_{receipt.id}_Comida"), InlineKeyboardButton("🛒 Supermercado", callback_data=f"cat_{receipt.id}_Supermercado")],
            [InlineKeyboardButton("🚌 Transporte", callback_data=f"cat_{receipt.id}_Transporte"), InlineKeyboardButton("🎉 Ocio", callback_data=f"cat_{receipt.id}_Ocio")],
            [InlineKeyboardButton("🏠 Hogar", callback_data=f"cat_{receipt.id}_Hogar"), InlineKeyboardButton("💊 Salud", callback_data=f"cat_{receipt.id}_Salud")],
            [InlineKeyboardButton("📦 Otros", callback_data=f"cat_{receipt.id}_Otros")]
        ]

    # Botones de edición siempre presentes
    keyboard.append([InlineKeyboardButton("✏️ Corregir Marca", callback_data=f"edit_merchant_{receipt.id}"), InlineKeyboardButton("💲 Corregir Monto", callback_data=f"edit_amount_{receipt.id}")])
    
    # Botones de confirmación y cancelación
    keyboard.append([InlineKeyboardButton("✅ Confirmar", callback_data=f"confirm_receipt_{receipt.id}"), InlineKeyboardButton("🗑️ Cancelar", callback_data=f"cancel_receipt_{receipt.id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text=response_msg, reply_markup=reply_markup, parse_mode='Markdown')

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

async def handle_expense_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Maneja los callbacks relacionados con gastos (categoría, edición)."""
    query = update.callback_query
    data = query.data
    
    if data.startswith("edit_merchant_"):
        receipt_id = int(data.split("_")[2])
        # Guardar estado para esperar el nombre
        context.user_data['waiting_for_merchant'] = receipt_id
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"back_to_options_{receipt_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text="✏️ **Por favor, escribe el nombre de la marca/comercio:**", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data.startswith("edit_amount_"):
        receipt_id = int(data.split("_")[2])
        # Guardar estado para esperar el monto
        context.user_data['waiting_for_amount'] = receipt_id
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"back_to_options_{receipt_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text="💲 **Por favor, escribe el monto total correcto (solo números):**", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data.startswith("confirm_receipt_"):
        receipt_id = int(data.split("_")[2])
        await query.edit_message_text(text="✅ **¡Boleta confirmada!** Todo listo. 🚀", parse_mode='Markdown')
        return True

    if data.startswith("cancel_receipt_"):
        receipt_id = int(data.split("_")[2])
        
        db_gen = get_db()
        db = next(db_gen)
        repo = ReceiptRepository(db)
        repo.delete_receipt(receipt_id)
        
        await query.edit_message_text(text="🗑️ **Boleta eliminada.** No se guardó nada.", parse_mode='Markdown')
        return True

    if data.startswith("change_cat_"):
        receipt_id = int(data.split("_")[2])
        
        keyboard = [
            [InlineKeyboardButton("🍔 Comida", callback_data=f"cat_{receipt_id}_Comida"), InlineKeyboardButton("🛒 Supermercado", callback_data=f"cat_{receipt_id}_Supermercado")],
            [InlineKeyboardButton("🚌 Transporte", callback_data=f"cat_{receipt_id}_Transporte"), InlineKeyboardButton("🎉 Ocio", callback_data=f"cat_{receipt_id}_Ocio")],
            [InlineKeyboardButton("🏠 Hogar", callback_data=f"cat_{receipt_id}_Hogar"), InlineKeyboardButton("💊 Salud", callback_data=f"cat_{receipt_id}_Salud")],
            [InlineKeyboardButton("📦 Otros", callback_data=f"cat_{receipt_id}_Otros")],
            [InlineKeyboardButton("🔙 Volver", callback_data=f"back_to_options_{receipt_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="📂 **Selecciona la nueva categoría:**", reply_markup=reply_markup, parse_mode='Markdown')
        return True

    if data == "cancel_manual_entry":
        await query.edit_message_text(text="❌ Operación cancelada. Si necesitas algo más, aquí estoy. 🤖")
        return True

    if data.startswith("back_to_options_"):
        receipt_id = int(data.split("_")[3])
        
        # Limpiar estados de espera por si acaso
        context.user_data.pop('waiting_for_merchant', None)
        context.user_data.pop('waiting_for_amount', None)
        
        await query.delete_message()
        await show_receipt_options(update, context, receipt_id)
        return True

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
        
        # Verificar presupuesto
        await check_budget_alert(update, context, category)
        
        await query.edit_message_text(
            text=f"✅ ¡Listo! Guardado en **{category}**.\n\n💡 **Dato curioso:** {insight}", 
            parse_mode='Markdown'
        )
        
        # Volver a mostrar las opciones por si quiere editar algo más
        await show_receipt_options(update, context, receipt_id)
        return True
        
    return False
