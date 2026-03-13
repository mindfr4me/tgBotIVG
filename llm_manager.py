from __future__ import annotations

import logging
from typing import Dict, Optional

from config import config
from gigachat_client import GigaChatClient
from openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class LLMManager:
    """
    Менеджер LLM-клиентов.

    Держит экземпляры клиентов для разных провайдеров и выдает нужный
    в зависимости от имени провайдера.
    """

    def __init__(self):
        self.clients: Dict[str, object] = {}

        if config.GIGACHAT_TOKEN:
            try:
                self.clients["gigachat"] = GigaChatClient(config.GIGACHAT_TOKEN)
            except Exception as e:
                logger.error(f"Не удалось инициализировать GigaChatClient: {e}")

        if config.OPENAI_API_KEY:
            try:
                self.clients["openai"] = OpenAIClient(config.OPENAI_API_KEY)
            except Exception as e:
                logger.error(f"Не удалось инициализировать OpenAIClient: {e}")

        if not self.clients:
            logger.error("Не инициализирован ни один LLM-клиент. Проверь токены в .env.")

    def available_providers(self) -> Dict[str, str]:
        """
        Возвращает доступных провайдеров.
        Ключ: идентификатор (gigachat/openai), значение: человекочитаемое имя.
        """
        result = {}
        if "gigachat" in self.clients:
            result["gigachat"] = "GigaChat"
        if "openai" in self.clients:
            result["openai"] = "OpenAI"
        return result

    def get_client(self, provider: Optional[str]) -> Optional[object]:
        """
        Возвращает клиента по имени провайдера.
        Если provider не задан, используется LLM_DEFAULT_PROVIDER.
        """
        if not self.clients:
            return None

        name = (provider or config.LLM_DEFAULT_PROVIDER or "gigachat").lower()
        client = self.clients.get(name)

        if client is None:
            # fallback на первый доступный
            any_client = next(iter(self.clients.values()))
            logger.warning(
                f"Клиент для провайдера '{name}' не найден, используется первый доступный."
            )
            return any_client

        return client

