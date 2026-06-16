# AI Sales Agent

Telegram-бот как AI-команда для продажи и разработки AI-чат-ботов бизнесу. Пользователь пишет команду, бот выбирает нужного агента и вызывает локальную Ollama API. OpenAI API не используется.

## Что внутри

- 25 AI-агентов для контента, продаж, аудита, КП, разработки, промтов, тестов и ведения проекта.
- Threads Publishing Agent: готовит посты, хранит SQLite-очередь и публикует через Threads API только после подтверждения пользователя.
- Без спама: бот не пишет людям сам, не лайкает, не подписывается, не обходит лимиты и не отправляет автолички.

## Команды

### Маркетинг и контент
1. `/posts` — 10 постов.
2. `/threads <тема>` — Threads-ветка.
3. `/reels <тема>` — сценарий Reels/TikTok/Shorts.
4. `/hooks <ниша>` — 20 хуков.
5. `/niches` — 10 ниш.
6. `/competitors <ниша>` — анализ конкурентов.
7. `/case <проект>` — оформление кейса.
8. `/brand <цель>` — личный бренд.

### Продажи и диалоги
9. `/comment <комментарий>` — ответы на комментарий.
10. `/dm <сообщение>` — ответ клиенту.
11. `/objection <возражение>` — обработка возражения.
12. `/followup <контекст>` — follow-up.
13. `/qualify <клиент>` — квалификация.
14. `/script <ниша>` — скрипт продаж.
15. `/close <контекст>` — закрытие на следующий шаг.

### Аналитика, офферы и КП
16. `/audit <бизнес>` — аудит бизнеса.
17. `/offer <ниша>` — оффер.
18. `/proposal <задача>` — КП.
19. `/pricing <проект>` — цена и пакеты.
20. `/roi <бизнес>` — объяснение выгоды без гарантий прибыли.

### Разработка, ТЗ и проект
21. `/codex <проект>` — ТЗ для Codex/разработчика.
22. `/architecture <бот>` — архитектура бота.
23. `/prompt <задача>` — system prompt.
24. `/tests <бот>` — тестовые сценарии.
25. `/pm <проект>` — план работ.

### Threads Publishing Agent

- `/threads_day` — подготовить 5 постов на сегодня и добавить в очередь.
- `/threads_post <тема>` — подготовить один пост.
- `/threads_queue` — показать очередь.
- `/threads_publish <id>` — опубликовать выбранный пост после подтверждения.
- `/threads_rewrite <id>` — переделать пост.
- `/threads_skip <id>` — пропустить пост.
- `/threads_next` — показать следующий draft.

У draft-поста есть inline-кнопки: опубликовать, переделать, пропустить, следующий.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ollama

Установите Ollama с официального сайта и скачайте модель:

```bash
ollama pull llama3.2:3b
```

Если Ollama не отвечает, запустите Ollama и проверьте, что модель скачана.

## Telegram BotFather

1. Откройте `@BotFather` в Telegram.
2. Выполните `/newbot`.
3. Скопируйте токен в `.env`.

## .env

Скопируйте пример:

```bash
cp .env.example .env
```

Заполните:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
THREADS_ACCESS_TOKEN=your_threads_access_token
THREADS_USER_ID=your_threads_user_id
THREADS_API_BASE_URL=https://graph.threads.net
THREADS_AUTO_PUBLISH=false
DATABASE_PATH=./ai_sales_agent.db
```

`THREADS_AUTO_PUBLISH=false` — безопасный режим по умолчанию. Публикация только после подтверждения.

## Threads API

Для публикации нужны `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`, `THREADS_API_BASE_URL`. Если они не настроены, бот будет только готовить посты и держать их в очереди.

## Запуск

```bash
python -m app.main
```

## Railway Deploy

Проект готовится как два отдельных Railway-сервиса: `ai-sales-agent` и `ollama`.

### 1. Создать Railway Project

1. Откройте Railway и создайте новый Project.
2. Подключите GitHub-репозиторий `vrempel90-dev/ai-sales-agent`.
3. Создайте сервис `ai-sales-agent` из этого репозитория. Railway использует `Dockerfile` и `railway.json`.

### 2. Variables для `ai-sales-agent`

Добавьте переменные окружения в Railway Variables:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b
DATABASE_PATH=/data/ai_sales_agent.db
THREADS_ACCESS_TOKEN=your_threads_access_token
THREADS_USER_ID=your_threads_user_id
THREADS_API_BASE_URL=https://graph.threads.net
THREADS_AUTO_POSTING_ENABLED=false
THREADS_AUTO_POSTS_PER_DAY=3
THREADS_AUTO_POST_HOURS=10,14,18
THREADS_AUTO_POST_TIMEZONE=Asia/Almaty
THREADS_AUTO_GENERATE_IF_QUEUE_EMPTY=true
THREADS_DAILY_POST_LIMIT=3
```

`THREADS_ACCESS_TOKEN` и `THREADS_USER_ID` не обязательны для генерации и очереди. Если их нет, публикация в Threads будет отключена, но бот сможет готовить посты и хранить их в SQLite.

### 3. SQLite Volume

Чтобы очередь Threads-постов не очищалась при рестарте Railway:

1. Добавьте Railway Volume к сервису `ai-sales-agent`.
2. Укажите mount path: `/data`.
3. Установите `DATABASE_PATH=/data/ai_sales_agent.db`.

Локально можно использовать `DATABASE_PATH=./ai_sales_agent.db`.

### 4. Ollama service

`OLLAMA_BASE_URL` на Railway не должен быть `localhost`: Railway-сервис не видит Ollama на вашем ПК.

Варианты подключения:

- **Вариант A: отдельный Railway Ollama service.** Создайте отдельный сервис `ollama`, скачайте модель и укажите для бота внутренний URL, например `OLLAMA_BASE_URL=http://ollama:11434`, или URL, который даст Railway.
- **Вариант B: внешний VPS с Ollama.** Запустите Ollama на VPS и укажите публичный/приватный URL VPS в `OLLAMA_BASE_URL`.
- **Вариант C: локальная Ollama не подходит для Railway.** `http://localhost:11434` работает только на вашей машине, но не из контейнера Railway.

Для старта на Railway используйте модель:

```bash
llama3.2:3b
```

Она легче, чем `llama3.1:8b`. Более тяжёлые модели могут требовать больше памяти.

### 5. Проверка после деплоя

В Telegram проверьте команды:

- `/start`
- `/health`
- `/agents`
- `/day`
- `/threads_day`
- `/threads_queue`

`/health` показывает, что бот работает, модель Ollama, URL Ollama, статус Threads API, количество draft-постов, количество опубликованных сегодня и статус автопостинга.

### 6. Автопостинг Threads

По умолчанию автопостинг выключен:

```env
THREADS_AUTO_POSTING_ENABLED=false
```

Чтобы включить его на Railway, установите:

```env
THREADS_AUTO_POSTING_ENABLED=true
```

Также можно использовать команды статуса и ручных действий:

- `/autopost_status`
- `/autopost_plan`
- `/autopost_now`
- `/autopost_generate`
- `/autopost_on`
- `/autopost_off`

Важно: автопостинг публикует только собственные подготовленные посты. Бот не пишет комментарии, не пишет в личку, не лайкает и не подписывается.
