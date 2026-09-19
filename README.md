# AI Math Tutor

A desktop math tutor built with Electron + React (renderer) and a Python FastAPI
backend. The core solver is an exact, offline computer-algebra engine (SymPy);
a course-material index (Chroma) feeds a **Practice** mode that writes word
problems and shows the equation behind them; local or remote language models
for free-form problems, handwriting recognition and speech are optional and
loaded on demand.

## What it does

| Capability | Backed by | Availability |
| --- | --- | --- |
| Solve equations, systems, inequalities; derivatives, integrals, limits; simplify / factor / expand; arithmetic — with steps, LaTeX and answer checking | `src/backend/services/math_engine.py` (SymPy) | Always, offline, no GPU |
| Whiteboard: pen, eraser, select, text, line, rectangle, ellipse; colour swatches and width presets; dot/line grid; tool hotkeys; undo/redo; export PNG/PDF; basic ink analysis | Fabric.js + Pillow/NumPy | Always |
| Course material index: upload PDF/Markdown/text, chunked and embedded, semantic search | `services/knowledge_service.py` — Chroma (MiniLM ONNX embedder) with a NumPy/hashing fallback | Always, offline |
| Practice ("learn by doing"): word problems on a topic or from your material, with the modelling equation, answer checking, hints and worked solutions | `services/practice_service.py` — language model grounded in retrieved chunks, every problem verified by the SymPy engine; deterministic template generator when no LLM is configured | Always; LLM-written problems need a language model |
| Free-form / word problems, handwriting recognition | Qwen3-Omni-30B-A3B-Thinking locally, or any OpenAI-compatible endpoint (`LLM_API_BASE_URL`) | Optional: local model needs the ML stack, the model on disk and a GPU |
| Voice input | MERaLiON-AudioLLM (Whisper fallback) | Optional: needs the ML stack and model |
| Spoken answers | VibeVoice-1.5B (XTTS fallback) | Optional: needs the ML stack and model |

When an optional model is not loaded the UI says so and disables the
corresponding button; the backend never fabricates results. Frequently
changed preferences (theme, font size, steps/confidence display, whiteboard
grid, practice options) are in the **Quick settings** popover in the title
bar; everything else is on the Settings page.

### Practice flow

1. Open **Practice**, optionally upload course material (PDF/MD/TXT) or paste
   text into the **Course material** panel. Text is chunked and embedded into
   the Chroma store under `<DATA_DIR>/knowledge`.
2. Enter a topic (or leave it blank to draw from your material), pick a
   difficulty and press **Generate**. The backend retrieves the most relevant
   chunks, asks the language model for a word problem *plus* the equation that
   models it, and accepts it only if the SymPy engine can solve the equation
   and reach the model's stated answer. Without a language model, a template
   generator produces the problem and equation directly.
3. Work the problem (or send it to the whiteboard), check your answer, ask for
   hints, and reveal the equation and worked solution when you are ready.

## Architecture

```
Electron main (src/main/main.js)
  ├─ spawns/reuses the Python backend on 127.0.0.1:8000, forwards its status
  ├─ CSP, single-instance lock, settings store, file dialogs
  └─ BrowserWindow ──preload.js (contextBridge)──► React renderer (src/renderer)
                                                     ├─ one WebSocket (WebSocketProvider) + REST fallback
                                                     ├─ MathTutorPage: whiteboard + tutor chat
                                                     ├─ PracticePage: course material + word problems
                                                     ├─ QuickSettings popover (title bar)
                                                     └─ SettingsPage: models, resources, preferences

FastAPI backend (src/backend/main.py)
  ├─ /ws/{client_id}      validated JSON protocol, request_id correlation
  ├─ /api/math/*          solve, verify, batch, history, analyze-drawing
  ├─ /api/drawing/*       image + stroke analysis
  ├─ /api/audio/*         speech-to-text / text-to-speech (report unavailable without models)
  ├─ /api/knowledge/*     status, documents (text/upload/list/delete), search
  ├─ /api/practice/*      status, generate, problem, check, hint, solution
  ├─ /api/llm/*           language-model source: config, presets, models, test
  ├─ /api/models/*        list, load, unload, status, resources, auto-load config
  ├─ /api/system/*        status, config, logs, metrics
  └─ services/            ServiceContainer singletons: AI (math engine + local/remote LLM),
                          knowledge (Chroma), practice, audio, drawing, model management
```

## Requirements

- Node.js 18+ and npm
- Python 3.10+ (3.12 tested)
- Windows 10/11 is the packaging target; development also works on macOS/Linux
- For optional models: an NVIDIA GPU with recent CUDA drivers and tens of GB of disk

## Quick start (development)

```bash
npm install                      # also installs src/renderer dependencies
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r src/backend/requirements.txt -r src/backend/requirements-dev.txt

python start_app.py              # backend + Electron with hot reload
```

`start_app.py` starts the backend, waits for `/health`, then runs `npm run dev`
(React dev server on :3000 + Electron). Use `--backend-only` to just run the
API (docs at <http://127.0.0.1:8000/api/docs>), `--port N` to change the port.

Alternatively run the pieces yourself:

```bash
npm run dev:backend     # python main.py in src/backend
npm run dev             # React dev server + Electron (Electron reuses a running backend)
```

Electron picks the backend interpreter from `MATH_TUTOR_PYTHON`, then a bundled
`resources/python`, then `venv/` or `.venv/` in the repo, then `python` on PATH.
Set `MATH_TUTOR_SKIP_BACKEND=1` to stop Electron from managing the backend.

## Optional AI models

```bash
pip install -r src/backend/requirements-ml.txt   # torch, transformers, accelerate, audio libs
python scripts/setup_models.py --list
python scripts/setup_models.py --model Qwen3-Omni-30B-A3B-Thinking
```

Then open **Settings → AI models** in the app and press **Load**. The Settings
page shows why a model cannot be loaded (ML stack missing, not downloaded, no
GPU, insufficient RAM/disk). Models live under `src/backend/models/` in
development and under the app's user-data folder when packaged (`MODEL_DIR`
overrides both).

### Choosing the language model: local, OpenRouter, or any OpenAI-compatible API

Free-form word problems and LLM-written practice problems can come from the
local Qwen model **or** from an API. Pick the source in the app:

- **Settings → Language model**: choose *Auto* (local model when loaded,
  otherwise the API), *Local model* (nothing leaves the machine) or *API*.
  Pick a provider preset — **OpenRouter**, OpenAI, Ollama, LM Studio or a
  custom URL — paste the key, pick a model from the live model list (OpenRouter
  models show context size, price and a "good at math" flag), *Test
  connection*, then *Save & use*. The choice applies immediately to every open
  window and is persisted in `<DATA_DIR>/llm_config.json` (key stored locally,
  file mode 0600, never returned by the API).
- **Quick settings** (title bar): a one-click *Auto / Local / API* toggle.

Environment defaults (used until you change something in the app; `.env` in
`src/backend`):

```bash
OPENROUTER_API_KEY=sk-or-v1-...                 # shortest path: selects the OpenRouter preset
LLM_API_MODEL=openai/gpt-4o-mini                # any model id from https://openrouter.ai/models

# or any OpenAI-compatible endpoint
LLM_API_BASE_URL=http://localhost:11434/v1      # Ollama; LM Studio is :1234; OpenAI is https://api.openai.com/v1
LLM_API_KEY=...                                 # omit for local servers that do not need one
LLM_MODE=auto                                   # auto | local | remote
```

REST: `GET/PUT/DELETE /api/llm/config`, `GET|POST /api/llm/models`,
`POST /api/llm/test`. Answers produced by any language model are cross-checked
with the SymPy engine whenever they contain an equation; Practice problems are
rejected and regenerated if the engine cannot reproduce the model's answer.

## Configuration

Backend settings come from environment variables or `src/backend/.env`
(see `src/backend/config/settings.py`). Commonly used:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Bind address (loopback only by design) |
| `AI_USE_GPU` | `true` | Use CUDA when available |
| `PRELOAD_MODELS` | `false` | Warm heavy models in the background after start |
| `MODEL_DIR`, `DATA_DIR`, `LOG_DIR` | under `src/backend/` | Storage locations |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MAX_WEBSOCKET_MESSAGE_BYTES` | 8 MiB | Upper bound for one WebSocket frame (drawings) |
| `LLM_MODE` | `auto` | `auto` (local when loaded, else API), `local`, `remote`; overridable in the app |
| `OPENROUTER_API_KEY` | unset | Selects the OpenRouter preset with this key |
| `LLM_API_BASE_URL`, `LLM_API_KEY`, `LLM_API_MODEL`, `LLM_API_TIMEOUT_SECONDS` | unset / `gpt-4o-mini` / `60` | Any OpenAI-compatible endpoint (see above) |
| `KNOWLEDGE_DIR` | `<DATA_DIR>/knowledge` | Chroma store and document registry |
| `KNOWLEDGE_EMBEDDING` | `auto` | `minilm` (Chroma's ONNX all-MiniLM-L6-v2), `hashing` (offline, no download), or `auto` = MiniLM if available |
| `KNOWLEDGE_CHUNK_CHARS` / `KNOWLEDGE_CHUNK_OVERLAP_CHARS` | `900` / `150` | Chunking of ingested text |
| `KNOWLEDGE_MAX_UPLOAD_BYTES` / `KNOWLEDGE_MAX_DOCUMENT_CHARS` | 25 MiB / 2 M | Upload limits |

Renderer: `REACT_APP_BACKEND_URL` at build time (Electron overrides it at run
time with the port it manages). User preferences are stored via
`electron-store` (or `localStorage` in a plain browser).

## Testing and checks

```bash
npm test                 # backend pytest + renderer tests
npm run test:backend     # 123 tests: math engine, knowledge base, practice, LLM client, REST API, WebSocket protocol
npm run typecheck        # tsc --noEmit for the renderer
npm run lint
```

## Building the Windows app

```bash
npm run build            # React production build + NSIS installer + portable exe → dist/
npm run pack             # unpacked directory for inspection
```

The installer ships the backend as Python source under
`resources/backend` and expects Python 3.10+ on the target machine (the
installer warns if it is missing). Bundling an interpreter is not yet done;
place one at `resources/python/python.exe` and Electron will prefer it.

## Project layout

```
package.json               Electron app, scripts, electron-builder config
start_app.py               development launcher
assets/                    icon, installer.nsh (NSIS customInstall/customUnInstall hooks)
scripts/                   model download / optimisation helpers, make_icons.py
src/main/                  Electron main process + preload
src/renderer/              CRA + TypeScript renderer
  src/lib/backend.ts       backend URL resolution + typed fetch / JSON / multipart helpers
  src/types/protocol.ts    WebSocket message types shared with main.py
  src/hooks/useWebSocket.ts one self-healing socket with request/response correlation
  src/components/          DrawingCanvas, WhiteboardToolbar, QuickSettings, CourseMaterialPanel,
                           ChatInterface, MathInput, ConnectionStatus, layout
  src/pages/               MathTutorPage, PracticePage, SettingsPage, HelpPage
src/backend/
  main.py                  app factory, lifespan, WebSocket protocol
  api/dependencies.py      ServiceContainer (single instance of each service)
  api/routes/              math, drawing, audio, knowledge, practice, llm, system, model routers
  services/math_engine.py  SymPy solver, parser sandbox, steps, verification
  services/knowledge_service.py  chunking, embedders, Chroma / local vector store, ingestion, search
  services/practice_service.py   RAG word-problem generation, engine validation, templates, grading
  services/llm_client.py   OpenAI-compatible chat client (OpenRouter/OpenAI/Ollama/LM Studio presets, model listing)
  services/llm_config.py   persisted runtime choice of local / API / auto
  services/                AI / audio / drawing / model services, optional_deps
  tests/                   pytest suite
  requirements*.txt        core / ml / dev dependency sets
```

## WebSocket protocol (summary)

Connect to `ws://127.0.0.1:8000/ws/{client_id}`. The server first sends
`{"type":"connected", "capabilities": {symbolic_solver, llm, llm_name, llm_mode, speech, drawing_recognition, knowledge_base, practice}}`
and pushes `{"type":"capabilities", ...}` whenever they change (e.g. the language model source is switched).
Client messages are JSON with a `type` and optional `request_id`, which the
server echoes on the reply:

| Client `type` | Fields | Server reply |
| --- | --- | --- |
| `ping` | – | `pong` |
| `math_input` | `content`, `metadata?` | `math_solution` (+ `audio_response` if TTS enabled and available) |
| `verify` | `problem`, `solution` | `verification` |
| `drawing` | `data` (data URL or `{image}`), `analysis_type?` | `drawing_analysis` |
| `audio` | `data` (base64), `language?`, `format?` | `audio_transcription` |

Invalid input yields `{"type":"error","code":...,"message":...}` without
closing the connection. Full types: `src/renderer/src/types/protocol.ts`.

## Security notes

- Renderer runs with `contextIsolation`, `sandbox`, no Node integration; the
  preload exposes a small typed API and never the raw `ipcRenderer`.
- A Content-Security-Policy header is applied to every response; `unsafe-eval`
  is only allowed in development for CRA hot reload.
- The backend binds to loopback only; CORS is restricted to loopback origins
  (any `http://localhost:<port>` / `http://127.0.0.1:<port>`) and the packaged
  `file://` origin.
- Uploaded course material stays on disk locally; only the retrieved chunks
  are sent to a language model, and only when an API provider is the active
  source. In *Local* mode nothing leaves the machine. API keys are stored in
  `<DATA_DIR>/llm_config.json` (mode 0600) and only ever sent to the configured
  base URL.
- The math parser is sandboxed: whitelisted functions/symbols, no attribute
  access, no builtins, size limits, and CPU-bound work runs with a timeout.

## Known limitations

- Handwriting recognition and speech need the optional local models and a GPU.
  Free-form word problems and LLM-written practice problems need either the
  local Qwen model or a configured OpenAI-compatible endpoint; without one,
  Practice uses the built-in template generator.
- The MiniLM embedder is downloaded by Chroma on first use (~80 MB); set
  `KNOWLEDGE_EMBEDDING=hashing` for a fully offline install (lower recall).
- Solution history and practice session stats are in-memory per backend process;
  the course-material index is persisted.
- macOS/Linux packaging targets are not configured (development works).
- The installer does not bundle a Python runtime.

## License

MIT.
