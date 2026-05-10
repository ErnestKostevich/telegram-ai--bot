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

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not user.get("vip"):
        await update.message.reply_text("💎 <b>Генерация изображений доступна только для VIP!</b>", parse_mode="HTML")
        return
        
    if not context.args:
        await update.message.reply_text("🎨 Использование: /generate [описание изображения]")
        return
        
    prompt = " ".join(context.args)
    provider = user.get("ai_provider", "openai")
    keys = user.get("api_keys", {})
    key = keys.get(provider)
    
    if not key:
        await update.message.reply_text(f"❌ Ключ для {provider} не найден. Используйте /setkey")
        return
        
    msg = await update.message.reply_text("🎨 Рисую изображение... Это может занять секунд 10-20.")
    
    # Simple mockup implementation for BYOK generation (using OpenAI DALL-E 3 format as a generic fallback)
    # In a fully fleshed out BYOK, we'd route based on provider.
    import aiohttp
    url = "https://api.openai.com/v1/images/generations"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024"}
    
    try:
        if provider == "together":
            url = "https://api.together.xyz/v1/images/generations"
            payload = {"model": "stabilityai/stable-diffusion-xl-base-1.0", "prompt": prompt, "n": 1, "steps": 20}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    await msg.edit_text(f"❌ Ошибка провайдера: {data['error']['message']}")
                    return
                if "data" in data and len(data["data"]) > 0:
                    image_url = data["data"][0]["url"]
                    await update.message.reply_photo(photo=image_url, caption=f"🎨 {prompt}")
                    await msg.delete()
                else:
                    await msg.edit_text("❌ Не удалось получить изображение от провайдера.")
    except Exception as e:
        await msg.edit_text(f"❌ Системная ошибка: {str(e)}")
