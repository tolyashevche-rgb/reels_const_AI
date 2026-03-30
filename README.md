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
| Knowledge Base | ChromaDB (RAG, локально) |
| LLM (creative / script) | Claude Sonnet 4.6 |
| LLM (simple / structured) | Claude Haiku 4.5 |
| Video Search | TwelveLabs |
| TTS (voice-over) | ElevenLabs / OpenAI TTS |
| Trim / Normalize | FFmpeg |
| Render / Compose | Creatomate API |
| Queue / Jobs | Redis + Celery |
| Infrastructure | NETX VPS |

---

## Інфраструктура NETX (1 сервер MVP)

```
┌─────────────────────────────────────────────────────┐
│  NETX Server — All-in-One Node (VPS NVMe)           │
│  FastAPI · LangGraph · Redis · Celery · Auth        │
│  PostgreSQL · ChromaDB · backups                    │
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

*Де*: NETX Server

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

*Де*: NETX Server

---

### C.1 — AI Model Selection (по вузлах)

| Вузол | Модель | Причина |
|---|---|---|
| `input_normalizer` | **Claude Haiku 4.5** | Проста задача: очистка і нормалізація тексту |
| `audience_intent_analysis` | **Claude Haiku 4.5** | Класифікація + structured JSON output |
| `retrieve_marketing_knowledge` | — | RAG, не LLM виклик |
| `retrieve_child_dev_knowledge` | — | RAG, не LLM виклик |
| `script_writer` | **Claude Sonnet 4.6** | Творча задача, якість тексту = цінність продукту |
| `policy_review` | **Claude Haiku 4.5** | Чітке слідування правилам, низька температура |
| `shot_planner` | **Claude Haiku 4.5** | Структурований JSON output, логічна задача |
| `asset_selector` | **Claude Haiku 4.5** | Вибір з переліку, не творча задача |

**Логіка вибору моделі:**

| Тип задачі | Модель | Коли використовувати |
|---|---|---|
| Творчість, якість тексту | Claude Sonnet 4.6 | Коли результат — це продукт (script) |
| Структура, класифікація, JSON | Claude Haiku 4.5 | Коли задача чітко визначена |
| Правила, безпека, перевірка | Claude Haiku 4.5 | Low temp + чіткі інструкції важливіше за потужність |

**Чому тільки Claude:**
- Один API ключ, один SDK (`langchain-anthropic`) — простіший код і білінг
- Haiku 4.5 чудово слідує інструкціям — критично для `policy_review` і JSON вузлів
- Sonnet 4.6 для `script_writer` — якість сценарію це ядро продукту, економити тут недоцільно
- Контекст 200K у всіх моделях — зручно для RAG chunks

**Орієнтовна вартість 1 запиту: ~$0.01–0.03**

*Резервний варіант*: якщо якість script_writer достатня — можна понизити до Haiku 4.5 (~$0.005/запит).

---

### D — Knowledge Base / RAG (ChromaDB)

*Що зберігає*

| Колекція | Зміст |
|---|---|
| `marketing_knowledge` | Книги продажів, hooks, CTA, storytelling, сприйняття соцмереж |
| `child_dev_knowledge` | Книги та матеріали фахівців розвитку 0–6 |
| `editorial_guide` | Внутрішній tone-of-voice, формати, стилі |
| `safe_claims` | Дозволені твердження |
| `banned_claims` | Заборонені / ризикові твердження |

*Джерела*: папка `files/` — PDF, TXT, DOCX, EPUB книг та матеріалів.
Скрипт індексації розбиває книги на chunks → генерує embeddings → зберігає в ChromaDB.

*Технічно*: LangGraph + ChromaDB (локальна vector DB, $0).
Метадані кожного chunk: `source`, `author`, `trust_level`, `topic`, `age_range`, `collection`.

*Файлова структура*:
```
files/
  marketing/         ← книги з продажів, SMM, психології
  child_dev/         ← книги з дитячого розвитку
  editorial/         ← tone guide, стилі, правила
chroma_db/           ← локальна база ChromaDB (автоматично)
```

*Де*: NETX Server (локально, без зовнішніх сервісів)

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

*Де*: NETX Server

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

*Де*: NETX Server

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

*Де*: NETX Server

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

*NETX частина*: оригінали зберігані на NETX Server, trim-результати теж.

---

### I — Trim / Normalize Worker (FFmpeg)

*Що робить*:
- trim по timestamps від TwelveLabs
- scale/normalize відео
- bitrate normalization
- subtitle timing prep
- rough cut concatenation

*Де*: NETX Server

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

*NETX частина*: готові audio файли зберігаються у `/voiceovers/` на NETX Server.

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
| NETX Server (All-in-One) | per plan |

Головна витрата — LLM + рендери. NETX фіксована оренда.

---

## Оптимізації витрат

- Зменшити кількість LLM-викликів: pipeline з 4 на 2 → -50% витрат
- Кешувати hook / brief для схожих тем → до -70%
- Для простих вузлів використовувати дешевші моделі (gpt-4o-mini)
- TwelveLabs індексувати один раз, пошук — дешевий
- Creatomate: шаблони замість повного JSON-рендеру кожного разу
