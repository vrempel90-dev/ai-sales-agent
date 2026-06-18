# AI Sales Agent

Telegram-бот как AI-команда для продажи и разработки AI-чат-ботов бизнесу. Пользователь пишет команду, бот выбирает нужного агента и вызывает локальную Ollama API. OpenAI API не используется.

## Что внутри

- 25 AI-агентов для контента, продаж, аудита, КП, разработки, промтов, тестов и ведения проекта.
- Viral Threads Agent: создаёт сильные template-first посты о потерях заявок и AI-автоматизации.
- Threads Publishing Agent: готовит посты, хранит SQLite-очередь и публикует через Threads API только после подтверждения пользователя.
- Human-like Sales DM Agent: отвечает на обычные Telegram-сообщения, квалифицирует лидов и ведёт горячих клиентов в WhatsApp.
- Без спама: бот не пишет людям сам, не лайкает, не подписывается, не обходит лимиты и не отправляет автолички.

## Команды

### Маркетинг и контент
1. `/posts` — 10 постов.
2. `/threads тема поста` — Threads-ветка.
3. `/reels тема ролика` — сценарий Reels/TikTok/Shorts.
4. `/hooks ниша` — 20 хуков.
5. `/niches` — 10 ниш.
6. `/competitors ниша` — анализ конкурентов.
7. `/case описание проекта` — оформление кейса.
8. `/brand цель` — личный бренд.

### Продажи и диалоги
9. `/comment текст комментария` — ответы на комментарий.
10. `/dm сообщение клиента` — ответ клиенту.
11. `/objection возражение клиента` — обработка возражения.
12. `/followup контекст диалога` — follow-up.
13. `/qualify описание клиента` — квалификация.
14. `/script ниша` — скрипт продаж.
15. `/close контекст диалога` — закрытие на следующий шаг.

### Lead Conversation Agent

- Обычное Telegram-сообщение без `/` обрабатывается как обращение потенциального клиента.
- Ответы строятся template-first: агент коротко выясняет нишу и процесс, не полагаясь на свободную генерацию слабой Ollama-модели.
- Агент различает интерес, вопрос цены, описание бизнеса, согласие на аудит, горячий лид, запрос сайта и негатив.
- Сайты, лендинги и веб-приложения не предлагаются: диалог возвращается к AI-чат-ботам, обработке заявок, записи, CRM и follow-up.
- Горячий лид получает `WHATSAPP_CONTACT_LINK`; если ссылки нет — `WHATSAPP_PHONE`; если нет обоих, агент просит оставить контакт.
- Владелец получает Telegram-уведомление о горячем лиде через `OWNER_TELEGRAM_ID`.
- `/lead_mode_on`, `/lead_mode_off`, `/lead_mode_status` — управление автоответами только для владельца.
- `/dm_preview сообщение` — предпросмотр ответа без отправки реальному клиенту.
- `/whatsapp_status` — статус WhatsApp-контактов, владельца и lead mode.
- Агрессивный автоматический follow-up не выполняется. Позже агент можно подключить к Threads DM, Instagram DM или WhatsApp только через официальный API/webhook, если он доступен.

### Аналитика, офферы и КП
16. `/audit описание бизнеса` — аудит бизнеса.
17. `/offer ниша` — оффер.
18. `/proposal описание задачи` — КП.
19. `/pricing описание проекта` — цена и пакеты.
20. `/roi описание бизнеса` — объяснение выгоды без гарантий прибыли.

### Разработка, ТЗ и проект
21. `/codex описание проекта` — ТЗ для Codex/разработчика.
22. `/architecture описание бота` — архитектура бота.
23. `/prompt описание задачи` — system prompt.
24. `/tests описание бота` — тестовые сценарии.
25. `/pm описание проекта` — план работ.

### Threads Publishing Agent

- `/viral_threads_day` — создать 7 viral draft-постов: 2 pain, mistake, niche, mini-case, comparison и audit CTA.
- `/viral_post ниша` — создать сильный viral draft под конкретную нишу.
- `/positioning` — показать текущее позиционирование проекта.
- `/threads_day` — подготовить 5 постов на сегодня и добавить в очередь.
- `/threads_post тема поста` — подготовить один пост.
- `/threads_queue` — показать очередь.
- `/threads_publish id_поста` — опубликовать выбранный пост после подтверждения.
- `/threads_rewrite id_поста` — переделать пост.
- `/threads_skip id_поста` — пропустить пост.
- `/threads_next` — показать следующий draft.

У draft-поста есть inline-кнопки: опубликовать, переделать, пропустить, следующий.

## Threads Growth Agent

Threads Growth Agent включается через `THREADS_GROWTH_MODE_ENABLED=true` и сам поддерживает
не менее `THREADS_MIN_QUEUE_SIZE` сильных viral draft-постов. Если очередь пуста и включён
`THREADS_AUTO_GENERATE_IF_QUEUE_EMPTY=true`, scheduler создаёт проверенный viral post без
зависимости от Ollama. При `THREADS_VIRAL_ONLY=true` команды `/threads_day` и
`/threads_post` также используют только premium viral templates.

Перед сохранением пост проходит safety-проверку и `score_thread_post`: оцениваются хук,
боль владельца, последствие, AI-бот как решение, канал обработки заявки и сильный CTA.
Слабый или нерелевантный текст заменяется viral fallback. Автопостинг выбирает лучший
доступный draft по score, а duplicate guard сравнивает нормализованный текст и первые
160 символов с очередью и публикациями за сегодня.

- `/growth_status` — настройки Growth Agent, размер очереди, публикации и расписание.
- `/growth_refill` — вручную дополнить очередь до заданного минимума уникальными постами.
- `/growth_plan` — темы постов, комментариев, ответов и оффер дня.
- `/engagement_tasks` — ручной чек-лист активности для роста охвата.

Growth Agent не обещает гарантированные просмотры и не использует автоспам, автолайки,
автофолловинг, автокомментарии или серые методы. Engagement-задачи выполняются вручную.

## Viral Threads Agent

Viral Threads Agent помогает получать больше просмотров в Threads и привлекать владельцев
бизнеса на аудит обработки заявок. Контент строится вокруг скорости ответа, потерь в Direct,
WhatsApp и Telegram, ручного переноса лидов в CRM, записи клиентов и забытых follow-up.

Команды `/viral_threads_day`, `/viral_post`, `/threads_day`, `/threads_post` и `/posts`
работают **template-first** и **fallback-first**. Модель `qwen2.5:0.5b` может использоваться
только как дополнительный перефразировщик: недоступность Ollama или слабый ответ не мешают
создать качественный draft. Текст с запрещёнными или нерелевантными направлениями не
сохраняется как готовый пост — вместо него используется проверенный premium fallback.

## Positioning

Проект продаёт только AI-чат-ботов и AI-автоматизацию обработки заявок: AI-администраторов,
AI-менеджеров продаж, ботов для Direct, Telegram и WhatsApp, запись клиентов, CRM-интеграции
и follow-up. Сайты, лендинги, обычные веб-приложения, SEO, SMM и дизайн сайтов не являются
услугами проекта. Если лид запрашивает такую работу, Lead Conversation Agent мягко
переводит разговор к AI-боту для приёма и передачи заявок.

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
PUBLIC_TELEGRAM_BOT_LINK=https://t.me/your_bot_username
THREADS_ACCESS_TOKEN=your_threads_access_token
THREADS_USER_ID=your_threads_user_id
THREADS_API_BASE_URL=https://graph.threads.net
THREADS_AUTO_PUBLISH=false
DATABASE_PATH=./ai_sales_agent.db
LEAD_AUTO_REPLY_ENABLED=true
OWNER_TELEGRAM_ID=
WHATSAPP_CONTACT_LINK=https://wa.me/77712841932
WHATSAPP_PHONE=+77712841932
```

`THREADS_AUTO_PUBLISH=false` — безопасный режим по умолчанию. Публикация только после подтверждения.

`PUBLIC_TELEGRAM_BOT_LINK` добавляет ссылку на Telegram-бота в CTA для Threads-постов. Если переменная пустая, CTA останется без ссылки.

## Threads API

Для публикации нужны `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`, `THREADS_API_BASE_URL`. Если они не настроены, бот будет только готовить посты и держать их в очереди.


## Threads → Telegram → WhatsApp lead flow

- Threads публикует короткие посты про AI-ботов, заявки и автоматизацию.
- CTA в конце Threads-поста ведёт клиента в Telegram-бота для мини-аудита.
- Telegram Lead Conversation Agent задаёт вопросы и квалифицирует клиента по потребности, нише и готовности к следующему шагу.
- Горячий лид получает настроенный WhatsApp-контакт, а владельцу отправляется уведомление через `OWNER_TELEGRAM_ID`.

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
OLLAMA_BASE_URL=http://ollama.railway.internal:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_NUM_CTX=512
OLLAMA_NUM_PREDICT=300
OLLAMA_NUM_THREAD=1
OLLAMA_TEMPERATURE=0.7
OLLAMA_TOP_P=0.9
DATABASE_PATH=/data/ai_sales_agent.db
PUBLIC_TELEGRAM_BOT_LINK=https://t.me/your_bot_username
LEAD_AUTO_REPLY_ENABLED=true
OWNER_TELEGRAM_ID=
WHATSAPP_CONTACT_LINK=https://wa.me/77712841932
WHATSAPP_PHONE=+77712841932
THREADS_ACCESS_TOKEN=your_threads_access_token
THREADS_USER_ID=your_threads_user_id
THREADS_API_BASE_URL=https://graph.threads.net
THREADS_AUTO_POSTING_ENABLED=false
THREADS_AUTO_POSTS_PER_DAY=3
THREADS_AUTO_POST_HOURS=10,14,18
THREADS_AUTO_POST_TIMEZONE=Asia/Almaty
THREADS_AUTO_GENERATE_IF_QUEUE_EMPTY=true
THREADS_DAILY_POST_LIMIT=3
THREADS_GROWTH_MODE_ENABLED=true
THREADS_MIN_QUEUE_SIZE=7
THREADS_VIRAL_ONLY=true
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

- **Вариант A: отдельный Railway Ollama service.** Если Ollama-сервис в Railway называется `ollama`, используйте `OLLAMA_BASE_URL=http://ollama.railway.internal:11434`. Если сервис называется иначе, замените `ollama` на имя своего Railway-сервиса: `http://service-name.railway.internal:11434`. Если Railway показывает другой internal/private URL, используйте именно его.
- **Вариант B: внешний VPS с Ollama.** Запустите Ollama на VPS и укажите публичный/приватный URL VPS в `OLLAMA_BASE_URL`.
- **Вариант C: локальная Ollama не подходит для Railway.** `http://localhost:11434` работает только на вашей машине. На Railway `localhost` будет указывать на сам `ai-sales-agent` контейнер, а не на Ollama.

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

`/health` показывает, что бот работает, модель Ollama, URL Ollama, статус Threads API, включён ли автопостинг, часы публикаций, дневной лимит, количество опубликованных сегодня и количество draft-постов.

### Railway Ollama stability

Если Ollama на Railway падает с:

```text
llama-server process has terminated: signal: segmentation fault
```

то используйте лёгкие настройки:

```env
OLLAMA_MODEL=qwen2.5:0.5b
OLLAMA_NUM_CTX=512
OLLAMA_NUM_PREDICT=300
OLLAMA_NUM_THREAD=1
```

И проверьте командой в Telegram:

```text
/ollama_test
```

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

### 7. Background scheduler автопостинга

Auto scheduler actually runs in background when `THREADS_AUTO_POSTING_ENABLED=true`.

Как это работает:

- автопостинг выключен по умолчанию: `THREADS_AUTO_POSTING_ENABLED=false`;
- для Railway нужно поставить `THREADS_AUTO_POSTING_ENABLED=true` и перезапустить сервис;
- для реальной публикации нужны `THREADS_ACCESS_TOKEN` и `THREADS_USER_ID`;
- без Threads API scheduler не будет публиковать, а только залогирует понятную ошибку;
- scheduler работает в фоне вместе с Telegram-ботом и не блокирует polling;
- каждые 60 секунд проверяет текущее время в `THREADS_AUTO_POST_TIMEZONE`;
- публикует не больше одного поста в один scheduled hour из `THREADS_AUTO_POST_HOURS`;
- публикует не больше `THREADS_DAILY_POST_LIMIT` постов в день;
- бот не делает комментарии, личку, лайки, подписки, автолайки, автоподписки или массовые комментарии;
- публикует только собственные посты из очереди;
- если очередь пустая, может сгенерировать безопасный пост через Ollama, если `THREADS_AUTO_GENERATE_IF_QUEUE_EMPTY=true`.

Важно: автопостинг публикует только собственные подготовленные посты. Бот не пишет комментарии, не пишет в личку, не лайкает и не подписывается.
