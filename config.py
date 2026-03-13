import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Конфигурация приложения"""
    TELEGRAM_TOKEN: str
    GIGACHAT_TOKEN: str
    OPENAI_API_KEY: str
    LLM_DEFAULT_PROVIDER: str = "gigachat"  # gigachat | openai
    DEBUG: bool = True
    
    @classmethod
    def from_env(cls):
        """Загружает конфигурацию из переменных окружения"""
        return cls(
            TELEGRAM_TOKEN=os.getenv("TELEGRAM_TOKEN"),
            GIGACHAT_TOKEN=os.getenv("GIGACHAT_TOKEN"),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
            LLM_DEFAULT_PROVIDER=os.getenv("LLM_DEFAULT_PROVIDER", "gigachat").lower(),
            DEBUG=os.getenv("DEBUG", "True").lower() == "true"
        )

# Инициализация конфигурации
config = Config.from_env()