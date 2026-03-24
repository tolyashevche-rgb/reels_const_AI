# Reels Construction AI — MVP Architecture

Система для автоматичної генерації коротких відео (Reels) на теми дитячого розвитку 0–6 років.
Користувач вводить тему — система проходить повний pipeline: аналіз → сценарій → підбір відео → монтаж → озвучка → preview → редагування.

---

## Стек (коротко)

| Шар | Технологія |
|---|---|
| Web / Cabinet | Laravel + MySQL |
| API Gateway | Python FastAPI |
| Orchestrator | LangGraph |
| Knowledge Base | PostgreSQL + pgvector (RAG) |
| LLM (script / review) | Claude 3.5 Haiku |
| LLM (intent / structure) | GPT-4o-mini |
| LLM (normalizer) | Gemini 1.5 Flash |
| Video Search | TwelveLabs |
| TTS (voice-over) | ElevenLabs / OpenAI TTS |
| Trim / Normalize | FFmpeg |
| Render / Compose | Creatomate API |
| Queue / Jobs | Redis + Celery |
| Infrastructure | NETX VPS |

---

## Інфраструктура NETX (3 сервери MVP)

```
┌─────────────────────────────────────────────────────┐
│  NETX Server 1 — App Node (VPS NVMe)                │
│  FastAPI · LangGraph · Redis · Celery · Auth        │
├─────────────────────────────────────────────────────┤
│  NETX Server 2 — DB Node (VPS SSD)                  │
│  PostgreSQL · pgvector · backups                    │
├─────────────────────────────────────────────────────┤
│  NETX Server 3 — Media Node (VPS dedicated storage) │
│  FFmpeg workers · raw media · previews · finals     │
└─────────────────────────────────────────────────────┘

Зовнішні сервіси (API):
  TwelveLabs · Anthropic (Claude) · OpenAI · Google (Gemini) · ElevenLabs · Creatomate
```

---

## Модулі системи

### A — Frontend / Cabinet (Laravel)

*Що робить*
- Форма вводу: тема, мова, тривалість, стиль, аудиторія
- Кабінет: список проєктів, статуси, history версій
- Preview відео прямо у браузері
- Редагування: текст, кадри, музика, голос
- Export готового ролика

*Де*: окремий Laravel-сервер або NETX Server 1 (на старті разом з App Node)

---

### B — API Gateway (FastAPI)

*Що робить*
- Приймає запити від Laravel
- Створює project / render job в БД
- Запускає LangGraph pipeline через Celery
- Повертає статуси (processing / done / failed) через webhook

*Endpoints*:
```
POST   /api/v1/render              — створити задачу
GET    /api/v1/render/{task_id}    — статус задачі
POST   /api/v1/render/{task_id}/edit — редагувати версію
GET    /api/v1/projects/{id}       — дані проєкту
POST   /api/v1/callback/render     — webhook до Laravel
```

*Де*: NETX Server 1

---

### C — Orchestrator (LangGraph)

*Що робить*
- Керує вузлами pipeline зі збереженням state / checkpoints
- Дозволяє rerun окремих вузлів без повного перезапуску
- Підтримує human-in-the-loop (review перед рендером)

*Граф вузлів*:
```
[User Input]
     │
     ▼
[1. input_normalizer]       ← нормалізація теми, мови, стилю
     │
     ▼
[2. audience_intent_analysis]  ← емоція, біль, тип рілза
     │
     ├──▶ [3a. retrieve_marketing_knowledge]   ┐
     │                                          ├──▶ [4. script_writer]
     └──▶ [3b. retrieve_child_dev_knowledge]   ┘
                                                       │
                                                       ▼
                                               [5. policy_review]  ← безпека, точність
                                                       │
                                                       ▼
                                               [6. shot_planner]   ← shot list + таймінги
                                                       │
                                                       ▼
                                               [7. twelvelabs_search]  ← пошук відеосегментів
                                                       │
                                                       ▼
                                               [8. asset_selector]     ← відбір кліпів
                                                       │
                                                       ▼
                                               [9. voiceover_generate] ← TTS
                                                       │
                                                       ▼
                                               [10. render_compose]    ← Creatomate / FFmpeg
                                                       │
                                                       ▼
                                               [11. preview_publish]   ← preview на media storage
                                                       │
                                                       ▼
                                               [Human Edit / Re-render]
```

*Де*: NETX Server 1

---

### C.1 — AI Model Selection (по вузлах)

| Вузол | Модель | Причина |
|---|---|---|
| `input_normalizer` | Gemini 1.5 Flash | Проста задача, найдешевший ($0.075/1M) |
| `audience_intent_analysis` | GPT-4o-mini | Класифікація, структурований output ($0.15/1M) |
| `retrieve_marketing_knowledge` | — | RAG, не LLM виклик |
| `retrieve_child_dev_knowledge` | — | RAG, не LLM виклик |
| `script_writer` | **Claude 3.5 Haiku** | Якість письма, довгий structured текст ($0.80/1M in) |
| `policy_review` | **Claude 3.5 Haiku** | Точне слідування правилам, безпека дитячого контенту |
| `shot_planner` | GPT-4o-mini | JSON output, проста структура |
| `asset_selector` | GPT-4o-mini | Вибір з переліку, не творча задача |

**Чому Claude 3.5 Haiku для script + review:**
- Краща якість довгих структурованих текстів ніж GPT-4o-mini
- Точніше дотримується системних інструкцій (критично для policy_review)
- Дешевший за Claude Sonnet у 4x, але якість значно вища за mini-моделі
- Контекст 200K — зручно для RAG chunks

**Орієнтовна вартість 1 запиту при такому міксі: ~$0.02–0.05**

*Резервний варіант*: якщо бюджет дуже обмежений — `script_writer` на GPT-4o-mini (~$0.005/запит, але нижча якість тексту).

---

### D — Knowledge Base / RAG

*Що зберігає*

| База | Зміст |
|---|---|
| marketing_knowledge | Книги продажів, hooks, CTA, storytelling, сприйняття соцмереж |
| child_dev_knowledge | Книги та матеріали фахівців розвитку 0–6 |
| editorial_guide | Внутрішній tone-of-voice, формати, стилі |
| safe_claims | Дозволені твердження |
| banned_claims | Заборонені / ризикові твердження |

*Технічно*: embeddings + pgvector. Метадані: source, author, trust_level, topic, age_range.

*Де*: NETX Server 2 (PostgreSQL + pgvector)

---

### E — Primary Database (PostgreSQL)

*Таблиці*:
```
users
projects
project_versions
briefs
scripts
knowledge_sources
retrieval_logs
shots
assets
voice_tracks
music_tracks
render_jobs
render_outputs
edit_actions
```

*Де*: NETX Server 2

---

### F — Media Storage

*Структура*:
```
/raw_uploads/          ← завантажені вихідні відео
/indexed_candidates/   ← кліпи від TwelveLabs
/trimmed_clips/        ← нарізані нормалізовані сегменти
/voiceovers/           ← згенерований голос
/music/                ← фонова музика
/preview_renders/      ← preview для UI
/final_renders/        ← готовий ekspor
/templates/            ← render JSON templates
```

*Де*: NETX Server 3 (VPS with dedicated storage)

---

### G — Queue / Background Jobs

*Що запускає в background*:
- embeddings для нових документів
- TwelveLabs indexing / search
- TTS генерація
- FFmpeg trim/normalize
- Creatomate render / re-render
- cleanup старих файлів

*Стек*: Redis + Celery

*Де*: NETX Server 1 (Redis), NETX Server 3 (Celery FFmpeg workers)

---

### H — Video Search (TwelveLabs)

*Що робить*:
- Upload + індексація відеобібліотеки через API
- Semantic пошук сегментів за змістом shot list
- Повертає timestamps (start/end) релевантних фрагментів

*Flow*:
```
shot plan → TwelveLabs search API → candidates list
         → asset selector → trim via FFmpeg (Media Node)
```

*NETX частина*: оригінали зберігані на Media Node, trim-результати теж.

---

### I — Trim / Normalize Worker (FFmpeg)

*Що робить*:
- trim по timestamps від TwelveLabs
- scale/normalize відео
- bitrate normalization
- subtitle timing prep
- rough cut concatenation

*Де*: NETX Server 3

---

### J — Render / Compose (Creatomate)

*Що робить*:
- складає сцени з кліпів
- накладає текст / субтитри
- підставляє voice-over
- підставляє фонову музику
- анімації / переходи
- рендерить preview і final (9:16)

*Flow*:
```
shot list + assets + timings + voice_duration
    → render JSON template
    → Creatomate API
    → відео файл → media storage → preview URL
```

---

### K — Voice-over (TTS)

*Що робить*:
- генерує голос по фінальному сценарію
- повертає audio duration (для перерахунку таймінгів)
- версійність голосів (зміна голосу в editor)

*Сервіс*: ElevenLabs / OpenAI TTS

*NETX частина*: готові audio файли зберігаються у `/voiceovers/` на Media Node.

---

### L — Revision / Editable Project Model

Система зберігає не просто mp4, а повний стан проєкту:

```json
{
  "project_id": "...",
  "version": 3,
  "brief": { "topic": "...", "audience": "0-3", "emotion": "joy" },
  "script": { "hook": "...", "body": "...", "cta": "..." },
  "shot_list": [ { "order": 1, "description": "...", "duration_sec": 3 } ],
  "assets": [ { "shot_id": 1, "clip_path": "...", "start": 0.5, "end": 3.5 } ],
  "voice_track": "...",
  "music_track": "...",
  "text_overlays": [ { "time": 0, "text": "...", "style": "..." } ],
  "render_template": { ... }
}
```

Редагуючи будь-який блок, система перезапускає тільки потрібні вузли LangGraph.

---

## Повний Pipeline Flow

```
1. Користувач вводить тему на Laravel
2. Laravel POST /api/v1/render → FastAPI
3. FastAPI створює project + job у PostgreSQL
4. Celery запускає LangGraph pipeline
5. LangGraph:
   a. Нормалізує тему
   b. Аналізує аудиторію / емоцію / тип
   c. Витягує знання з RAG (marketing + child_dev)
   d. Генерує hook + script + CTA через LLM
   e. policy_review node — перевірка безпеки
   f. Будує shot list з таймінгами
   g. TwelveLabs знаходить відеосегменти
   h. FFmpeg worker нарізає / нормалізує кліпи
   i. TTS генерує voice-over (повертає duration)
   j. Creatomate збирає preview
6. Preview зберігається на Media Node
7. FastAPI webhook → Laravel: status=done, preview_url
8. Користувач дивиться preview в кабінеті
9. Опціонально редагує (текст / кадр / музика / голос)
10. Система re-renders тільки змінені вузли
11. Final export
```

---

## Обмін Laravel ↔ Python

**Laravel → Python**:
- `POST /api/v1/render` — `{ topic, duration, language, style, user_id }`
- `POST /api/v1/render/{task_id}/edit` — `{ field, value }`

**Python → Laravel**:
- Webhook: `{ task_id, status, preview_url, version }`
- Статуси: `queued` / `processing` / `review_needed` / `done` / `failed`

---

## Запуск (локально / dev)

```powershell
cd C:\Users\LocalAdmin\Documents\reels_const_AI
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8080
```

Redis (окремо):
```powershell
redis-server
```

Celery worker:
```powershell
celery -A app.worker worker --loglevel=info
```

---

## MVP Етапи (не все одразу)

**MVP 1 — Content Engine**
> Тема → hook → сценарій → shot list → текст оверлеїв → CTA
> Без монтажу. Перевіряє цінність ядра.

**MVP 2 — Semi-auto Video**
> + TwelveLabs пошук + FFmpeg rough cut + Preview
> Користувач редагує вручну.

**MVP 3 — Full Construction**
> + Creatomate рендер + TTS + editor + re-render + export variants

---

## Бюджет орієнтовно (50 users / 5 req/day)

| Стаття | ~ ціна/міс |
|---|---|
| LLM (OpenAI / Gemini) | $150–300 |
| TwelveLabs | за індексацію + пошук |
| TTS (ElevenLabs) | $22–99 |
| Creatomate | за рендери |
| NETX Server 1 (App) | per plan |
| NETX Server 2 (DB) | per plan |
| NETX Server 3 (Media) | per plan |

Головна витрата — LLM + рендери. NETX фіксована оренда.

---

## Оптимізації витрат

- Зменшити кількість LLM-викликів: pipeline з 4 на 2 → -50% витрат
- Кешувати hook / brief для схожих тем → до -70%
- Для простих вузлів використовувати дешевші моделі (gpt-4o-mini)
- TwelveLabs індексувати один раз, пошук — дешевий
- Creatomate: шаблони замість повного JSON-рендеру кожного разу
