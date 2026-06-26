# Local LLM Setup

TUI wizard for hosting local LLMs with **Ollama**, **vLLM**, **llama.cpp**, and **SGLang**. Detects your OS and hardware, checks dependencies, generates `docker-compose.yaml`, optional `nginx.conf`, and can deploy the stack with one command.

## Features

- Auto-detect OS (Linux, macOS, Windows/WSL), GPU, Docker, CUDA, ROCm, nginx
- Keyboard-driven TUI (↑/↓ navigate, Space select, Enter confirm, `/` slash commands)
- Deploy log with **Pretty** (colored Rich output) and **Copy mode** (`c` toggle — drag-select, Ctrl+C)
- Quick or **full** configuration — every model, runtime, Docker, and nginx option per provider
- **Custom Docker image** per provider (Quick and Full) with default image shown in the wizard — override when a tag is incompatible
- Model validation (Ollama registry, Hugging Face, GGUF for llama.cpp)
- Capability flags: vision, audio, tool calling, speculative decoding (MTP)
- Optional nginx reverse proxy with API key auth (`X-API-Key` or `Authorization: Bearer`) and Cloudflare quick tunnel
- Generate & deploy from TUI or CLI (`generate --run`, `run`, `stop`)
- Access URLs for localhost, **public IP** (auto-detected), private LAN, and Cloudflare tunnel — plus curl smoke tests
- Save/load YAML profiles
- One-line server install and uninstall via `curl | bash` ([Hermes-style](https://hermes-agent.nousresearch.com/))

## Quick start

### One-line install (server / fresh machine)

```bash
curl -fsSL https://raw.githubusercontent.com/PerasutRu/Local_LLM_setup/main/install.sh | bash
local-llm-setup tui
```

The installer bootstraps **uv**, **Python 3.11**, clones the repo, creates a venv, and links `local-llm-setup` into `~/.local/bin`. Root installs on Linux use `/usr/local/lib/local-llm-setup` and `/usr/local/bin/local-llm-setup`.

| Path | Purpose |
|------|---------|
| `~/.local-llm-setup/app` | Git checkout + virtualenv |
| `~/.local-llm-setup/bin/uv` | Managed uv binary |
| `~/.local-llm-setup/llm_local/output` | Generated compose/nginx files |
| `~/.local-llm-setup/llm_local/profiles` | Saved YAML profiles |
| `~/.local/bin/local-llm-setup` | CLI command shim |

Install options (pass after `bash -s --`):

| Option | Description |
|--------|-------------|
| `--dir PATH` | Install directory (default `~/.local-llm-setup/app`) |
| `--branch NAME` | Git branch to clone (default `main`) |
| `--no-venv` | Install into system Python instead of a venv |
| `--skip-doctor` | Skip post-install `doctor` check |

```bash
curl -fsSL .../install.sh | bash -s -- --branch main --skip-doctor
```

**Custom install URL:** host `install.sh` on your domain (GitHub Pages, nginx, or Cloudflare) and point users at `https://your-domain/install.sh`.

> **404 on `curl | bash`?** `raw.githubusercontent.com` only serves **public** repositories. If you see `curl: (56) ... 404`, open **GitHub → Settings → General → Danger zone → Change repository visibility → Public**, then retry. A private repo also blocks the `git clone` step inside `install.sh` for users without credentials.

### Uninstall

Stop any running stack first (`local-llm-setup stop` or `local-llm-setup stop --volumes`), then:

```bash
curl -fsSL https://raw.githubusercontent.com/PerasutRu/Local_LLM_setup/main/uninstall.sh | bash
```

| Option | Description |
|--------|-------------|
| `--keep-data` | Keep `llm_local/` (output and profiles) under `~/.local-llm-setup` |
| `--keep-uv` | Keep the managed uv binary |
| `--yes`, `-y` | Skip confirmation prompt |

```bash
curl -fsSL .../uninstall.sh | bash -s -- --keep-data --yes
```

The uninstaller does **not** remove Docker images or volumes. Shell `PATH` lines added to `~/.bashrc` / `~/.zshrc` are left in place — remove the `# Local LLM Setup` block manually if needed.

### Developer install

```bash
# Install from source
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Interactive wizard (generate + start Docker by default)
local-llm-setup tui

# Check host dependencies
local-llm-setup doctor

# Generate from profile
local-llm-setup generate --config llm_local/profiles/sample.yaml

# Generate and deploy in one step
local-llm-setup generate --config llm_local/profiles/sample.yaml --run

# Start or stop an existing stack
local-llm-setup run --config llm_local/profiles/sample.yaml
local-llm-setup stop
```

**Full guide (Thai):** [GUIDE.md](GUIDE.md) · **Architecture:** [UML.md](UML.md)

## CLI commands

| Command | Description |
|---------|-------------|
| `tui` | Interactive wizard |
| `doctor` | Check Docker, GPU, CUDA, nginx (`--json` for machine output) |
| `detect` | Alias for `doctor` |
| `generate` | Write `llm_local/output/` from a profile (`--run` to deploy, `--dry-run` to validate) |
| `run` | Start a generated stack (`--no-pull` to skip image pull) |
| `stop` | Stop the stack (`--volumes` to remove data volumes) |
| `save` | Save a config as a named profile |

After `generate` or `run`, the CLI prints **access URLs** (localhost, public IP when detectable, private LAN, and Cloudflare tunnel when nginx is enabled). See [Access URLs](#access-urls) below.

## Access URLs

After deploy, the TUI and `ACCESS.md` show several endpoints — each is for a different network:

| Label | Example | Use when |
|-------|---------|----------|
| **local** | `http://127.0.0.1:8080/` | On the host machine only |
| **public IP** | `http://203.0.113.10:8080/` | From the internet, if the host port is open in firewall and port-forwarded (when behind NAT) |
| **LAN** | `http://192.168.1.191:8080/` | Other devices on the same WiFi/LAN (shown alongside public IP when both are known) |
| **public** (tunnel) | `https://….trycloudflare.com` | From anywhere on the internet — no firewall/port-forward setup; URL changes when the tunnel container restarts |
| **openai** / **ollama** | Same host as public IP or LAN above | Base URL for API clients (`/v1` is appended for OpenAI-compatible clients) |

**Public IP detection** — on deploy, the tool queries `api.ipify.org` / `ifconfig.me` over HTTPS. If that fails (offline host), it falls back to the private LAN address.

**With nginx enabled**, only nginx publishes a host port (e.g. `8080` or `8081` if the default was busy). Ollama/vLLM containers stay on the internal Docker network (`11434/tcp` in `docker ps` with no `0.0.0.0:…` mapping is expected). Traffic flows:

```
Client → host:8080 (nginx) → ollama:11434 (internal)
Client → https://….trycloudflare.com (cloudflared) → nginx → ollama
```

**`/test` slash command** — curl smoke tests hit `127.0.0.1` on the port from `llm_local/output/docker-compose.yaml`. When API key auth is on, `/test` reads the key from `llm_local/output/api_keys.map` and sends `X-API-Key` (Ollama native routes) or `Authorization: Bearer` (`/v1/*` routes, same as OpenAI clients).

### API key auth (nginx)

When **Yes nginx — with API key auth** is selected, nginx accepts either header (same key value):

| Header | Typical client |
|--------|----------------|
| `X-API-Key: <key>` | curl, Ollama CLI, custom HTTP |
| `Authorization: Bearer <key>` | OpenAI Python SDK, Cursor, LangChain (`api_key=` / `OPENAI_API_KEY`) |

The key is printed after deploy under `api_keys:` and saved in `llm_local/output/api_keys.map`. `/health` does not require a key.

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://YOUR_HOST:8081/v1",
    api_key="YOUR_KEY_FROM_api_keys.map",
)
client.chat.completions.create(model="tinyllama:1.1b", messages=[{"role": "user", "content": "hi"}])
```

```bash
# curl — Ollama native
curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:8081/api/tags

# curl — OpenAI-compatible
curl -H "Authorization: Bearer YOUR_KEY" http://127.0.0.1:8081/v1/models
```

Example checks from another machine:

```bash
# Same LAN
curl http://192.168.1.191:8080/health

# Internet via public IP (firewall + port forward required)
curl http://YOUR_PUBLIC_IP:8080/health

# Internet via Cloudflare quick tunnel (no port forward)
curl https://YOUR_TUNNEL.trycloudflare.com/health
docker logs local-llm-tunnel 2>&1 | grep trycloudflare   # current tunnel URL
```

## TUI slash commands

Press `/` in the wizard to open the command bar:

| Command | Action |
|---------|--------|
| `/help` | List commands |
| `/providers` | Switch Ollama / vLLM |
| `/deploy` | Regenerate and start the stack |
| `/test` | Run curl smoke tests (uses compose port + `api_keys.map` when auth is on) |
| `/stop` | Stop containers (keep volumes) |
| `/delete-container` | Stop and remove containers + volumes |
| `/doctor` | Jump back to Host Doctor |

Press `s` to stop the running stack from any screen.

### Deploy log (Pretty + Copy)

After `/deploy`, `/test`, or **Stop running Docker stack**, a log panel appears below the wizard steps.

| Mode | What you see |
|------|----------------|
| **Pretty** (default) | Colored Rich log — ✓/✗, gold headings, blue underlined URLs |
| **Copy** | Plain text in a TextArea — drag to select, **Ctrl+C** / **Cmd+C** to copy |

Focus the log panel, then:

| Key | Action |
|-----|--------|
| `c` | Toggle Pretty ↔ Copy mode |
| `v` or `Esc` | Return to Pretty view (from Copy mode) |
| `Ctrl+C` / `Cmd+C` | Copy selection (Copy mode only) |

A hint line above the log and the footer bar repeat these shortcuts. See [GUIDE.md](GUIDE.md) for the Thai walkthrough.

Access URLs printed after deploy use the same styling (gold headings, blue links) in the TUI and in `ACCESS.md`.

## Configuration modes

| Mode | Best for |
|------|----------|
| **Quick** | Fast path — model name, optional custom Docker image, capabilities, nginx on/off |
| **Full** | Every settable option — ports, env, volumes, GPU ids, vLLM serve flags, nginx timeouts |

Full mode adds a **Runtime & Docker** step between Model and Capabilities. Both modes let you override the provider Docker image; leave the field empty to use the default shown in the wizard.

### Default Docker images

| Provider | Default image | Notes |
|----------|---------------|-------|
| Ollama | `ollama/ollama:latest` | |
| vLLM | `vllm/vllm-openai:latest` | AMD hosts use `rocm/vllm:latest` automatically |
| llama.cpp | `ghcr.io/ggerganov/llama.cpp:server` | |
| SGLang | `lmsysorg/sglang:latest` | |

Set a custom image in the TUI (Quick: Model step; Full: Runtime step) or in profile YAML as `image_tag`. Example: `ollama/ollama:0.5.4` when `latest` is incompatible with your stack.

### Full mode — common fields (all providers)

| Step | Fields |
|------|--------|
| Model | `model.name`, `context_length`, `quantization` (vLLM/SGLang), `tensor_parallel`, HF token |
| Runtime | `profile_name`, `output_dir`, `port`, `bind_host`, `image_tag`, `shm_size`, `extra_env`, `extra_args` |
| Nginx | `listen_port`, `server_name`, `bind_host`, `client_max_body_size`, `proxy_read_timeout`, CORS, cloudflared tunnel |

Provider-specific extras:

| Provider | Additional Full fields |
|----------|------------------------|
| **Ollama** | `OLLAMA_NUM_PARALLEL`, `OLLAMA_MODELS`, `OLLAMA_HOST` (auto-synced to `0.0.0.0:<port>` when ports are auto-adjusted; override in Full mode if needed) |
| **vLLM** | See [vLLM production config](#vllm-production-config) below |
| **llama.cpp** | `n_gpu_layers` (→ `--n-gpu-layers`) |
| **SGLang** | `gpu_count`, same HF/quantization fields as vLLM |

In Full mode, use **bind_host** on the Runtime step instead of the “expose publicly” capability toggle.

## vLLM production config

Full mode maps to real-world `docker compose` setups (e.g. Gemma 4 multimodal with audio):

| Setting | Full mode field | Compose effect |
|---------|-----------------|----------------|
| Host `8002` → container `8000` | `port` = `8000`, `publish_port` = `8002` | `ports: ["0.0.0.0:8002:8000"]` |
| Pin GPU 0 | `gpu_device_ids` = `0` | `device_ids: ["0"]` + `NVIDIA_VISIBLE_DEVICES` |
| HF cache volume | `extra_volumes` | `volumes: ["/host:/root/.cache/huggingface"]` |
| `ipc: host` | `ipc` = `host` | `ipc: host` |
| Env vars | `extra_env` | `HF_HOME`, `PYTORCH_CUDA_ALLOC_CONF`, … |
| Serve flags | vLLM model fields | `entrypoint: [vllm, serve]` + flags |
| Audio models | Capabilities → **Audio** | `bash -lc` bootstrap installs `vllm[audio]` then `exec vllm serve` |

**vLLM-only model fields:** `gpu_memory_utilization`, `max_num_seqs`, `tool_call_parser`, `reasoning_parser`, `kv_cache_dtype`, `limit_mm_per_prompt`, `trust_remote_code`, `enable_prefix_caching`.

**Example (Gemma 4 AWQ):**

- Model: `cyankiwi/gemma-4-E4B-it-AWQ-INT4`, context `80000`, gpu_mem `0.3`, parsers `gemma4`, limit_mm `{"image": 4, "audio": 1}`
- Runtime: port `8000`, publish `8002`, gpu_device_ids `0`, ipc `host`, volume for HF cache
- Capabilities: tool calling, vision, **audio**

For a fully custom start script, set **command_shell** on the Runtime step (overrides generated `vllm serve`).

## Dockerized setup app

Run the wizard without installing Python on the host:

```bash
docker build -t local-llm-setup .
docker run -it --rm -v "$(pwd)/llm_local/output:/workspace/llm_local/output" local-llm-setup tui
```

Generated files appear in `./llm_local/output/`.

## Framework notes

| Framework   | Model source        | GGUF | GPU required |
|------------|---------------------|------|--------------|
| Ollama     | Ollama model name   | No   | No           |
| vLLM       | Hugging Face repo   | No   | Yes (NVIDIA/AMD) |
| llama.cpp  | GGUF path/URL       | Yes  | No           |
| SGLang     | Hugging Face repo   | No   | Yes          |

**Ollama model names** — use the same format as `ollama pull`:

- `llama3.2` or `llama3.2:latest` — official library models
- `namespace/model:tag` — community models on Ollama Library (e.g. `dommage/gemma4-e4b-qat:latest`)

The wizard validates names before generate/deploy; invalid examples include extra path segments like `org/sub/model:tag`.

## Docker Compose

Generated stacks use a single Compose file in `llm_local/output/docker-compose.yaml`. All services (LLM backends, nginx, cloudflared) join the **`local_llm`** bridge network (`local-llm-setup-local_llm`) so containers talk over Docker DNS (`ollama:11434`, `nginx:80`, etc.) instead of the host loopback.

```bash
cd llm_local/output
docker compose pull
docker compose up -d
docker compose ps
docker compose logs -f nginx ollama
docker compose down          # stop
docker compose down -v       # stop + remove volumes
```

When **nginx is enabled**, only nginx (and optional cloudflared) publish host ports. LLM containers stay on the internal network; nginx proxies to `service_name:port` inside the stack. In `docker ps`, expect `11434/tcp` without a host mapping for Ollama — use the nginx port or tunnel URL instead.

**Ollama + nginx:** generated compose sets `OLLAMA_HOST=0.0.0.0:<port>` so the Ollama HTTP API is reachable from nginx and other containers on `local_llm`. Without this, Ollama listens on `127.0.0.1` inside its container and nginx returns **502 Bad Gateway** on `/api/*` while `/health` still passes.

When **nginx is disabled**, each framework publishes its own host port (e.g. `127.0.0.1:11434`).

CLI shortcuts:

```bash
local-llm-setup generate --config llm_local/profiles/sample.yaml --run
local-llm-setup run --config llm_local/profiles/sample.yaml
local-llm-setup stop --output ./llm_local/output
local-llm-setup stop --output ./llm_local/output --volumes
```

## Output files

- `docker-compose.yaml` — services on shared network `local_llm`, healthchecks, GPU reservations
- `.env` — secrets (e.g. `HF_TOKEN`)
- `nginx.conf` — reverse proxy (if enabled)
- `api_keys.map` — API key map for nginx (if enabled)
- `RUN.md` — copy-paste run commands
- `commands.log` — append-only log of every shell command executed during deploy/stop/test (for debugging)
- `ACCESS.md` — access URLs and example curl commands

When nginx is enabled, the framework binds to `127.0.0.1` internally and only nginx is exposed on `0.0.0.0`. An optional **cloudflared** sidecar provides a public `trycloudflare.com` URL.

## Troubleshooting

**Docker not found** — Install Docker Desktop (macOS/Windows) or run the [Docker install script](https://get.docker.com) on Linux.

**GPU not available in container** — Install NVIDIA drivers and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

**vLLM/SGLang validation errors on Mac** — Use Ollama or llama.cpp on Apple Silicon.

**Port already in use** — Ports are auto-adjusted to the next free port during `generate` (a warning is printed). When **nginx is enabled**, framework ports are internal to Docker only — a host Ollama on `11434` does not force the container to move ports. When **nginx is disabled**, host port conflicts bump the published port and `OLLAMA_HOST` stays in sync. When running **multiple frameworks** (Ollama + vLLM + …), each service gets its default port (`11434`, `8000`, `8080`, `30000`) or the next free one if that port is taken. `/test` and `ACCESS.md` read the actual port from `docker-compose.yaml`.

**Cannot reach the API from outside** — Use the **Cloudflare tunnel** URL (`https://….trycloudflare.com`) or ensure the **public IP** port is allowed in the host firewall and forwarded on the router. Do not use `192.168.x.x` from outside your LAN. The `openai` / `ollama` lines in the TUI follow public IP (or LAN if public IP could not be detected).

**Stale tunnel URL** — Cloudflare quick-tunnel URLs change every time `local-llm-tunnel` restarts. Run `docker logs local-llm-tunnel 2>&1 | grep trycloudflare` or redeploy to refresh `ACCESS.md`.

**`401 Unauthorized` on `/api/*` or `/v1/*`** — nginx API key auth is enabled. Pass `X-API-Key` or `Authorization: Bearer` with the key from `llm_local/output/api_keys.map`. OpenAI SDK users set `api_key=` to that value. Regenerate nginx with `/deploy` after upgrading if Bearer auth was added recently.

**`502 Bad Gateway` on `/api/*` while `/health` is ok** — nginx is up but cannot reach the LLM backend. Regenerate and redeploy so `docker-compose.yaml` and `nginx.conf` use the same Ollama port (`OLLAMA_HOST: 0.0.0.0:<port>` must match the upstream in `nginx.conf`). Confirm with `docker exec local-llm-nginx wget -qO- http://ollama:11434/api/tags` (replace `11434` with your configured port) and check `docker logs local-llm-ollama` if the container is crashing (RAM/GPU).

**Gated Hugging Face models** — Set `HF_TOKEN` in the wizard or `.env`.

**`curl: (56) ... 404` on install** — The GitHub repo must be **public** for `raw.githubusercontent.com/.../install.sh` to work. Private repos return 404 to anonymous curl. Fix: **Settings → Change repository visibility → Public**, wait a minute, then retry. Until then, install from a local clone: `bash install.sh`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
