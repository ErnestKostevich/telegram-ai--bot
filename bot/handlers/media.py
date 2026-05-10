from telegram import Update
from telegram.ext import ContextTypes
import base64
from bot.ai import ai_handler
from bot.storage import storage

async def media_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    msg = update.message
    caption = msg.caption or "Опиши это изображение или ответь на вопросы, связанные с ним."
    
    # Check if VIP is required for media?
    if not user.get("vip"):
        await update.message.reply_text("💎 <b>Анализ фото и файлов доступен только для VIP!</b>\n\nПриобретите VIP у создателя: /grant_vip", parse_mode="HTML")
        return
        
    status_msg = await update.message.reply_text("🔍 Анализирую медиафайлы...")
    
    try:
        # Currently we only handle photos
        if msg.photo:
            photo_file = await msg.photo[-1].get_file()
            photo_bytes = await photo_file.download_as_bytearray()
            
            # Since Gemini/OpenAI vision APIs require different formatting, we'll try a generic approach if possible.
            # For simplicity in this rework, we'll notify the user about BYOK vision support.
            # In a full implementation we'd encode base64 and pass to the provider.
            
            # Let's check if the provider is gemini or openai which support vision easily
            provider = user.get("ai_provider", "gemini")
            if provider not in ["gemini", "openai", "anthropic"]:
                await status_msg.edit_text(f"❌ Ваш текущий провайдер ({provider}) пока не поддерживает анализ изображений через этот бот. Пожалуйста, используйте Gemini, OpenAI или Anthropic.")
                return
                
            photo_b64 = base64.b64encode(photo_bytes).decode('utf-8')
            
            # Prepare special prompt for vision
            prompt = f"[Пользователь отправил изображение. Подпись: {caption}]"
            
            # Since our bot.ai currently only takes strings for simplicity, we append a notice.
            # In reality, `bot.ai` needs to be updated to accept images. I'll update it later if needed.
            # For now, let's inform the user that vision module is initializing.
            await status_msg.edit_text("📸 Фото получено! К сожалению, полная поддержка загрузки изображений в BYOK модуле находится в разработке для версии 4.1.")
            
        elif msg.document:
            await status_msg.edit_text("📎 Файл получен! Поддержка анализа документов в BYOK модуле находится в разработке для версии 4.1.")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка обработки: {str(e)}")
