import logging
from typing import Optional, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from game_engine import CityGameEngine
from llm_manager import LLMManager
from config import config

logger = logging.getLogger(__name__)

class TelegramBotHandler:
    """Упрощенный обработчик бота (только текст)"""
    
    def __init__(self, game_engine: CityGameEngine, llm_manager: LLMManager):
        self.game_engine = game_engine
        self.llm_manager = llm_manager
        # LLM, выбранная пользователем: user_id -> provider ("gigachat" | "openai")
        self.user_llm: Dict[int, str] = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало игры"""
        user_id = update.effective_user.id
        
        providers = self.llm_manager.available_providers()
        # Если доступен только один провайдер — сразу стартуем игру с ним
        if len(providers) <= 1:
            if providers:
                # единственный доступный
                only_provider = next(iter(providers.keys()))
                self.user_llm[user_id] = only_provider
            message = self.game_engine.start_game(user_id)
            await update.message.reply_text(message)
            return

        # Если провайдеров несколько — предлагаем выбрать
        keyboard = [
            [
                InlineKeyboardButton("🤖 GigaChat", callback_data="llm_gigachat"),
                InlineKeyboardButton("🧠 OpenAI", callback_data="llm_openai"),
            ]
        ]
        await update.message.reply_text(
            "Выбери, какой LLM использовать в этой игре:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Помощь по игре"""
        help_text = (
            "*Игра в города*\n\n"
            "1. Называем города России по очереди\n"
            "2. Следующий город начинается на последнюю букву предыдущего\n"
            "3. Буквы Ь, Ы, Ъ, Й, Ё пропускаем\n"
            "4. Города не должны повторяться\n\n"
            "*Команды:*\n"
            "/start - начать игру\n"
            "/help - эта справка\n"
            "/end - закончить игру"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def end_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершение игры"""
        user_id = update.effective_user.id
        message = self.game_engine.end_game(user_id)
        await update.message.reply_text(message)
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений с городами"""
        user_id = update.effective_user.id
        city_name = update.message.text.strip()
        
        # Проверяем активную игру
        game_state = self.game_engine.get_game_state(user_id)
        if not game_state:
            await update.message.reply_text("Игра не начата. Отправьте /start")
            return
        
        # Проверяем ход игрока
        if not game_state.player_turn:
            await update.message.reply_text("Сейчас ход бота! Подождите...")
            return
        
        # Валидация города
        is_valid, error = self.game_engine.validate_city_name(city_name)
        if not is_valid:
            await update.message.reply_text(f"{error}")
            return

        # Проверка существования города через выбранный LLM
        provider = self.user_llm.get(user_id, config.LLM_DEFAULT_PROVIDER)
        client = self.llm_manager.get_client(provider)
        if client and hasattr(client, "is_real_russian_city"):
            try:
                if not client.is_real_russian_city(city_name):
                    await update.message.reply_text(
                        f"Города *{city_name}* не существует в России (по данным модели). "
                        f"Попробуйте другой город.",
                        parse_mode="Markdown",
                    )
                    return
            except Exception as e:
                logger.error(f"Ошибка при проверке существования города '{city_name}': {e}")
        
        # Проверка правил игры
        is_valid_rule, rule_error = self.game_engine.check_city_rules(
            user_id, city_name, game_state.last_city
        )
        if not is_valid_rule:
            await update.message.reply_text(f"{rule_error}")
            return
        
        # Добавляем город игрока
        game_state.used_cities.add(city_name.strip().lower())
        game_state.last_city = city_name
        last_letter = self.game_engine.get_last_letter(city_name)
        
        if not last_letter:
            await update.message.reply_text("Не удалось определить букву")
            game_state.player_turn = True
            return
        
        # Сообщаем о принятии города
        await update.message.reply_text(
            f"Принято: {city_name}\n"
            f"Боту на букву *'{last_letter.upper()}'*\n"
            f"Бот думает...",
            parse_mode='Markdown'
        )
        
        # Ход бота
        await self._process_bot_turn(update, context, user_id, city_name, last_letter)
    
    async def _process_bot_turn(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               user_id: int, user_city: str, last_letter: str):
        """Обработка хода бота"""
        # Формируем промпт для LLM
        used_cities_prompt = self.game_engine.get_available_cities_prompt(user_id, last_letter)
        
        # Выбираем LLM для этого пользователя
        provider = self.user_llm.get(user_id, config.LLM_DEFAULT_PROVIDER)
        client = self.llm_manager.get_client(provider)

        bot_city = None
        if client:
            # duck typing: и GigaChatClient, и OpenAIClient реализуют этот метод
            bot_city = client.get_city_from_ai(
                last_city=user_city,
                used_cities_prompt=used_cities_prompt
            )
        
        if not bot_city:
            await update.message.reply_text(
                f"*Поздравляю! Вы выиграли!*\n"
                f"Бот не смог назвать город на букву '{last_letter.upper()}'\n\n"
                f"Новая игра: /start",
                parse_mode='Markdown'
            )
            self.game_engine.end_game(user_id)
            return
        
        # Добавляем город бота
        game_state = self.game_engine.get_game_state(user_id)
        game_state.used_cities.add(bot_city.strip().lower())
        game_state.last_city = bot_city
        bot_last_letter = self.game_engine.get_last_letter(bot_city)
        game_state.player_turn = True  # Возвращаем ход игроку
        
        # Создаем кнопку для информации о городе
        keyboard = [[InlineKeyboardButton("ℹ️ Инфо о городе", callback_data=f"info_{bot_city.lower()}")]]
        
        # Отправляем ответ бота
        await update.message.reply_text(
            f"*Бот отвечает:* {bot_city}\n"
            f"Вам на букву *'{bot_last_letter.upper()}'*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Обработка выбора LLM при старте игры
        if query.data == "llm_gigachat" or query.data == "llm_openai":
            provider = "gigachat" if query.data == "llm_gigachat" else "openai"
            self.user_llm[user_id] = provider

            llm_name = "GigaChat" if provider == "gigachat" else "OpenAI"
            start_text = self.game_engine.start_game(user_id)
            await query.message.reply_text(
                f"Выбран LLM: *{llm_name}*\n\n{start_text}",
                parse_mode="Markdown",
            )
            return
        
        if query.data.startswith("info_"):
            city_name = query.data[5:].title()
            provider = self.user_llm.get(user_id, config.LLM_DEFAULT_PROVIDER)
            client = self.llm_manager.get_client(provider)

            info = None
            if client:
                info = client.get_city_info(city_name)
            
            if info:
                await query.message.reply_text(f"*{city_name}:*\n{info}", parse_mode='Markdown')
            else:
                await query.message.reply_text(f"Нет информации о городе {city_name}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ошибок"""
        logger.error(f"Ошибка: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("Произошла ошибка. Попробуйте еще раз.")