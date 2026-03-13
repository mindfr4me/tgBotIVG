import os
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DB_NAME = "logLLM.db"  # файл БД в корне проекта
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)


def _ensure_db() -> None:
    """Создает БД и таблицу logLLM при необходимости."""
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logLLM (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Не удалось инициализировать БД logLLM: {e}")


def log_llm_call(model: str, prompt: str, response: Optional[str]) -> None:
    """
    Логирует один запрос/ответ LLM в SQLite.
    Ошибки логирования не должны ломать основную логику бота.
    """
    if response is None:
        response = ""

    try:
        _ensure_db()
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO logLLM (model, prompt, response)
                VALUES (?, ?, ?);
                """,
                (model, prompt, response),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Ошибка при записи лога LLM в БД: {e}")

