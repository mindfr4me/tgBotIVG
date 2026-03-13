import logging
import time
import re
from typing import Optional
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

logger = logging.getLogger(__name__)

class GigaChatClient:
    """Клиент для работы с GigaChat API"""
    
    def __init__(self, token: str, base_url: Optional[str] = None):
        """Инициализация клиента GigaChat"""
        self.client = GigaChat(
            credentials=token,
            base_url=base_url,
            verify_ssl_certs=False
        )
        self.model = "GigaChat:latest"
        
    def get_city_from_ai(self, 
                        last_city: Optional[str] = None,
                        used_cities_prompt: str = "",
                        max_retries: int = 3) -> Optional[str]:
        """
        Получает город от AI с учетом правил игры
        
        Args:
            last_city: Последний названный город
            used_cities_prompt: Информация об использованных городах
            max_retries: Максимальное количество попыток
            
        Returns:
            Название города или None в случае ошибки
        """
        system_prompt = self._create_system_prompt(last_city, used_cities_prompt)
        
        # Логируем промпт для отладки
        logger.debug(f"GigaChat промпт:\n{system_prompt}")
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Запрос к GigaChat (попытка {attempt + 1}/{max_retries})")
                
                response = self.client.chat(
                    Chat(
                        messages=[
                            Messages(
                                role=MessagesRole.SYSTEM,
                                content=system_prompt
                            )
                        ],
                        model=self.model,
                        temperature=0.7,
                        max_tokens=50
                    )
                )
                
                # Логируем полный ответ
                full_response = response.choices[0].message.content
                logger.debug(f"Полный ответ GigaChat: {full_response}")
                
                city = self._extract_city_from_response(response)
                
                if city:
                    logger.info(f"GigaChat ответил: '{city}' (извлечено из: '{full_response}')")
                    return city
                else:
                    logger.warning(f"Не удалось извлечь город из ответа: '{full_response}'")
                    
            except Exception as e:
                logger.error(f"Ошибка при запросе к GigaChat: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Задержка перед повторной попыткой
                    
        logger.error(f"Не удалось получить город от GigaChat после {max_retries} попыток")
        return None
    
    def get_city_info(self, city_name: str) -> Optional[str]:
        """
        Получает информацию о городе от AI
        
        Args:
            city_name: Название города
            
        Returns:
            Информация о городе или None в случае ошибки
        """
        try:
            prompt = (f"Предоставь краткую информацию о городе {city_name} (Россия). "
                     f"Укажи: область/край/республику, население (примерно), "
                     f"год основания и одну достопримечательность. "
                     f"Ответ должен быть кратким (1-2 предложения).")
            
            response = self.client.chat(
                Chat(
                    messages=[
                        Messages(
                            role=MessagesRole.USER,
                            content=prompt
                        )
                    ],
                    model=self.model,
                    temperature=0.3,
                    max_tokens=150
                )
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о городе: {e}")
            return None

    def is_real_russian_city(self, city_name: str, max_retries: int = 2) -> bool:
        """
        Проверяет через GigaChat, является ли указанная строка реальным городом России.
        Ожидаемый ответ модели: строго 'ДА' или 'НЕТ'.
        """
        question = (
            "Определи, является ли следующий топоним реальным городом России.\n"
            f"Топоним: '{city_name}'.\n\n"
            "Ответь строго одним словом: 'ДА', если это реальный город России, "
            "или 'НЕТ' в любом другом случае. Никаких других слов или знаков."
        )

        for attempt in range(max_retries):
            try:
                response = self.client.chat(
                    Chat(
                        messages=[
                            Messages(
                                role=MessagesRole.USER,
                                content=question
                            )
                        ],
                        model=self.model,
                        temperature=0.0,
                        max_tokens=3
                    )
                )
                answer = response.choices[0].message.content.strip().upper()
                logger.debug(f"Проверка города '{city_name}' в GigaChat: ответ '{answer}'")
                if "ДА" in answer:
                    return True
                if "НЕТ" in answer:
                    return False
            except Exception as e:
                logger.error(f"Ошибка при проверке города в GigaChat: {e}")
                time.sleep(1)

        # Если что-то пошло не так, считаем город некорректным, чтобы не ломать правила
        return False
    
    def _create_system_prompt(self, last_city: Optional[str], used_cities_prompt: str) -> str:
        """Создает системный промпт для AI"""
        # Более строгий и четкий промпт
        base_rules = """
Ты - участник игры в города России. Отвечай ТОЛЬКО названием города.

ВАЖНЫЕ ПРАВИЛА:
1. Ответ должен быть ТОЛЬКО названием города, без любых других слов
2. Без кавычек, точек, восклицательных знаков
3. Без пояснений типа "Я назову город..." или "Мой ответ:"
4. Город должен быть реальным и находиться в России
5. Формат: одно или несколько СЛОВ с заглавной буквы, между словами ОБЯЗАТЕЛЬНО пробелы
6. Буквы Ь, Ы, Ъ, Й, Ё пропускаются при определении последней буквы

Примеры ПРАВИЛЬНЫХ ответов:
Москва
Санкт-Петербург
Набережные Челны
Нижний Новгород

Примеры НЕПРАВИЛЬНЫХ ответов:
"Астрахань" (лишние кавычки)
Я выбираю город Екатеринбург (лишние слова)
казань (маленькая буква)
Набережныечелны (нет пробела между словами)
Нижнийновгород (нет пробела между словами)
"""
        
        if last_city:
            # Определяем последнюю букву (пропуская запрещенные)
            last_letter = self._get_last_letter_simple(last_city)
            return (
                f"{base_rules}\n"
                f"СИТУАЦИЯ: Последний названный город: '{last_city}'.\n"
                f"Последняя буква (без Ь, Ы, Ъ, Й, Ё): '{last_letter.upper()}'.\n"
                f"Ты должен назвать город, который начинается на букву '{last_letter.upper()}'.\n"
                f"{used_cities_prompt}\n\n"
                f"ТВОЙ ОТВЕТ (ТОЛЬКО название города):"
            )
        else:
            return (
                f"{base_rules}\n"
                f"СИТУАЦИЯ: Игра только началась.\n"
                f"Назови ЛЮБОЙ российский город для начала игры.\n"
                f"{used_cities_prompt}\n\n"
                f"ТВОЙ ОТВЕТ (ТОЛЬКО название города):"
            )
    
    def _get_last_letter_simple(self, city: str) -> str:
        """Упрощенный метод определения последней буквы (для промпта)"""
        if not city:
            return ""
        
        city_lower = city.lower().strip()
        forbidden = {'ь', 'ы', 'ъ', 'й', 'ё'}
        
        # Ищем последнюю допустимую букву
        for i in range(len(city_lower) - 1, -1, -1):
            letter = city_lower[i]
            if letter not in forbidden:
                return letter
        
        # Если все буквы запрещенные (маловероятно), возвращаем последнюю
        return city_lower[-1] if city_lower else ""
    
    def _extract_city_from_response(self, response) -> Optional[str]:
        """Извлекает название города из ответа GigaChat"""
        try:
            content = response.choices[0].message.content.strip()
            
            # Логи для отладки
            logger.debug(f"Сырой ответ GigaChat: '{content}'")
            
            # 1. Убираем все HTML/маркдаун теги
            content = re.sub(r'[*_`#]', '', content)
            
            # 2. Убираем "Город:", "Назову:", "Я выберу" и т.д.
            patterns_to_remove = [
                r'^(?:я\s+)?(?:выбираю|назову|отвечаю|говорю|называю|предлагаю)[:\s]*',
                r'^(?:город|городом|города)[:\s]*',
                r'^(?:пусть\s+)?будет[:\s]*',
                r'^(?:давай|например|скажем)[:\s]*',
                r'^[^а-яА-Я]*',  # Все не-буквы в начале
            ]
            
            for pattern in patterns_to_remove:
                content = re.sub(pattern, '', content, flags=re.IGNORECASE)
            
            # 3. Убираем кавычки, точки, знаки препинания в начале/конце
            content = content.strip('"\':.,!? \n\t')
            
            # 4. Разделяем на строки и берем первую непустую
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line) > 2:
                    line = re.sub(r'[.,!?:;]+$', '', line)

                    # 4.1. Пробуем однословные варианты
                    if re.match(r'^[А-ЯЁ][а-яё-]+$', line):
                        return line
                    if re.match(r'^[а-яё-]+$', line):
                        return line.capitalize()

                    # 4.2. Многословные города: берем до 3 слов с русскими буквами
                    words = [w.strip('",.?!:;') for w in line.split() if w.strip('",.?!:;')]
                    rus_words = []
                    for w in words:
                        if re.search(r'[а-яА-ЯёЁ]', w):
                            rus_words.append(w)
                    if rus_words:
                        candidate = ' '.join(rus_words[:3])
                        return candidate.title()

            # 5. Если не нашли по правилам, берем до 3 слов из всего контента
            words = [w.strip('",.?!:;') for w in content.split() if w.strip('",.?!:;')]
            rus_words = [w for w in words if len(w) > 1 and re.search(r'[а-яА-ЯёЁ]', w)]
            if rus_words:
                candidate = ' '.join(rus_words[:3])
                candidate = candidate.title()
                candidate = self._normalize_compound_city(candidate)
                return candidate
            
            logger.warning(f"Не удалось извлечь город из ответа: '{content}'")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке ответа GigaChat: {e}")
            
        return None

    def _normalize_compound_city(self, city: str) -> str:
        """
        Исправляет некоторые часто встречающиеся слитные написания многословных городов.
        Например: 'Нижнийновгород' -> 'Нижний Новгород', 'Набережныечелны' -> 'Набережные Челны'.
        """
        mapping = {
            "нижнийновгород": "Нижний Новгород",
            "набережныечелны": "Набережные Челны",
        }
        key = city.replace(" ", "").lower()
        return mapping.get(key, city)