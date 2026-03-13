import os
import sys
import logging

# Опциональная установка значений по умолчанию для локального запуска.
# Рекомендуется задавать реальные токены через переменные окружения или .env.
os.environ.setdefault("TELEGRAM_TOKEN", "")
os.environ.setdefault("GIGACHAT_TOKEN", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LLM_DEFAULT_PROVIDER", "gigachat")  # gigachat | openai

# Добавляем текущую папку в путь Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)

print("=" * 50)
print("Запуск бота (run_simple.py)")
print("TELEGRAM_TOKEN задан:", bool(os.environ.get("TELEGRAM_TOKEN")))
print("GIGACHAT_TOKEN задан:", bool(os.environ.get("GIGACHAT_TOKEN")))
print("OPENAI_API_KEY задан:", bool(os.environ.get("OPENAI_API_KEY")))
print("LLM_DEFAULT_PROVIDER:", os.environ.get("LLM_DEFAULT_PROVIDER"))
print("=" * 50)

# Теперь импортируйте и запустите main
try:
    from main import main

    main()
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Проверьте, что все файлы в одной папке:")
    import os as _os

    print("Файлы:", _os.listdir())
except Exception as e:
    print(f"Ошибка: {e}")