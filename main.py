import logging
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import config
from game_engine import CityGameEngine
from llm_manager import LLMManager
from bot_handler import TelegramBotHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Запуск упрощенного бота"""
    
    # Проверка токенов
    if not config.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не найден в .env")
        return
    
    logger.info("Запуск упрощенного бота для игры в города...")
    
    try:
        # Инициализация компонентов
        game_engine = CityGameEngine()
        llm_manager = LLMManager()
        bot_handler = TelegramBotHandler(game_engine, llm_manager)
        
        # Создание приложения Telegram
        app = Application.builder().token(config.TELEGRAM_TOKEN).build()
        
        # Регистрация обработчиков
        app.add_handler(CommandHandler("start", bot_handler.start_command))
        app.add_handler(CommandHandler("help", bot_handler.help_command))
        app.add_handler(CommandHandler("end", bot_handler.end_command))
        
        # Только текстовые сообщения
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.handle_text_message))
        
        # Кнопки
        app.add_handler(CallbackQueryHandler(bot_handler.handle_callback_query))
        
        # Обработчик ошибок
        app.add_error_handler(bot_handler.error_handler)
        
        logger.info("Бот запущен! Отправьте /start чтобы начать игру")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    main()