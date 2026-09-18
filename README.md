# AI Math Tutor

A desktop math tutor built with Electron + React (renderer) and a Python FastAPI
backend. The core solver is an exact, offline computer-algebra engine (SymPy);
local AI models for word problems, handwriting recognition and speech are
optional and loaded on demand.

## What it does

| Capability | Backed by | Availability |
| --- | --- | --- |
| Solve equations, systems, inequalities; derivatives, integrals, limits; simplify / factor / expand; arithmetic — with steps, LaTeX and answer checking | `src/backend/services/math_engine.py` (SymPy) | Always, offline, no GPU |
| Whiteboard: pen, eraser, text, line, rectangle, ellipse; undo/redo; export PNG/PDF; basic ink analysis | Fabric.js + Pillow/NumPy | Always |
| Free-form / word problems, handwriting recognition | Qwen3-Omni-30B-A3B-Thinking | Optional: needs the ML stack, the model on disk and a GPU |
| Voice input | MERaLiON-AudioLLM (Whisper fallback) | Optional: needs the ML stack and model |
| Spoken answers | VibeVoice-1.5B (XTTS fallback) | Optional: needs the ML stack and model |

When an optional model is not loaded the UI says so and disables the
corresponding button; the backend never fabricates results.

## Architecture

```
Electron main (src/main/main.js)
  ├─ spawns/reuses the Python backend on 127.0.0.1:8000, forwards its status
  ├─ CSP, single-instance lock, settings store, file dialogs
  └─ BrowserWindow ──preload.js (contextBridge)──► React renderer (src/renderer)
                                                     ├─ one WebSocket (WebSocketProvider) + REST fallback
                                                     ├─ MathTutorPage: whiteboard + tutor chat
                                                     └─ SettingsPage: models, resources, preferences

FastAPI backend (src/backend/main.py)
  ├─ /ws/{client_id}      validated JSON protocol, request_id correlation
  ├─ /api/math/*          solve, verify, batch, history, analyze-drawing
  ├─ /api/drawing/*       image + stroke analysis
  ├─ /api/audio/*         speech-to-text / text-to-speech (report unavailable without models)
  ├─ /api/models/*        list, load, unload, status, resources, auto-load config
  ├─ /api/system/*        status, config, logs, metrics
  └─ services/            ServiceContainer singletons: AI (math engine + optional LLM),
                          audio, drawing, model management
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

Renderer: `REACT_APP_BACKEND_URL` at build time (Electron overrides it at run
time with the port it manages). User preferences are stored via
`electron-store` (or `localStorage` in a plain browser).

## Testing and checks

```bash
npm test                 # backend pytest + renderer tests
npm run test:backend     # 60 tests: math engine, REST API, WebSocket protocol
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
scripts/                   model download / optimisation helpers
src/main/                  Electron main process + preload
src/renderer/              CRA + TypeScript renderer
  src/lib/backend.ts       backend URL resolution + typed fetch
  src/types/protocol.ts    WebSocket message types shared with main.py
  src/hooks/useWebSocket.ts one self-healing socket with request/response correlation
  src/components/          DrawingCanvas, ChatInterface, MathInput, ConnectionStatus, layout
  src/pages/               MathTutorPage, SettingsPage, HelpPage
src/backend/
  main.py                  app factory, lifespan, WebSocket protocol
  api/dependencies.py      ServiceContainer (single instance of each service)
  api/routes/              math, drawing, audio, system, model routers
  services/math_engine.py  SymPy solver, parser sandbox, steps, verification
  services/                AI / audio / drawing / model services, optional_deps
  tests/                   pytest suite
  requirements*.txt        core / ml / dev dependency sets
```

## WebSocket protocol (summary)

Connect to `ws://127.0.0.1:8000/ws/{client_id}`. The server first sends
`{"type":"connected", "capabilities": {symbolic_solver, llm, speech, drawing_recognition}}`.
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
- The backend binds to loopback only; CORS is restricted to the dev server and
  the packaged `file://` origin.
- The math parser is sandboxed: whitelisted functions/symbols, no attribute
  access, no builtins, size limits, and CPU-bound work runs with a timeout.

## Known limitations

- Word problems, handwriting and speech need the optional models and a GPU.
- Solution history is in-memory per backend process.
- macOS/Linux packaging targets are not configured (development works).
- The installer does not bundle a Python runtime.

## License

MIT.
