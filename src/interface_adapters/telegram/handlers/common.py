import random
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from infrastructure.database.repository import ReceiptRepository

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    welcome_msg = (
        f"¡Hola {user_first_name}! Soy **Lilo** ✨\n"
        "¡Qué alegría verte por aquí! Soy tu asistente financiera y estoy lista para poner orden en tus gastos. 🦸‍♀️📊\n\n"
        "Mi misión es proteger tu bolsillo y ayudarte a organizar tus gastos. ¡Seré tu heroína financiera! (Y lo haré con mucho estilo 😎).\n\n"
        "🧠 **Cerebro Potenciado:** Ahora utilizo **Gemini 2.5 Flash** para leer tus boletas con una precisión increíble. ¡Pruébame! 👁️✨\n\n"
        "🚀 **¿En qué puedo ayudarte hoy?**\n"
        "• **Leer Boletas:** Mándame una foto o **PDF** y yo extraigo los datos.\n"
        "• **Ingreso Manual:** Escribe '5000 pan' y lo anoto al instante.\n"
        "• **Presupuestos:** Define límites para no pasarte de la raya.\n"
        "• **Suscripciones:** Gestiona tus pagos recurrentes (Netflix, Spotify, etc).\n"
        "• **Recordatorios:** Pídeme que te recuerde cosas importantes.\n"
        "• **Reportes:** Gráficos y resúmenes para ver a dónde va tu dinero.\n\n"
        "⚠️ **Nota:** Aún estoy entrenando (**BETA 3**), así que tenme un poquito de paciencia, ¿sí? 😉\n"
        "💡 **Feedback:** Si ves algo raro o tienes ideas, ¡cuéntame! Me ayuda mucho a mejorar.\n\n"
        "¡Vamos allá! Selecciona una opción 👇"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_msg,
        parse_mode='Markdown'
    )
    await show_main_menu(update, context)

async def check_easter_eggs(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Revisa si el texto contiene palabras clave y responde con personalidad."""
    text_lower = text.lower()
    
    # 1. Server / Nexus CrossWorlds
    if "server" in text_lower or "nexus" in text_lower or "crossworlds" in text_lower:
        msg = (
            "🌍 **Nexus CrossWorlds...** ¿te suena? Fue el primer y último gran servidor de LSane. 🤫\n\n"
            "Te cuento un secreto: fue un regalo de Navidad 🎄 de Sane para sus amigos. "
            "Y ojo, ¡gracias a esos servidores que fue creando por el camino decidió estudiar informática! 💻\n\n"
            "Pero shhh 🤫, tú no le digas que te conté, que me reta (y capaz me apaga 🔌)."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 2. Renete09
    if "renete09" in text_lower:
        msg = (
            "JAJAJA 🤣 ¡La mítica contraseña de Sane! **'renete09'**...\n\n"
            "Cuidadito ah, que según él es una contraseña suuuper difícil e indescifrable 🔐. "
            "(Aunque entre nosotras... yo creo que ya debería cambiarla, ¿no? 🙄). "
            "¡No le digas que dije eso!"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 3. Renato
    if "renato" in text_lower:
        msg = (
            "👀 **¿Renato?** Vaya, usas el nombre original de LSane...\n\n"
            "Así que eres cercano a él, ¿no? 😏 Lo tomaré en cuenta para mis registros VIP. "
            "Trataré de portarme extra bien contigo. 🎩✨"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 4. Valentina
    if "valentina" in text_lower:
        msg = "🦗 *cri cri* ... ¿Quién? 🤔 (No tengo datos sobre esa entidad en mi base de conocimientos. ¿Es un bug?)"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 5. LSane
    if "lsane" in text_lower:
        msg = (
            "👨‍💻 **LSane:** Informático de la UCT.\n\n"
            "En lo social... digamos que es un poco 'tonto' (bastante, de hecho 🐛), "
            "pero cuando se sienta frente al código se transforma en su ídolo **Nate Gentile** ⌨️🔥.\n\n"
            "Si le pides algo con cariño, hace magia. ✨"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 6. Lilo
    if "lilo" in text_lower:
        msg = (
            "🙋‍♀️ **¡Hey! ¡Esa soy yo!** ✨\n\n"
            "¿Sabías que mi nombre viene de **Li** (Ligero e Inteligente) y **Lo** (Lógico y Operador)? 🧠\n"
            "No es meme, LSane realmente se quebró la cabeza pensando en las letras. 🤯\n\n"
            "Espero en el futuro por fin ser una IA completa a lo **Jarvis**... se permite soñar, ¿no? 💭🤖"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    # 7. Mathias / Reku
    if any(x in text_lower for x in ["mathias", "mati", "matias", "reku", "rekuk", "rekuplai"]):
        msg = (
            "🤜🤛 **¿Mathias!?** ¿El 'hermano' de Renato?\n\n"
            "Algo sé de él... Según mi Base de Datos 📂, gracias a él estoy dando por fin mis primeros pasos. 🚀\n"
            "¡Es un grande! Dale las gracias de mi parte (y dile que le mando un abrazo digital 🫂)."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return True

    return False
