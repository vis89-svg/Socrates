# Socrates — Project Summary

AI chat platform with deep-research pipeline. Django 6 + DRF backend, vanilla-JS single-file frontend, Supabase Postgres, OpenRouter + local llama.cpp models.

---

## 1. Timeline — What Was Built (Day 1 → Now)

### Foundation (5 commits)
| Commit | Established |
|---|---|
| `first commit` | Django + DRF skeleton: users/chat/ai/memory/files apps, JWT auth |
| `Base structure` | REST API: conversations/messages CRUD, SSE streaming, file upload, memory CRUD |
| `v1 model` | Local llama.cpp (`qwen2.5-3b`), inference, prompt builders, tool router |
| `Model config & polishing` | `models.json` routing (OpenRouter gemma-4-26b for planner/chat/extract/reasoning, cohere coding, local qwen fallback), feature flags, search providers (Tavily/Exa/Brave/DDG), retrieval profiles, golden facts, verifier, agent loop, observability |
| `01 persistent memory` | Memory model + Postgres FTS (`SearchVector`/`SearchRank`), conversation summarizer, memory retriever |

### Subsequent work phases
| Phase | Built / Fixed |
|---|---|
| Verification | Golden facts verified (NVIDIA founded 1993 etc.), retrieval profiles, corpus; 58 tests green |
| P5 UI | Clickable citations (`[Source N]` → URLs), source domain names, confidence badges (High/Medium/Low/None), Research Summary + Timings SSE events, evidence panel |
| Pipeline performance | Fixed `trace_pipeline` command, reworked `PipelineTracer`, robust `_parse_json`/`_repair_json`, removed blind all-null retry, model routing fix. **Full pipeline 523s → 190s** |
| Tables/Export/Share | Table Copy (TSV) + CSV buttons; Word export (python-docx); PDF export (PyMuPDF Story); conversation sharing (UUID token, public page + JSON API, revocable) |
| Edit fix | Edit → Save now regenerates the answer (`regenerate_message_id`), `streamReply()` frontend refactor |
| Request performance | DB connection pooling, N+1 fix, parallel frontend bootstrap, scrypt hashing. **Login 4302ms → ~700ms** |

---

## 2. Problems Existed → Problems Solved

| # | Problem | Root cause | Solution |
|---|---|---|---|
| 1 | Extraction returned all-null JSON, failed twice, **wasted 288s** | LLM returned invalid/unfenced JSON; blind retry on null | Robust `_parse_json` (balanced-brace scan, fence strip) + `_repair_json` + removed blind retry |
| 2 | Local qwen generation ~**900s** for deep research | Default model routed to local 3B CPU model | Default model_key `'default'`→`'chat'` (OpenRouter gemma) — generation **100s→33s** |
| 3 | Free-tier OpenRouter **silently returned 0 tokens** | Empty response on rate limit/cost | Retry chain `[model_key, model_key, 'fallback']` + extractor exponential backoff honoring `Retry-After` |
| 4 | `trace_pipeline` command crashed | `FeatureFlags._defaults` AttributeError | Use `settings.ENABLE_PIPELINE_TRACE` |
| 5 | Trace timings wrong | `_start_times` dict bug | `PipelineTracer` reworked (`_last_timed`, `finish()`, `stage_durations()`) |
| 6 | **Edit didn't regenerate** — edited query left with no reply | PATCH deleted later messages; frontend only reloaded | `regenerate_message_id` in `StreamView`; PATCH → reload → `streamReply()` |
| 7 | Tables/citations vanished from chat bubble | `bubble.textContent = fullResponse` clobbered markdown HTML | Fallback text only when response empty |
| 8 | **Every API call ~1.5s slower** | `CONN_MAX_AGE=0` → new TLS connection to remote Supabase per request | `CONN_MAX_AGE=60` + `CONN_HEALTH_CHECKS=True` |
| 9 | **Login 4.3s** | PBKDF2 password check 996ms + 5 sequential round trips | Scrypt (347ms, auto-upgrade) + parallel `fetchUser()`/`loadConversations()` + reuse messages from detail |
| 10 | Conversation list N+1 (2 queries per conv) | Serializer `messages.last()` + `.count()` per object | `Count()` + last-message `Subquery` annotations |
| 11 | Redundant round trip on chat open | Detail + messages fetched separately | Messages rendered from detail response |
| 12 | PDF export unusable | PyMuPDF 1.28 broke `Story.place/draw/write`; `insert_htmlbox` scales to 1 page | `Story(...).write_with_links(rectfn)` — multi-page works |
| 13 | Word export missing | python-docx not installed | Added `python-docx==1.2.0` |
| 14 | Share links hardcoded localhost | No public base URL | `PUBLIC_BASE_URL` env setting |
| 15 | Trace runs timed out (900s+) | Slow pipeline | Phase 3 fixes: trace4 = **190s** total, extraction 17/17 fields |
| 16 | Duplicate user message on edit-regenerate | StreamView always created a user message | `regenerate_id` path skips creation |

---

## 3. Production Optimizations (before → after)

| # | Optimization | Before | After |
|---|---|---|---|
| 1 | DB connection pooling (`CONN_MAX_AGE=60` + health checks) | ~1.5s reconnect/request | me 1051→**261ms**, list 2029→**545ms**, detail 1597→**645ms**, messages 1454→**649ms** |
| 2 | Scrypt password hashing | PBKDF2 = 996ms/login | Scrypt = 347ms (memory-hard, GPU-resistant), auto-upgrade |
| 3 | Extraction stage fix | 288s wasted, failed | ~30s, 17/17 fields |
| 4 | Model routing | local qwen (900s generation) | OpenRouter gemma (16–33s) |
| 5 | Retry chain | empty responses on free tier | `[chat, chat, fallback]` + backoff |
| 6 | Frontend parallel bootstrap | login→me→conversations serial | `Promise.all([fetchUser(), loadConversations()])` |
| 7 | Eliminated redundant round trip | detail + messages fetched twice | messages from detail response |
| 8 | N+1 elimination | 2 queries × conversations | 1 annotated query |
| 9 | Tracing accuracy | wrong timings | true per-stage durations surfaced in UI |
| 10 | Negative caching (diskcache 30-min TTL) | repeated searches re-run | `set_empty` caches no-result too |

**Net:** login 4302ms → ~700ms; chat open ~2s → ~650ms; full deep-research reply 523s → ~190s.

---

## 4. Architecture

### 4a. Backend layer hierarchy

```
config/ (Django project: settings, urls, wsgi/asgi)
├── users/    → JWT auth (simplejwt), register, profile            [auth layer]
├── chat/     → Conversations, Messages, SSE Stream, Export, Share  [API layer]
├── ai/       → THE RESEARCH ENGINE (17 modules)                    [intelligence layer]
│   ├── orchestrator.py        → generateResponse() generator
│   ├── query_planner.py       → LLM JSON plan (rewrite, intent, tools, model_route)
│   ├── task_analyzer.py       → regex capability classifier
│   ├── tool_router.py         → dispatches search/math/docs/code/memory tools
│   ├── retrieval_service.py   → profiles→expansion→multi-query search→dedupe→rank→coverage→fetch→summary
│   │   └── search/ (tavily, exa, brave, duckduckgo, cache)
│   ├── research_pipeline.py   → extract → verify → golden facts → consistency → gap-fill
│   ├── verifier.py + golden_facts.py + consistency.py + confidence_scorer.py
│   ├── response_formatter.py + citation_service.py
│   ├── model_router.py + model_loader.py + inference.py + inference_api.py
│   └── observability.py + feature_flags.py
├── memory/    → Memory (Postgres FTS), ConversationSummary, summarizer
└── files/     → UserFile, PDF text extraction (+Tesseract OCR fallback)
```

### 4b. Request journey (streaming chat message)

```
Frontend → POST /chat/conversations/{id}/stream/ {message, web_search, file_ids?, regenerate_message_id?}
  └▶ StreamView (chat/views.py)
       ├─ persist user Message
       ├─ generateResponse(...)  [Python generator]
       │    ├─ Observability.create_log + PipelineTracer
       │    ├─ QueryPlanner.plan (OpenRouter gemma, 150 tokens) ──▶ analysis event
       │    ├─ TaskAnalyzer.analyze → capability set
       │    ├─ ToolRouter.execute
       │    │    ├─ RetrievalService: profile → expand → search (concurrent providers)
       │    │    │    → dedupe → rank → coverage (site: queries) → fetch → summary
       │    │    ├─ memories (top-5 FTS) / documents / calculator / code
       │    │    └─ ──▶ search_results event (evidence, intent, coverage)
       │    ├─ prompt: deep-research (agent loop + extract + verify) / enhanced / chat (ChatML)
       │    ├─ ModelRouter.generate_stream (chat→gemma, fallback→qwen) ──▶ token events
       │    ├─ ResponseFormatter: confidence scorer + citations
       │    └─ ──▶ research_summary, citations, timings, done(message_id)
       └─ StreamingHttpResponse (text/event-stream) ──▶ SSE to browser
```

Frontend consumes SSE: `analysis` → `search` (status bar w/ coverage) → `token` (renderMarkdown live) → `citations` (Sources panel) → `summary`/`timings` → `done` (attach Word/PDF tools).

### 4c. Memory subsystem

| Piece | How it works |
|---|---|
| `Memory` model | key/content/importance; `MemoryQuerySet.search()` = Postgres `SearchVector` + `SearchRank`, rank ≥ 0.01, order rank + importance |
| `memory_retriever` | Top-5 relevant memories injected into every prompt (gated by `ENABLE_MEMORY`) |
| `summarizer` | Local LLM summarizes conversation → `ConversationSummary` |
| API | `GET/POST /api/memory/memories/` (+`?search=`), DELETE |

### 4d. Data model (core)

`User` ← `Conversation` (share_token, share_created_at) ← `Message` (role, content, tokens_used) / `UserFile` / `ConversationSummary`; `Memory` (key/content/importance) per user.

---

## 5. System Design Concepts Used

| Concept | Where |
|---|---|
| SSE streaming | Token-by-token via `text/event-stream`; Python generators as event pipeline |
| Orchestration pattern | `generateResponse()` composes planner/analyzer/router/prompter/generator/formatter |
| Strategy pattern | Search providers (Tavily/Exa/Brave/DDG) behind `SearchProvider` ABC |
| Fallback chain + retry w/ backoff | Model attempts `[key, key, fallback]`; extractor `10*2^n` backoff, honors `Retry-After` |
| RAG pipeline | Retrieval profiles → query expansion → multi-query fan-out → dedupe → weighted ranking → coverage enforcement (`site:` queries) → page fetch → summary |
| Ground-truth layer | `GoldenFacts` override/confirm extraction; `ConsistencyChecker` rule engine (stale "latest", future release, contradictions) |
| Confidence scoring | 3+ sources=High, 2=Medium, 1=Low, 0=None; staleness downgrade (2+ yrs) |
| Agent loop | Iterative gap detection → targeted searches → re-rank (max 2 iterations) |
| Singleton | Lazy `get_model()` llama.cpp instance (loaded once) |
| Feature flags | `ENABLE_*` env gates for search/memory/vision/code/calculator/planner/trace |
| Cache-aside + negative caching | diskcache search_cache + orchestrator_cache, SHA-256 keys, 30-min TTL, `set_empty` |
| N+1 elimination | `Count` + `OuterRef`/`Subquery` annotations |
| Connection pooling | `CONN_MAX_AGE=60` + `CONN_HEALTH_CHECKS` |
| Memory-hard hashing | scrypt first in `PASSWORD_HASHERS` |
| JWT auth | Access (30m) + refresh (7d), Bearer, auto-refresh on 401 |
| REST + generics | DRF `ListCreateAPIView` etc., pagination (page 50) |
| 12-factor env config | django-environ, all secrets/flags env-driven |
| ChatML templating | `<\|im_start\|>` blocks per capability (system/memory/search/docs/coding/reasoning) |
| Sandboxing | Code executor: AST safety scan blocks os/subprocess/exec/eval; whitelist + 10s timeout |
| Domain tiering | `SourceWeighter` Tier1=100/Tier2=80/Tier3=60/social=15/blocked=0 |
| Observability | Per-request trace with stage durations (`TraceView` staff-only + timings in UI) |
| Templated markdown→docx/pdf | Block parser (`_iter_blocks`) → python-docx / fitz.Story |
| Idempotent + revocable share | UUID `share_token` create/revoke, public page + JSON API |
| Single-file SPA | Vanilla JS, localStorage tokens, dark/light themes via CSS variables |

---

## 6. Current State & Hosting Checklist

| Item | Status |
|---|---|
| Tests | 58/58 pass (`ai.tests`: golden_facts, retrieval_profiles, regression) |
| Server | `runserver 0.0.0.0:8000 --noreload` (restart after backend edits) |
| Verified end-to-end | Login, chat stream, edit+regenerate, table copy/CSV, docx/pdf export, share + revoke, share public page |
| Hosting (Railway/Render) | Set `MODEL_PATH=''` (local GGUF won't exist) or upload model; `DEBUG=False`; gunicorn `1 worker × 4 threads` (Procfile ready); `PUBLIC_BASE_URL` → your domain; Supabase URL (pooling already applied) |

---

## 7. API Endpoints

| Method | URL | View | Notes |
|---|---|---|---|
| POST | `/api/auth/register/` | RegisterView | AllowAny |
| POST | `/api/auth/login/` | TokenObtainPairView | JWT |
| POST | `/api/auth/refresh/` | TokenRefreshView | JWT |
| GET/PATCH | `/api/auth/me/` | MeView | |
| GET/POST | `/api/chat/conversations/` | ConversationListCreateView | list annotated (N+1-free) |
| GET/DELETE | `/api/chat/conversations/{pk}/` | ConversationDetailView | includes messages |
| GET/POST | `/api/chat/conversations/{pk}/messages/` | MessageListCreateView | |
| POST | `/api/chat/conversations/{pk}/stream/` | StreamView | SSE; supports `regenerate_message_id` |
| GET/PATCH/DELETE | `/api/chat/conversations/{pk}/messages/{msg_pk}/` | MessageDetailView | PATCH deletes later msgs |
| POST | `/api/chat/conversations/{pk}/messages/{msg_pk}/export/` | MessageExportView | `format=docx\|pdf` |
| POST/DELETE | `/api/chat/conversations/{pk}/share/` | ConversationShareView | create/revoke |
| GET | `/share/{token}/` | SharePageView | public HTML |
| GET | `/api/share/{token}/` | PublicShareView | public JSON |
| POST | `/api/ai/generate/` | GenerateView | non-streaming |
| POST | `/api/ai/stream/` | ai StreamView | SSE |
| GET | `/api/ai/debug/trace/{request_id}/` | TraceView | staff-only |
| GET/POST | `/api/memory/memories/` | MemoryListCreateView | `?search=` FTS |
| GET/DELETE | `/api/memory/memories/{pk}/` | MemoryDetailView | |
| POST | `/api/files/upload/` | FileUploadView | PDF text extraction |
| GET/DELETE | `/api/files/files/{pk}/` | FileDetailView | |
| GET | `/api/files/files/{pk}/text/` | FileTextView | |

## 8. Environment / Features

- **Env-driven** (`backend/.env`, see `.env.example`): SECRET_KEY, DEBUG, DATABASE_URL (Supabase Postgres), ALLOWED_HOSTS, CORS, JWT TTLs, PUBLIC_BASE_URL, SUPABASE_*, MODEL_PATH/CONTEXT/THREADS, OPENROUTER_API_KEY, TAVILY/EXA/BRAVE keys, `ENABLE_*` flags
- **Model routing** (`ai/models.json`): planner/chat/extract/reasoning/creative → OpenRouter `google/gemma-4-26b-a4b-it:free`; coding → `cohere/north-mini-code:free`; default/fallback → local `qwen2.5-3b-instruct-q4_k_m`
