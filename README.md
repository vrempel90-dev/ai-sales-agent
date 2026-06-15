# AI Sales Agent

Telegram-бот как AI-команда для продажи и разработки AI-чат-ботов бизнесу. Пользователь пишет команду, бот выбирает нужного агента и вызывает локальную Ollama API. OpenAI API не используется.

## Что внутри

- 25 AI-агентов для контента, продаж, аудита, КП, разработки, промтов, тестов и ведения проекта.
- Threads Publishing Agent: готовит посты, хранит in-memory очередь и публикует через Threads API только после подтверждения пользователя.
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
ollama pull llama3.1:8b
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
OLLAMA_MODEL=llama3.1:8b
THREADS_ACCESS_TOKEN=your_threads_access_token
THREADS_USER_ID=your_threads_user_id
THREADS_API_BASE_URL=https://graph.threads.net
THREADS_AUTO_PUBLISH=false
```

`THREADS_AUTO_PUBLISH=false` — безопасный режим по умолчанию. Публикация только после подтверждения.

## Threads API

Для публикации нужны `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`, `THREADS_API_BASE_URL`. Если они не настроены, бот будет только готовить посты и держать их в очереди.

## Запуск

```bash
python -m app.main
```
