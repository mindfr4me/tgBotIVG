import logging
import re
import time
from typing import Optional

from openai import OpenAI

from log_llm import log_llm_call

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Клиент для работы с OpenAI как с LLM для игры в города."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        if not api_key:
            raise ValueError("OPENAI_API_KEY пустой. Укажи ключ в переменной окружения OPENAI_API_KEY.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def get_city_from_ai(
        self,
        last_city: Optional[str] = None,
        used_cities_prompt: str = "",
        max_retries: int = 3,
    ) -> Optional[str]:
        """
        Получает город от OpenAI с учетом правил игры.
        Поведение по смыслу повторяет GigaChatClient.get_city_from_ai.
        """
        system_prompt = self._create_system_prompt(last_city, used_cities_prompt)

        logger.debug(f"OpenAI промпт:\n{system_prompt}")

        for attempt in range(max_retries):
            try:
                logger.info(f"Запрос к OpenAI (попытка {attempt + 1}/{max_retries})")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=50,
                )

                full_response = response.choices[0].message.content or ""
                logger.debug(f"Полный ответ OpenAI: {full_response}")

                # Логируем запрос/ответ в SQLite
                log_llm_call(self.model, system_prompt, full_response)

                city = self._extract_city_from_response(full_response)
                if city:
                    logger.info(f"OpenAI ответил: '{city}' (извлечено из: '{full_response}')")
                    return city
                else:
                    logger.warning(f"Не удалось извлечь город из ответа: '{full_response}'")

            except Exception as e:
                logger.error(f"Ошибка при запросе к OpenAI: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)

        logger.error(f"Не удалось получить город от OpenAI после {max_retries} попыток")
        return None

    def get_city_info(self, city_name: str) -> Optional[str]:
        """
        Получает краткую информацию о городе от OpenAI.
        Аналогично GigaChatClient.get_city_info.
        """
        try:
            prompt = (
                f"Предоставь краткую информацию о городе {city_name} (Россия). "
                f"Укажи: область/край/республику, население (примерно), "
                f"год основания и одну достопримечательность. "
                f"Ответ должен быть кратким (1-2 предложения)."
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150,
            )
            content = response.choices[0].message.content

            # Логируем запрос/ответ в SQLite
            log_llm_call(self.model, prompt, content)

            return content

        except Exception as e:
            logger.error(f"Ошибка при получении информации о городе (OpenAI): {e}")
            return None

    def is_real_russian_city(self, city_name: str, max_retries: int = 2) -> bool:
        """
        Проверяет через OpenAI, является ли указанная строка реальным городом России.
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
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": question},
                    ],
                    temperature=0.0,
                    max_tokens=3,
                )
                raw_answer = response.choices[0].message.content or ""
                answer = raw_answer.strip().upper()
                # Логируем запрос/ответ в SQLite
                log_llm_call(self.model, question, raw_answer)
                logger.debug(f"Проверка города '{city_name}' в OpenAI: ответ '{answer}'")
                if "ДА" in answer:
                    return True
                if "НЕТ" in answer:
                    return False
            except Exception as e:
                logger.error(f"Ошибка при проверке города в OpenAI: {e}")
                time.sleep(1)

        # Если не смогли проверить, считаем город некорректным
        return False

    def _create_system_prompt(self, last_city: Optional[str], used_cities_prompt: str) -> str:
        """Создает системный промпт для AI (скопирован и адаптирован из GigaChatClient)."""
        base_rules = """
Ты - участник игры в города России. Отвечай ТОЛЬКО названием города.

ВАЖНЫЕ ПРАВИЛА:
1. Ответ должен быть ТОЛЬКО названием города, без любых других слов
2. Без кавычек, точек, восклицательных знаков
3. Без пояснений типа "Я назову город..." или "Мой ответ:"
4. Город должен быть реальным и находиться в России
5. Формат: одно слово с заглавной буквы
6. Буквы Ь, Ы, Ъ, Й, Ё пропускаются при определении последней буквы

Примеры ПРАВИЛЬНЫХ ответов:
Москва
Санкт-Петербург
Новосибирск

Примеры НЕПРАВИЛЬНЫХ ответов:
"Астрахань" (лишние кавычки)
Я выбираю город Екатеринбург (лишние слова)
казань (маленькая буква)
"""

        if last_city:
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
        """Упрощенный метод определения последней буквы (для промпта)."""
        if not city:
            return ""

        city_lower = city.lower().strip()
        forbidden = {"ь", "ы", "ъ", "й", "ё"}

        for i in range(len(city_lower) - 1, -1, -1):
            letter = city_lower[i]
            if letter not in forbidden:
                return letter

        return city_lower[-1] if city_lower else ""

    def _extract_city_from_response(self, content: str) -> Optional[str]:
        """Извлекает название города из текстового ответа модели."""
        try:
            content = (content or "").strip()
            logger.debug(f"Сырой ответ OpenAI: '{content}'")

            content = re.sub(r"[*_`#]", "", content)

            patterns_to_remove = [
                r"^(?:я\s+)?(?:выбираю|назову|отвечаю|говорю|называю|предлагаю)[:\s]*",
                r"^(?:город|городом|города)[:\s]*",
                r"^(?:пусть\s+)?будет[:\s]*",
                r"^(?:давай|например|скажем)[:\s]*",
                r"^[^а-яА-Я]*",
            ]

            for pattern in patterns_to_remove:
                content = re.sub(pattern, "", content, flags=re.IGNORECASE)

            content = content.strip('"\'.,!? \n\t')

            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line and len(line) > 2:
                    line = re.sub(r"[.,!?:;]+$", "", line)

                    # 1. Однословные варианты
                    if re.match(r"^[А-ЯЁ][а-яё-]+$", line):
                        return line
                    if re.match(r"^[а-яё-]+$", line):
                        return line.capitalize()

                    # 2. Многословные города: берем до 3 слов с русскими буквами
                    words = [w.strip('",.?!:;') for w in line.split() if w.strip('",.?!:;')]
                    rus_words = []
                    for w in words:
                        if re.search(r"[а-яА-ЯёЁ]", w):
                            rus_words.append(w)
                    if rus_words:
                        candidate = " ".join(rus_words[:3])
                        return candidate.title()

            # 3. Фолбэк: берем до 3 слов из всего контента
            words = [w.strip('",.?!:;') for w in content.split() if w.strip('",.?!:;')]
            rus_words = [w for w in words if len(w) > 1 and re.search(r"[а-яА-ЯёЁ]", w)]
            if rus_words:
                candidate = " ".join(rus_words[:3])
                return candidate.title()

            logger.warning(f"Не удалось извлечь город из ответа: '{content}'")

        except Exception as e:
            logger.error(f"Ошибка при обработке ответа OpenAI: {e}")

        return None

