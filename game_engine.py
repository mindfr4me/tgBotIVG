import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class GameState:
    """Состояние игры для одного пользователя"""
    used_cities: Set[str] = None
    last_city: Optional[str] = None
    player_turn: bool = True
    
    def __post_init__(self):
        if self.used_cities is None:
            self.used_cities = set()

class CityGameEngine:
    """Движок игры в города"""
    
    # Буквы, на которые не может начинаться следующий город
    FORBIDDEN_ENDINGS = {'ь', 'ы', 'ъ', 'й', 'ё'}
    
    def __init__(self):
        self.games: Dict[int, GameState] = {}
        
    def start_game(self, user_id: int) -> str:
        """Начинает новую игру для пользователя"""
        self.games[user_id] = GameState()
        return ("🎮 Игра началась!\n"
                "Правила: называем города России по очереди.\n"
                "Каждый следующий город должен начинаться на последнюю букву предыдущего.\n"
                "Буквы Ь, Ы, Ъ, Й, Ё пропускаем.\n\n"
                "Ты начинаешь! Назови любой город:")
    
    def end_game(self, user_id: int) -> str:
        """Завершает игру для пользователя"""
        if user_id in self.games:
            del self.games[user_id]
        return "Игра завершена! Чтобы начать новую, отправь /start"
    
    def get_game_state(self, user_id: int) -> Optional[GameState]:
        """Получает состояние игры для пользователя"""
        return self.games.get(user_id)
    
    def validate_city_name(self, city: str) -> Tuple[bool, str]:
        """Проверяет корректность названия города"""
        if not city:
            return False, "Название города не может быть пустым"
        
        if not re.match(r'^[а-яА-ЯёЁ\s-]+$', city):
            return False, "Название должно содержать только русские буквы, пробелы и дефисы"
        
        if len(city.strip()) < 3:
            return False, "Название города слишком короткое"
        
        return True, ""
    
    def get_last_letter(self, city: str) -> Optional[str]:
        """Получает правильную последнюю букву города"""
        # Убираем запрещенные окончания
        city_lower = city.lower().strip()
        
        # Ищем последнюю подходящую букву
        for i in range(len(city_lower) - 1, -1, -1):
            letter = city_lower[i]
            if letter not in self.FORBIDDEN_ENDINGS:
                return letter
        return None
    
    def check_city_rules(self, user_id: int, city: str, last_city: Optional[str] = None) -> Tuple[bool, str]:
        """Проверяет соответствие города правилам игры"""
        game_state = self.get_game_state(user_id)
        if not game_state:
            return False, "Игра не начата. Отправь /start"
        
        city_normalized = city.strip().lower()
        
        # Проверка на повтор
        if city_normalized in game_state.used_cities:
            return False, f"Город '{city}' уже был назван!"
        
        # Проверка первой буквы, если есть предыдущий город
        if last_city and game_state.last_city:
            required_letter = self.get_last_letter(game_state.last_city)
            if not required_letter:
                return False, "Не удалось определить последнюю букву предыдущего города"
            
            first_letter = city_normalized[0]
            if first_letter != required_letter:
                return False, f"Город должен начинаться на букву '{required_letter.upper()}'!"
        
        return True, ""
    
    def add_city(self, user_id: int, city: str) -> str:
        """Добавляет город в список использованных"""
        game_state = self.get_game_state(user_id)
        if game_state:
            city_normalized = city.strip().lower()
            game_state.used_cities.add(city_normalized)
            game_state.last_city = city
            game_state.player_turn = False
            return self.get_last_letter(city)
        return None
    
    def get_available_cities_prompt(self, user_id: int, required_letter: str) -> str:
        """Создает промпт с информацией об использованных городах"""
        game_state = self.get_game_state(user_id)
        if not game_state or not game_state.used_cities:
            return ""
        
        # Фильтруем города по первой букве для подсказки
        cities_on_letter = [
            city for city in game_state.used_cities 
            if city[0] == required_letter.lower()
        ]
        
        if cities_on_letter:
            required_upper = required_letter.upper()
            return (
                f"Уже использованы города на букву '{required_upper}': "
                f"{', '.join(c.title() for c in cities_on_letter[:5])}"
            )
        return ""