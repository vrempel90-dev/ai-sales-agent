# AI Growth Manager for Threads

Это единый AI Growth Manager, а не набор из 25 разрозненных агентов. Он работает как
команда из семи практических ролей: Threads Strategist, Viral Ghostwriter, Hook Maker,
Safe Comment Discovery Agent, Profile Analyst, Sales DM Agent и Content QA.

Бот ведёт Threads-профиль как growth-команда: создаёт и публикует сильные посты,
поддерживает очередь, анализирует механику профилей, готовит безопасные комментарии,
обрабатывает лидов в Telegram и переводит только горячих клиентов в WhatsApp.

Продуктовое позиционирование строго ограничено AI-чат-ботами, AI-администраторами,
AI-менеджерами продаж, автоматизацией Direct / Telegram / WhatsApp, CRM и follow-up.
Сайты, лендинги, SEO, дизайн и обычная веб-разработка не продаются.

Часть старых команд сохранена для совместимости, но основной режим — AI Growth Manager.

## Senior Marketing Brain

AI Growth Manager не просто пишет регулярные посты. Перед попаданием в очередь слой
Senior Marketing Brain проверяет конкретную боль бизнеса, последствие, коммерческий
смысл, сильный оффер, действие AI-бота и CTA в личку. Высокую оценку получает только
контент, который показывает потерю денег, заявки, времени или контроля и объясняет,
как AI-бот отвечает первым, квалифицирует клиента, сохраняет контакт, передаёт лид в
CRM или запускает follow-up.

Каждый пост должен вести по цепочке «доверие → личка → квалифицированный клиент».
Общие SMM-тексты, самореклама в стиле «мы лучшие», случайные темы и абстрактная
автоматизация запрещены. Также запрещён уход в сайты, лендинги, SEO, дизайн и
веб-разработку: фокус остаётся только на AI-чат-ботах, AI-администраторах и обработке
заявок из Direct, Telegram, WhatsApp и CRM.

## Safe Autopilot Growth Agent

Safe Autopilot автоматически:

- поддерживает не меньше `THREADS_MIN_QUEUE_SIZE` качественных draft-постов;
- использует template-first/fallback-first генерацию и не зависит от доступности Ollama;
- выбирает лучший draft по `score_thread_post`;
- публикует по `THREADS_AUTO_POST_HOURS`, если включены API и auto publish;
- после публикации пополняет очередь;
- отбрасывает слабые, короткие, оборванные, нерелевантные и похожие посты;
- отправляет владельцу один growth report в день.

Autopilot **не** делает автолайки, автофолловинг, массовые комментарии, массовые DM,
парсинг пользователей, спам или обход ограничений Meta.

Основные Railway Variables:

```env
THREADS_GROWTH_MODE_ENABLED=true
THREADS_MIN_QUEUE_SIZE=7
THREADS_VIRAL_ONLY=true
THREADS_AUTO_GENERATE_IF_QUEUE_EMPTY=true
THREADS_AUTO_POSTING_ENABLED=true
THREADS_AUTO_PUBLISH=true
GROWTH_AUTOPILOT_ENABLED=true
GROWTH_DAILY_REPORT_ENABLED=true
GROWTH_REPORT_HOUR=21
GROWTH_REPORT_TIMEZONE=Asia/Almaty
```

`/autopilot_status` показывает режим, очередь, публикации, DM/WhatsApp и Comment
Discovery. `/growth_report` показывает публикации, drafts, ошибки и состояние
комментариев. Без `OWNER_TELEGRAM_ID` ежедневный отчёт не отправляется.

## Safe Comment Discovery Agent

В текущем проекте официальный Threads API используется для публикации собственных
постов, но источник официального поиска публичных веток не подключён. Поэтому агент
не обещает фиктивный поиск и не применяет scraping. Он работает queue-first:
владелец передаёт текст или ссылку через `/comment_find`, после чего система оценивает
relevance/risk, создаёт полезные drafts и ждёт подтверждения.

Команды:

- `/comment_discovery_status`
- `/comment_find текст_или_ссылка`
- `/comment_generate текст`
- `/comment_queue`
- `/comment_next`
- `/comment_publish id`
- `/comment_skip id`
- `/comment_report`

По умолчанию `COMMENT_APPROVAL_REQUIRED=true`, `COMMENT_AUTO_REPLY_ENABLED=false`, а
лимит равен трём комментариям в день. Комментарии не содержат ссылок и WhatsApp,
не используют агрессивную продажу, не публикуются в токсичных, политических,
религиозных, медицинских, инвестиционных и других рискованных контекстах.

## Threads Growth Agent Quality

- Growth-пост: 300–700 символов и 2–4 коротких абзаца.
- Обязательны сильная первая строка, боль, последствие, AI-решение и сильный CTA.
- Слабые CTA и оборванные тексты заменяются проверенным viral fallback.
- Public Threads posts никогда не содержат `wa.me`, `WHATSAPP_CONTACT_LINK` или номер
  WhatsApp. WhatsApp используется только после квалификации hot lead в Sales DM Agent.
- `PUBLIC_TELEGRAM_BOT_LINK` используется выборочно, а не в каждом посте.
- Duplicate guard сравнивает нормализованный текст и первые 160 символов.
- Ollama может только дополнительно перефразировать; качество обеспечивает fallback.

## Запуск

```bash
cp .env.example .env
pip install -r requirements.txt
python -m app.main
```

Проверки:

```bash
python -m compileall app
PYTHONPATH=. pytest -q
git diff --check
```

## AI Sales Closing Agent

AI Sales Closing Agent — безопасный автопилот обработки входящих лидов в Telegram/DM.
Он общается как sales-консультант по AI-ботам: определяет нишу и боль, простым языком
показывает ценность автоматизации, задаёт не больше 1–2 квалифицирующих вопросов за
сообщение и оценивает лид как `cold`, `warm` или `hot`.

Агент продаёт только AI-чат-ботов, AI-администраторов, AI-менеджеров продаж,
автоматизацию Direct / Telegram / WhatsApp, обработку и запись заявок, CRM-интеграции
и follow-up. Запросы на сайты, лендинги, веб-приложения, интернет-магазины, SEO,
веб-дизайн и отдельный SMM возвращаются к фокусу на AI-ботах.

Безопасная ценовая логика:

- простой AI-бот / AI-ответчик — от `150 000 ₸`;
- AI-администратор для заявок — `150 000–300 000 ₸`;
- Telegram / WhatsApp / CRM / запись — `300 000–700 000 ₸`;
- сложный AI-агент под бизнес-процессы — от `700 000 ₸`;
- поддержка — `30 000–100 000 ₸/мес`.

Это ориентиры, а не автоматический оффер. Агент не принимает оплату, не обещает
точную цену или сроки без разбора и подтверждения владельца, не гарантирует результат
и не утверждает, что полностью выполнит проект без участия владельца. Если лид готов
покупать, он получает WhatsApp handoff, владельцу через `OWNER_TELEGRAM_ID` уходит
уведомление с нишей, запросом, болью, каналом, бюджетным сигналом, рекомендуемым чеком
и следующим шагом. Краткое summary сохраняется в базе.

Команды владельца:

- `/sales_status` — состояние агента, auto reply, WhatsApp, owner notifications,
  ценовые вилки, hot threshold и последнее summary;
- `/sales_preview текст` — ответ, lead score, следующий шаг и preview уведомления;
- `/dm_preview текст` — совместимый краткий preview на той же Sales Closing logic;
- `/whatsapp_status` и `/lead_mode_status` продолжают работать без изменений.

## Senior SMM & Marketing Director

AI Growth Manager теперь работает не как шаблонный генератор постов, а как внутренний **Senior SMM & Marketing Director** для Threads-страницы.

Он ведёт аккаунт с задачей роста подписчиков, доверия и заявок на AI-ботов:

- чередует контент-цели: awareness, trust, education, pain, proof, objection, offer, founder POV, diagnostic и conversation starter;
- использует живые форматы: наблюдение, диагностика, анти-совет, мини-кейс, разбор ошибки, миф, чеклист, сравнение, личный взгляд, провокация, вопрос к аудитории, мини-аудит, разбор ниши, доверительный пост и прямой оффер;
- хранит content memory для каждого draft/published поста: hook, topic/content_angle, content_format, CTA type, niche, goal, date/created_at, first_sentence через hook и normalized_text;
- не повторяет first_sentence 14 дней, content_angle чаще 48 часов, один format или CTA type больше двух раз подряд;
- отбраковывает банальные SMM-тексты через anti-banal guard `is_not_banal_smm_post`;
- не строит каждый пост по схеме «боль → AI-бот → CTA», а выбирает одну стратегическую цель для каждого поста;
- строит доверие и экспертность, а оффер использует аккуратно, когда аккаунту нужен переход в личку.

Команды `/growth_refill`, `/growth_rebuild`, `/threads_next` и `/growth_report` показывают SMM-логику: format, angle, goal, stage, CTA, риск роботности и рекомендацию SMM-директора.

## Safe Lead Hunter Agent

Safe Lead Hunter Agent помогает безопасно оценивать потенциальных клиентов на AI-чат-ботов, AI-администраторов, Direct/Telegram/WhatsApp-ботов, обработку заявок, запись, CRM-интеграции и follow-up.

Архитектура queue-first/manual-send: пользователь вручную вставляет ссылку на профиль, bio, описание аккаунта, текст поста или список потенциальных клиентов. Агент анализирует текст, определяет нишу, считает lead score 0–100, готовит персональное первое сообщение и сохраняет лида в outreach queue только если score не ниже `LEAD_HUNTER_MIN_SCORE`.

Безопасность:

- нет scraping, browser emulation и обхода ограничений Threads/Meta/Instagram/Telegram;
- нет автолайков, автофолловинга, массовых комментариев и массовых DM;
- `LEAD_HUNTER_AUTO_DM_ENABLED=false` по умолчанию;
- `LEAD_HUNTER_APPROVAL_REQUIRED=true` по умолчанию;
- дневной лимит задаётся `LEAD_HUNTER_DAILY_DM_LIMIT=3`;
- первое сообщение короткое, персональное, без цены, без WhatsApp-ссылки, без давления и гарантий;
- если официальной DM-интеграции нет, `/lead_send id` не имитирует отправку, а переводит лида в `ready_for_manual_send` и показывает текст для ручной отправки.

Команды:

- `/lead_hunter_status` — настройки, лимиты, очередь и последние ошибки;
- `/lead_scan текст` — проверить потенциального клиента и при подходящем score добавить в очередь;
- `/lead_queue` — показать outreach queue;
- `/lead_next` — показать следующий draft;
- `/lead_send id` — подготовить ручную отправку с safety guard и лимитами;
- `/lead_skip id` — пропустить лида;
- `/lead_report` — отчёт по найденным лидам, очереди, отправкам и нишам.

## Lead Outreach Autopilot

Lead Outreach Autopilot — безопасный режим первого касания для лидов из Lead Hunter outreach queue. Он технически умеет обработать одного лида за запуск, проверить score, safety guard, duplicate guard, дневной лимит и наличие разрешённого официального канала DM.

Безопасные значения по умолчанию:

```env
LEAD_HUNTER_AUTOPILOT_ENABLED=false
LEAD_HUNTER_AUTO_DM_ENABLED=false
LEAD_HUNTER_APPROVAL_REQUIRED=true
LEAD_HUNTER_DAILY_DM_LIMIT=3
LEAD_HUNTER_MIN_SCORE=80
LEAD_HUNTER_ALLOWED_CHANNELS=telegram
LEAD_HUNTER_REQUIRE_PERSONALIZATION=true
LEAD_HUNTER_BLOCK_IF_NO_OFFICIAL_CHANNEL=true
```

Что важно:

- автопилот может отправлять первое сообщение только через разрешённый официальный канал, который реально поддерживается проектом;
- сейчас безопасный путь для большинства лидов остаётся manual-send: если у лида нет официального Telegram `chat_id`, лид переводится в `ready_for_manual_send`, а текст показывается владельцу;
- система не имитирует отправку и не помечает лида как `sent`, если официального канала нет;
- `LEAD_HUNTER_AUTO_DM_ENABLED=false` по умолчанию, поэтому авто-DM выключен до явного включения;
- `LEAD_HUNTER_APPROVAL_REQUIRED=true` по умолчанию, поэтому отправка требует подтверждения владельца;
- дневной лимит по умолчанию — 3 сообщения;
- safety guard запрещает WhatsApp-ссылки, цены, агрессивные фразы, одинаковый текст, длинные сообщения и массовый шаблон без персонализации;
- нет scraping;
- нет browser automation, Selenium или Playwright для обхода Threads/Instagram/Meta;
- нет mass DM;
- нет autofollow;
- нет спама;
- нет обхода официальных ограничений Meta/Instagram/Threads;
- нет имитации отправки.

Команды:

- `/lead_autopilot_status` — настройки, лимиты, очередь, наличие официального канала и последние ошибки;
- `/lead_autopilot_on` — owner-only runtime-включение Lead Outreach Autopilot;
- `/lead_autopilot_off` — owner-only runtime-выключение;
- `/lead_autopilot_run` — безопасно обработать максимум 1 лида;
- `/lead_confirm_send id` — owner-only подтверждение отправки конкретного лида;
- `/lead_send id` — если авто-DM выключен или нет официального канала, готовит ручную отправку и ставит `ready_for_manual_send`.

## AI Growth Marketer UX

`AI Growth Marketer` — единый образ Telegram-агента для Threads: маркетолог, SMM-стратег, таргетолог, копирайтер, lead hunter и sales assistant в одном продукте. Главная цель — растить доверие в Threads и получать заявки на AI-ботов / AI-администраторов, которые помогают бизнесу не терять обращения из Direct, WhatsApp, Telegram и CRM.

### Master prompt

Единый master prompt находится в `app/prompts/growth_marketer_master_prompt.py`. Он объединяет роли AI Growth Manager, SMM Director, Viral Ghostwriter, Threads Content Strategist, Comment Agent, Lead Hunter, Lead Outreach Agent, Sales Closing Agent, Safety Guard и Daily Report Analyst. Старые agent-команды сохранены, но генерация промтов идёт через общий AI Growth Marketer контекст и короткие task instructions.

### Human commands и daily flow

Главное меню Telegram сокращено до человеческих команд:

- `/start` — главное меню
- `/today` — отчёт за сегодня
- `/plan` — план на день
- `/content` — контент
- `/leads` — клиенты
- `/sales` — продажи
- `/status` — автопилот
- `/system` — система
- `/next_post` — следующий пост
- `/next_lead` — следующий лид

Ежедневный сценарий:

1. Утром открыть `/plan`.
2. Днём проверить `/content` и `/leads`.
3. Если клиент ответил — вставить сообщение в `/sales_preview` или `/dm_preview`.
4. Вечером открыть `/today`.

### Menu structure и aliases

Разделы `/content`, `/leads`, `/sales`, `/system` показывают короткие UX-меню с командами следующего шага. Добавлены human aliases: `/today` → `/growth_report`, `/plan` → `/growth_plan`, `/status` → `/autopilot_status`, `/next_post` → `/threads_next`, `/posts` → `/threads_queue`, `/refill` → `/growth_refill`, `/rebuild` → `/growth_rebuild`, `/find_leads` → безопасная инструкция поиска, `/next_lead` → `/lead_next`.

### Совместимость и проверка после deploy

Старые команды сохранены: `/health`, `/ollama_test`, `/growth_report`, `/growth_plan`, `/autopilot_status`, `/threads_next`, `/threads_queue`, `/lead_scan`, `/lead_queue`, `/lead_next`, `/lead_report`, `/sales_preview`, `/dm_preview`, `/sales_status`, `/whatsapp_status` и технические команды автопилотов. После deploy проверьте `/start`, затем `/plan`, `/content`, `/leads`, `/sales`, `/status`, `/system`, `/today`, `/next_post` и `/next_lead`.

## Autonomous Threads Growth Agent

Autonomous Threads Growth Agent — единый AI Growth Marketer для Threads: SMM Director, Content Agent, Threads Scout, Threads Cleaner, Comment Agent, Lead Hunter, Outreach Agent, Sales Agent, Safety Guard и Daily Report Analyst в одном безопасном runtime-агенте.

Что агент делает сам при включённом автономном режиме:
- ведёт Threads-аккаунт вокруг цели заявок на AI-ботов и AI-администраторов;
- планирует 3 поста в день: утро — боль/наблюдение, день — экспертность/ошибка, вечер — оффер/CTA;
- ищет релевантные Threads по нишам Алматы/Казахстан: салоны, маникюр, косметологи, стоматологии, клиники, барбершопы, массаж, онлайн-школы, эксперты и локальные услуги;
- чистит мусор: личные посты без бизнеса, мемы, политика, токсичные споры, знакомства, повторы и темы без outreach angle;
- считает lead score, готовит комментарии и первые DM;
- в live mode может комментировать/писать DM только при включённых флагах, рабочих часах, лимитах, duplicate guard и safety guard.

Telegram не является control center для ручного подтверждения каждого действия. Он используется только для статуса, ежедневных отчётов, аварийных уведомлений и включения/выключения агента.

Безопасные defaults:
- `AUTONOMOUS_THREADS_AGENT_ENABLED=false` — агент не включается без решения владельца;
- `AUTONOMOUS_THREADS_AGENT_AUTO_START=false` — после redeploy не стартует сам, пока владелец явно не включит auto start;
- `AUTONOMOUS_THREADS_AGENT_DRY_RUN=true` — по умолчанию ничего не публикует и не отправляет;
- `AUTONOMOUS_THREADS_COMMENTS_ENABLED=false` и `AUTONOMOUS_THREADS_DMS_ENABLED=false` — live comments/DM выключены;
- `AUTONOMOUS_THREADS_BROWSER_MODE=false` — browser automation выключен.

Как включить:
1. Для анализа без live-действий установите `AUTONOMOUS_THREADS_AGENT_ENABLED=true` и оставьте `AUTONOMOUS_THREADS_AGENT_DRY_RUN=true`.
2. Для autostart после Railway redeploy добавьте `AUTONOMOUS_THREADS_AGENT_AUTO_START=true`.
3. Для live comments/DM отдельно включите `AUTONOMOUS_THREADS_COMMENTS_ENABLED=true`, `AUTONOMOUS_THREADS_DMS_ENABLED=true`, `AUTONOMOUS_THREADS_AGENT_DRY_RUN=false` и настройте browser layer.
4. Команды владельца: `/agent_on`, `/agent_off`, `/agent_dry_run_on`, `/agent_dry_run_off`, `/agent_run_once`.
5. Статус и отчёты: `/agent_status`, `/agent_report`, `/agent_plan`, `/agent_history`.

Browser automation — optional layer. Если зависимости браузера или сессия Threads не настроены, основной Telegram-бот не ломается, команды честно показывают `Browser mode is not configured`, а daily report пишет, что autonomous live actions unavailable. Пароли не хранятся в коде: используйте только env/secrets/cookies/session storage, добавленные владельцем. Агент не обходит captcha/checkpoint/login verification.

Stop conditions:
- captcha;
- checkpoint;
- rate limit;
- action blocked;
- login issue;
- предупреждение аккаунта.

При stop condition агент останавливается, сохраняет причину и уведомляет владельца при включённых уведомлениях. Он не пытается решать captcha, обходить защиту или продолжать действия.

Limits и anti-spam:
- daily scans/comments/DM ограничиваются env-переменными;
- no mass DM;
- no fake sending;
- no duplicate comments;
- no duplicate DMs;
- один профиль нельзя контактировать повторно минимум 14 дней;
- первый touch без ссылок и без цены.

Daily report в 21:00 Asia/Almaty включает контент, поиск, мусор, релевантные ветки, comments sent/prepared/skipped, DM sent/closed/skipped/manual unavailable, лиды, ошибки и рекомендацию на завтра.

## Threads Browser Layer (controlled live comments)

The Autonomous Threads Growth Agent now has an optional Playwright browser layer for Threads web. It is safe by default: `AUTONOMOUS_THREADS_BROWSER_MODE=false`, `AUTONOMOUS_THREADS_COMMENTS_ENABLED=false`, `AUTONOMOUS_THREADS_DMS_ENABLED=false`, and `AUTONOMOUS_THREADS_AGENT_DRY_RUN=true`.

### Railway Playwright setup

Railway needs two separate pieces for the Threads Browser Layer: the Python package from `requirements.txt` (`playwright`) and the actual Chromium browser binary. Having only the Python package is not enough; `/agent_browser_test` will report `browser_unavailable` when Chromium or its system libraries are missing.

This repository installs Chromium at build time for both supported deploy styles:

- `Dockerfile` runs `python -m playwright install --with-deps chromium` after `pip install -r requirements.txt`.
- `nixpacks.toml` runs `python -m playwright install chromium` during the Nixpacks install phase.

Keep `AUTONOMOUS_THREADS_BROWSER_HEADLESS=true` on Railway. The browser launches with container-safe flags: `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`, and `--disable-setuid-sandbox`. If browser launch still fails, the bot must continue to start normally; use `/agent_browser_status` or `/agent_browser_test` and check `last browser error` for the short reason, for example missing browser binaries, missing system dependencies, launch timeout, sandbox issue, or permission issue.

1. Install Python dependencies from `requirements.txt`.
2. Install Playwright browsers during the build/install phase if your Railway image does not already include Chromium:
   ```bash
   python -m playwright install chromium
   ```
   If the image is missing OS libraries and permits dependency installation, use:
   ```bash
   python -m playwright install --with-deps chromium
   ```
3. Configure one session source; the bot never stores or asks for a Threads password:
   - `AUTONOMOUS_THREADS_COOKIES_JSON` — exported cookies from an already-authorized web session.
   - `AUTONOMOUS_THREADS_SESSION_FILE` — Playwright storage-state JSON path.
   - `AUTONOMOUS_THREADS_USER_DATA_DIR=/tmp/threads-profile` — persistent profile directory, preferably backed by a Railway volume.
4. First keep `AUTONOMOUS_THREADS_AGENT_DRY_RUN=true` and run `/agent_browser_test`; if it says `browser_unavailable`, read `last browser error` before changing live-action flags.
5. To allow one live comment per run, set `AUTONOMOUS_THREADS_AGENT_DRY_RUN=false`, `AUTONOMOUS_THREADS_BROWSER_MODE=true`, `AUTONOMOUS_THREADS_COMMENTS_ENABLED=true`, provide a valid session, and keep `AUTONOMOUS_THREADS_DMS_ENABLED=false`.

New owner commands:

- `/agent_browser_status` — dependency, session, readiness, login-state and stop-reason status.
- `/agent_browser_test` — safe home-page/session test; it never comments and never sends DMs.

Live comments are gated by dry-run off, browser mode on, comments enabled, configured session, Playwright readiness, score threshold, safety checks, duplicate history, daily limit, and absence of captcha/checkpoint/rate-limit/action-blocked/login issues. If no session is configured, the layer reports `session not configured` and dry-run still works. If Threads shows captcha, checkpoint, rate limit, action blocked, suspicious activity, session expiry, login issue, or selector/interface changes, the agent stops and records the reason; it does not try to bypass protections.

Live DMs are intentionally not implemented. Even if `AUTONOMOUS_THREADS_DMS_ENABLED=true`, the agent reports: `Live DM is not implemented yet. DM remains disabled/manual.`
