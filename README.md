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
