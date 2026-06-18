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
