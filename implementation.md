# AI Web Platform – Implementation Plan (V1)

## Project Structure

```
E:\Socrates\backend\
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── users/              # Auth, profiles, settings
├── chat/               # Conversations, messages, streaming
├── ai/                 # Model loading, prompt builder, inference
├── memory/             # Long-term memory, summaries
├── files/              # Uploads, PDF text extraction
├── manage.py
└── requirements.txt
```

## Django Apps & Models

### `users` — Custom User model
- `User(AbstractUser)` — email, avatar, bio, settings (JSON), timestamps
- JWT auth via `simplejwt` (register/login/refresh/logout/me endpoints)

### `chat` — Conversations & Messages
- `Conversation` — FK→User, title, timestamps
- `Message` — FK→Conversation, role (`user`/`assistant`/`system`), content, tokens_used, timestamp
- Endpoints: CRUD conversations, list/create messages, **stream response**

### `ai` — Model orchestration (no DB models)
- `model_loader.py` — Load GGUF once at server startup, hold in memory
- `prompt_builder.py` — Assemble prompt: system instructions + memory context + chat history + user query
- `inference.py` — Call `llama-cpp-python`, yield tokens for streaming
- `memory_retriever.py` — Fetch relevant memories from memory app
- Endpoints: `POST /api/ai/generate` (non-streaming), `POST /api/ai/stream` (SSE)

### `memory` — Long-term memory & summaries
- `Memory` — FK→User, key, content (text), importance (float), timestamps
- `ConversationSummary` — FK→Conversation, summary (text), timestamps
- `memory_manager.py` — CRUD + relevance search (basic keyword/cosine similarity)
- `summarizer.py` — Use the model to summarize conversations (scheduled or on-demand)

### `files` — File uploads & processing
- `UserFile` — FK→User, file URL (Supabase Storage ref), file_type, original_name, extracted_text (nullable), FK→Conversation (nullable), timestamp
- Upload → store in Supabase Storage → extract text (PyMuPDF for PDFs) → return metadata
- Endpoints: upload, delete, get extracted text

## API Endpoints

| Prefix | Endpoints |
|---|---|
| `/api/auth/` | `register`, `login`, `refresh`, `logout`, `me` (GET+PATCH) |
| `/api/chat/` | `conversations` (CRUD), `conversations/:id/messages` (list+create), `conversations/:id/stream` (SSE) |
| `/api/ai/` | `generate` (POST), `stream` (POST) |
| `/api/memory/` | `memories` (CRUD + `?search=` query) |
| `/api/files/` | `upload` (POST), `files/:id` (DELETE), `files/:id/text` (GET) |

## Key Dependencies

```
Django>=5.0
djangorestframework>=3.15
djangorestframework-simplejwt>=5.3
django-cors-headers>=4.3
django-environ>=0.11
psycopg2-binary>=2.9
gunicorn>=22.0
llama-cpp-python>=0.2
PyMuPDF>=1.23
Pillow>=10.0
```

## Implementation Order

| Step | What | Details |
|---|---|---|
| 1 | Scaffold | `django-admin startproject`, create apps, install deps, env setup |
| 2 | Settings | DB (Supabase), JWT, CORS, env vars, storage backend |
| 3 | Users app | Custom User model, serializers, RegisterView, LoginView, MeView |
| 4 | Chat app | Conversation/Message models, serializers, CRUD views, streaming view |
| 5 | AI app | Model loader (singleton), prompt builder, inference wrapper, streaming endpoint |
| 6 | Memory app | Memory model, memory manager (CRUD + relevance), summary model |
| 7 | Files app | UserFile model, Supabase storage adapter, upload view, PDF parser |
| 8 | Wire URLs | Central routing in `config/urls.py` |
| 9 | Deployment | Railway config (`Procfile`, `gunicorn`, env vars) |

## Design Principles

- **Model independent of frontend** — DRF API is the contract; Next.js just consumes JSON/SSE
- **Memory independent of model** — `memory_retriever.py` queries the memory app; `prompt_builder.py` feeds it into context. Swap model without touching memory
- **Swappable GGUF** — `model_loader.py` reads model path from env var; any GGUF works as long as prompt format is adjusted in `prompt_builder.py`
- **CPU→GPU upgrade path** — No frontend or DB changes needed; just change the host and env vars
