# AI Sales Agent для Threads

Production-ready каркас автономного AI-агента, который ведёт Threads-аккаунт Виктора и приводит горячих лидов на разработку AI-агентов для бизнеса.

## Что делает агент

- генерирует Threads-посты от лица Виктора;
- публикует посты по расписанию;
- принимает webhook-события Threads: комментарии, ответы, упоминания;
- отвечает потенциальным клиентам коротко и без давления;
- выявляет нишу, боль, канал заявок и интерес к автоматизации;
- оценивает лида по шкале 0–100;
- отправляет Виктору в Telegram только горячих лидов;
- сохраняет посты, контакты, диалоги и лидов в базе;
- не отвлекает Виктора холодными диалогами.

## Архитектура

```text
app/
  main.py              FastAPI endpoints и startup
  config.py            Pydantic Settings
  database.py          SQLAlchemy engine/session/init_db
  models.py            Post, Contact, Conversation, Lead
  schemas.py           Pydantic API-схемы
  prompts.py           системные промты
  ai.py                LLM provider wrapper: Ollama/OpenAI с fallback и retry
  threads_api.py       wrapper Threads / Meta Graph API
  content_agent.py     генерация и сохранение постов
  comment_agent.py     ответы, квалификация, скоринг
  lead_scoring.py      правила оценки лида
  lead_handoff.py      создание лида и передача Виктору
  telegram_notify.py   Telegram Bot API уведомления
  scheduler.py         APScheduler публикации
  safety_guard.py      антиспам и безопасные ответы
  utils.py             утилиты
```

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Проверка:

```bash
curl http://127.0.0.1:8000/health
```

Ответ:

```json
{"status":"ok"}
```

## Переменные окружения

```env
LLM_PROVIDER=ollama

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

THREADS_ACCESS_TOKEN=
THREADS_USER_ID=
THREADS_WEBHOOK_VERIFY_TOKEN=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DB

AUTO_PUBLISH=true
POSTS_PER_DAY=3
LEAD_SCORE_THRESHOLD=70
```

Если Threads или Telegram токены не заданы, приложение логирует warning и продолжает работать. Секреты не выводятся в логах.

## AI provider

По умолчанию агент использует Ollama:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
```

Для Railway нужен отдельный Ollama service/container в том же проекте или внешний Ollama URL, доступный из Railway. Если Ollama недоступна, приложение не падает: оно логирует warning и возвращает безопасные fallback-ответы для AI-функций.

Чтобы переключиться на OpenAI, задайте:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4o-mini
```

Секреты не выводятся в логах. На старте приложение показывает выбранный `llm_provider`, факт настройки OpenAI, факт настройки Ollama base URL и модель Ollama.

## Railway deploy

1. Создать Railway project.
2. Подключить репозиторий.
3. Добавить PostgreSQL plugin или внешний PostgreSQL.
4. Заполнить переменные из `.env.example`.
5. Railway использует `railway.json` или `Procfile`:

```bash
sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'
```

## Threads API

`app/threads_api.py` содержит интерфейс:

- `publish_text_post(text)`
- `get_replies(post_id)`
- `reply_to_comment(comment_id, text)`
- `verify_webhook_token(token)`
- `parse_webhook_event(payload)`

Важно: реальные endpoint Threads API и permissions могут отличаться в зависимости от Meta Developer App, версии Graph API и режима приложения. Перед production-нaстройкой нужно проверить актуальный flow публикации, replies и webhook permissions в Meta Developer.

## Telegram

Создайте бота через BotFather, получите `TELEGRAM_BOT_TOKEN`, узнайте `TELEGRAM_CHAT_ID` Виктора и добавьте их в Railway Variables. Горячий лид отправляется в формате карточки:

```text
🔥 ГОРЯЧИЙ ЛИД
Ник: @username
Ниша:
Канал заявок:
Боль:
Что хочет:
Оценка лида:
Кратко:
Следующий шаг:
Ссылка на диалог:
```

## Lead scoring

Правила:

- +20 если есть бизнес;
- +20 если описана боль;
- +15 если спросил цену;
- +15 если спросил сроки;
- +20 если сказал «хочу», «нужно», «можно консультацию», «хочу внедрить»;
- +10 если оставил контакт или согласился на разбор.

Статусы:

- 0–39 = `cold`;
- 40–69 = `warm`;
- 70–100 = `hot`.

Виктор получает уведомление только если `lead_score >= LEAD_SCORE_THRESHOLD` и лид ещё не отправлялся.

## Endpoints

- `GET /health` — healthcheck;
- `GET /webhooks/threads` — verify token для Threads webhook;
- `POST /webhooks/threads` — обработка комментариев, ответов и упоминаний;
- `POST /admin/generate-post` — ручная генерация поста;
- `POST /admin/publish-post` — ручная публикация поста;
- `GET /admin/leads` — список лидов;
- `GET /admin/posts` — список постов.

## Что ещё нужно доделать для production

- подтвердить актуальные Threads endpoints и permissions в Meta Developer;
- добавить авторизацию на `/admin/*` endpoints;
- добавить Alembic migrations вместо `create_all`;
- добавить idempotency для webhook events;
- добавить observability: structured logs, metrics, tracing;
- добавить rate limit и backoff под реальные лимиты Threads;
- добавить e2e тесты с sandbox Meta app.

## Safety notes

В безопасном режиме: нет scraping, нет mass DM, нет browser automation без явного ручного включения и официальной доступной сессии. Автоматические DM отключены; live browser comments требуют отдельного подтверждённого режима и safety checks.
