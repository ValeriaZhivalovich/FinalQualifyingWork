# News Analyzer

Десктопное приложение для автоматического сбора, обработки и анализа новостей из различных источников (Telegram, VK, Twitter/X, Reddit, RSS) с использованием ИИ-агентов и методов обработки естественного языка.

## Стек технологий
- Python 3.12+
- Flet (GUI)
- SQLite + SQLAlchemy
- Ollama (локальные LLM, mistral:7b)
- Telethon / Pyrogram (Telegram API)
- vk_api / vkwave (VK API)
- Twikit (Twitter/X API, без API-ключа)
- PRAW / Async PRAW (Reddit API)
- feedparser (RSS)
- NLTK, pymystem3 (NLP)
- pydantic-settings (конфигурация)

## Архитектура
Система построена по модульному принципу с разделением на слои:
1. Сбор данных (Collectors) — RSS, Telegram, VK, Twitter/X, Reddit
2. Нормализация текста (NLP Preprocessor) — очистка HTML/URL, выделение ключевых слов
3. ИИ-обработка (AI Agent) — генерация заголовка (если отсутствует), саммари, категоризация
4. Хранение данных (Database) — дедупликация по SHA256 хешу + unique constraint
5. Интерфейс (Flet UI) — лента новостей, источники, настройки
6. Оркестрация (Scheduler) — периодический сбор новостей

## Запуск

```bash
# 1. Виртуальное окружение
python -m venv .venv
.venv\Scripts\activate  # Windows

# 2. Зависимости
pip install -r requirements.txt

# 3. Ollama
# Установите и запустите: https://ollama.ai
ollama pull mistral:7b

# 4. Настройки
copy .env.example .env
# Заполните .env (VK_ACCESS_TOKEN, TELEGRAM_API_ID, и т.д.)

# 5. Запуск (нативное окно)
flet run news_analyzer/main.py

# Или в браузере
python news_analyzer/main.py

# Headless режим (без GUI)
python news_analyzer/main.py --headless
```

## Источники

Коллекторы включаются автоматически при наличии соответствующих ключей в `.env`:

| Источник | Ключи в .env | Статус |
|----------|-------------|--------|
| RSS | — | Всегда активен |
| Telegram | TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE | Опционально |
| VK | VK_ACCESS_TOKEN | Опционально |
| Twitter/X | TWITTER_USERNAME, TWITTER_PASSWORD, TWITTER_EMAIL | Опционально |
| Reddit | REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT | Опционально |

По умолчанию все источники фильтруются по ключевым словам Крыма. Фильтрацию можно отключить или изменить в коде коллекторов.

## Структура проекта
```
news_analyzer/
├── collectors/          # Модули сбора данных
├── nlp/                 # Обработка текста
├── ai/                  # ИИ-агенты
├── db/                  # Модели и репозиторий БД
├── pipeline/            # Оркестрация и планировщик
├── ui/                  # Графический интерфейс
├── config/              # Настройки
├── utils/               # Утилиты
└── main.py              # Точка входа
```

## Лицензия
MIT
