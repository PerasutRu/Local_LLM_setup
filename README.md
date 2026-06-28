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
- **Multiple isolated stacks** — one profile per instance, output under `llm_local/output/{profile_name}/`, unique Docker project/container names
- **Cross-instance port allocation** — auto-avoid conflicts for providers (Ollama, vLLM, …), nginx, and Cloudflare tunnel sidecars
- **Instance management** — list, edit, deploy, stop, and delete profiles (`/instances`, `/delete-profile`, `local-llm-setup instances`)
- **Per-provider model cache** — bind-mounted `model-{provider}/` folders per profile (custom host path in Quick/Full or YAML)
- **Smart deploy pulls** — skip `docker pull` and `ollama pull` when images/models are already on the host
- **Slash command bar** — name-only suggestions, ↑↓ multi-match selection, Enter runs highlighted command; command mode keeps menus visible over deploy logs
- Access URLs for localhost, **public IP** (auto-detected), private LAN, and Cloudflare tunnel — plus curl smoke tests
- Save/load/delete YAML profiles
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
| `~/.local-llm-setup/llm_local/output` | Generated compose/nginx files (one subfolder per profile) |
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
local-llm-setup stop --config llm_local/profiles/sample.yaml
local-llm-setup stop --all                    # stop every running instance
local-llm-setup instances                     # list profiles + status
```

**Full guide (Thai):** [GUIDE.md](GUIDE.md) — install, TUI walkthrough, **Quick/Full parameter reference per provider** · **Architecture:** [UML.md](UML.md)

## CLI commands

| Command | Description |
|---------|-------------|
| `tui` | Interactive wizard |
| `doctor` | Check Docker, GPU, CUDA, nginx (`--json` for machine output) |
| `detect` | Alias for `doctor` |
| `generate` | Write `llm_local/output/{profile}/` from a profile (`--run` to deploy, `--dry-run` to validate) |
| `run` | Start a generated stack (`--no-pull` to skip image pull; deploy also skips pulls when images/models are already local) |
| `stop` | Stop one stack (`--config` profile, `--all` every running instance, `--volumes` remove data) |
| `instances` | List saved profiles, ports, and running/stopped status (`--json`) |
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

**With nginx enabled**, nginx publishes the main entry port (e.g. `8080`). Provider containers also publish their listen port on the host (e.g. `0.0.0.0:11434` for Ollama, `0.0.0.0:11435` for a second Ollama instance) so each stack stays addressable directly. Traffic through nginx:

```
Client → host:8080 (nginx) → ollama:11434 (internal)
Client → host:11434 (direct Ollama API)
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

Press `/` to focus the command bar and insert `/`. The **suggestion panel** stays hidden until the input starts with `/`.

**Filtering** — suggestions match **canonical command names** only (not Thai descriptions or aliases). Typing `/p` shows `/providers`, not `/instances`. Aliases such as `/profiles`, `/list`, `/curl`, and `/delete` still **run** on Enter but never appear in the filtered list.

**Keyboard**

| Key | Action |
|-----|--------|
| **↑↓** | Move highlight among matches (typed prefix stays — e.g. `/de` keeps all of `/delete-profile`, `/deploy`, `/delete-container` visible) |
| **Enter** | Run the **highlighted** command (or the typed command when only one match) |
| **Tab** | Autocomplete by command name (requires at least one typed character after `/`; press Tab again to cycle when several names share a prefix) |

Without a leading `/`, Tab moves focus to the next widget as usual. While the command bar is focused, deploy logs and access URLs shrink/hide so the suggestion list stays readable.

| Command | Action |
|---------|--------|
| `/help` | List all commands |
| `/instances` | List profiles — edit, deploy, or stop per instance (aliases: `/profiles`, `/list`) |
| `/delete-profile` | Delete saved profile YAML + deploy artifacts — multi-select, delete all, prompts for Docker volumes and model cache |
| `/providers` | Switch Ollama / vLLM |
| `/deploy` | Regenerate and start the current profile's stack |
| `/test` | Run curl smoke tests (uses compose port + `api_keys.map` when auth is on) |
| `/stop` | Pick instance to stop, stop all running, or `/stop my-profile` |
| `/delete-container` | Same picker as `/stop` but removes volumes (`/delete` — not profile configs) |
| `/doctor` | Jump back to Host Doctor |

Press `s` to open the **stop picker** (stop all or choose one instance).

### Multiple instances

Each profile gets its own output folder and Docker isolation:

```
llm_local/
├── profiles/
│   ├── smollm-1.yaml
│   └── smollm-2.yaml
└── output/
    ├── smollm-1/          # docker-compose.yaml, nginx.conf, …
    │   ├── model-ollama/  # downloaded models (bind-mounted into container)
    │   └── model-vllm/    # HF cache when using vLLM
    └── smollm-2/
```

- **Profile name** → subfolder name → Docker project `local-llm-{profile}` and containers `local-llm-{profile}-ollama`, etc.
- **Model cache** — each provider gets a dedicated host folder per profile (default: `output/model-{provider}/`). Set a custom path in Full → Runtime or Quick → model step (`model_cache_host_path` in YAML).
- Ports are reserved across other profiles so two Ollama stacks get `11434` and `11435`, nginx `8080` and `8081`, and so on.
- Edit a profile via `/instances` → **Edit**, change settings, then **Generate & deploy** or `/deploy` — only that stack restarts.
- Delete profiles via `/delete-profile` or `/instances` → **Delete profiles…** — select profiles, then choose **Docker volumes** and **model cache** removal separately. Deploy files and YAML are always removed; model cache is optional.

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

| Mode | Best for | Wizard steps |
|------|----------|--------------|
| **Quick** | Fast path — model, optional Docker image, capabilities, nginx | Model → Capabilities → Nginx → Summary |
| **Full** | Production tuning — ports, GPU, env, vLLM flags, nginx timeouts | Model → **Runtime & Docker** → Capabilities → Nginx → Summary |

**Quick** uses sensible defaults per provider (port, `bind_host`, `shm_size`, context length). Toggle **Bind to 0.0.0.0** under Capabilities to expose on LAN.

**Full** adds a **Runtime & Docker** step — set `bind_host`, `port`, `publish_port`, GPU ids, volumes, etc. instead of the Quick “expose publicly” toggle.

Both modes let you override the provider Docker image (Quick: Model step; Full: Runtime step). Leave empty to use the default shown in the wizard.

**Full walkthrough with parameter examples (Thai):** [GUIDE.md §7 — Quick vs Full setup](GUIDE.md#7-quick-setup-vs-full-setup-แต่ละ-provider)

### Default Docker images

| Provider | Default image | Notes |
|----------|---------------|-------|
| Ollama | `ollama/ollama:latest` | |
| vLLM | `vllm/vllm-openai:latest` | AMD hosts use `rocm/vllm:latest` automatically |
| llama.cpp | `ghcr.io/ggerganov/llama.cpp:server` | |
| SGLang | `lmsysorg/sglang:latest` | |

Set a custom image in the TUI or profile YAML as `image_tag`. Example: `ollama/ollama:0.5.4` when `latest` is incompatible.

### Shared parameters (all providers)

| Parameter | Meaning | Default | Example |
|-----------|---------|---------|---------|
| `profile_name` | Instance name → output folder, Docker project, container names | `default` | `ollama-prod`, `gemma-vllm` |
| `model.name` | Model id per provider (see below) | provider default | `llama3.2`, `meta-llama/Meta-Llama-3-8B-Instruct` |
| `context_length` | Max context window (tokens) | `8192` | `32768`, `80000` |
| `image_tag` | Docker image override | provider default | `vllm/vllm-openai:v0.6.3` |
| `model_cache_host_path` | Host folder for downloaded models | `output/model-{provider}/` | `/mnt/nvme/ollama`, `/data/hf-cache` |
| `port` | Port the service **listens on inside the container** | 11434 / 8000 / 8080 / 30000 | `8000`, `11435` |
| `publish_port` | Host port mapped to `port` (Full mode) | same as `port` | `8002` → `8002:8000` |
| `bind_host` | Host IP to bind | `127.0.0.1` | `0.0.0.0` (all interfaces) |
| `shm_size` | Container shared memory | `8gb` / `16gb` | `32gb` for large models |
| `extra_env` | Extra env vars (one `KEY=value` per line) | empty | `OLLAMA_NUM_PARALLEL=4` |
| `extra_args` | Extra CLI args appended to serve command | empty | `--dtype auto` |
| `gpu_count` | GPUs reserved when `gpu_device_ids` empty | `1` | `2`, `4` |
| `gpu_device_ids` | Pin specific GPUs (comma-separated) | empty | `0`, `0,1` |
| `ipc` | Docker IPC mode | empty | `host` (recommended for some vLLM setups) |
| `extra_volumes` | Extra bind mounts (one per line) | empty | `/mnt/hf:/root/.cache/huggingface` |
| `command_shell` | Bash script overriding generated start command | empty | vLLM advanced only |

**Capabilities:** vision, audio (vLLM only — bootstraps `vllm[audio]`), tool calling, MTP/speculative decoding (+ drafter model), and **Bind to 0.0.0.0** (Quick only).

**Nginx (Full):** `listen_port`, `server_name`, `bind_host`, `client_max_body_size`, `proxy_read_timeout`, CORS, cloudflared tunnel, API key auth.

### Provider quick reference

#### Ollama

| | Quick | Full extras |
|---|-------|-------------|
| **Model** | Ollama tag (`llama3.2`, `qwen2.5:7b`) | `context_length`, `OLLAMA_NUM_PARALLEL` |
| **Runtime** | defaults (port `11434`, `shm_size=8gb`) | `port`, `bind_host`, `OLLAMA_MODELS`, `OLLAMA_HOST`, cache path |
| **After deploy** | `ollama pull <model>` (skipped if already local) | same |

```yaml
# Full example — parallel requests + nginx
profile_name: ollama-prod
frameworks:
  - framework: ollama
    mode: full
    model: { name: llama3.2, context_length: 8192 }
    port: 11434
    bind_host: 0.0.0.0
    model_cache_host_path: /mnt/nvme/ollama
    extra_env: { OLLAMA_NUM_PARALLEL: "4" }
nginx: { enabled: true, listen_port: 8080, api_key_auth: true }
```

#### vLLM

| | Quick | Full extras |
|---|-------|-------------|
| **Model** | Hugging Face repo (safetensors, **not GGUF**) | `quantization`, `tensor_parallel`, HF token, serve flags (see below) |
| **Runtime** | port `8000`, `gpu_count=1`, `shm_size=16gb` | `publish_port`, `gpu_device_ids`, `ipc`, `command_shell` |
| **Requires** | NVIDIA/AMD GPU | same |

**vLLM-only model fields:** `gpu_memory_utilization`, `max_num_seqs`, `tool_call_parser`, `reasoning_parser`, `kv_cache_dtype`, `limit_mm_per_prompt`, `trust_remote_code`, `enable_prefix_caching`.

**Gated models:** set `HF_TOKEN` in wizard (Full) or `.env` (Quick).

#### llama.cpp

| | Quick | Full extras |
|---|-------|-------------|
| **Model** | GGUF path in container (`/models/foo.gguf`) or URL | `context_length`, `n_gpu_layers` → `--n-gpu-layers` |
| **Cache** | bind `./model-llamacpp` → `/models` | custom `model_cache_host_path` |
| **GPU** | optional (CPU ok; Metal on Apple Silicon) | tune layers via `n_gpu_layers` |

Place `.gguf` files in `llm_local/output/{profile}/model-llamacpp/` before deploy, or set a custom cache path.

#### SGLang

| | Quick | Full extras |
|---|-------|-------------|
| **Model** | Hugging Face repo | `quantization`, `tensor_parallel`, HF token |
| **Runtime** | port `30000`, `gpu_count=1` | `publish_port`, `gpu_device_ids`, MTP drafter model |
| **Requires** | GPU (no Apple Silicon, no GGUF) | same |

### When to use which mode

| Scenario | Recommendation |
|----------|----------------|
| First try / laptop dev | **Quick** + Ollama or llama.cpp |
| Standard HF model, 1 GPU | **Quick** + vLLM or SGLang |
| AWQ/GPTQ, multimodal, audio, pin GPU | **Full** + vLLM |
| Multiple stacks on one host | **Full** — distinct `profile_name`, `port`, `publish_port` |
| GGUF on CPU or Mac | **Quick/Full** + llama.cpp + `n_gpu_layers` in Full |

In Full mode, use **bind_host** on the Runtime step instead of the “expose publicly” capability toggle.

## vLLM production config

Full mode maps to real-world `docker compose` setups (e.g. Gemma 4 multimodal with audio):

| Setting | Full mode field | Compose effect |
|---------|-----------------|----------------|
| Host `8002` → container `8000` | `port` = `8000`, `publish_port` = `8002` | `ports: ["0.0.0.0:8002:8000"]` |
| Pin GPU 0 | `gpu_device_ids` = `0` | `device_ids: ["0"]` + `NVIDIA_VISIBLE_DEVICES` |
| Model cache path | `model_cache_host_path` | Host folder for downloaded models (default: `output/model-{provider}/`) |
| HF cache volume | `extra_volumes` | Override container mount entirely (advanced; skips default cache mount when same container path) |
| `ipc: host` | `ipc` = `host` | `ipc: host` |
| Env vars | `extra_env` | `HF_HOME`, `PYTORCH_CUDA_ALLOC_CONF`, … |
| Serve flags | vLLM model fields | `entrypoint: [vllm, serve]` + flags |
| Audio models | Capabilities → **Audio** | `bash -lc` bootstrap installs `vllm[audio]` then `exec vllm serve` |

**vLLM-only model fields:** `gpu_memory_utilization`, `max_num_seqs`, `tool_call_parser`, `reasoning_parser`, `kv_cache_dtype`, `limit_mm_per_prompt`, `trust_remote_code`, `enable_prefix_caching`.

**Example (Gemma 4 AWQ):**

| Step | Values |
|------|--------|
| Model | `cyankiwi/gemma-4-E4B-it-AWQ-INT4`, context `80000`, quantization `awq`, gpu_mem `0.3`, parsers `gemma4`, limit_mm `{"image": 4, "audio": 1}` |
| Runtime | port `8000`, publish `8002`, gpu_device_ids `0`, ipc `host`, shm `32gb` |
| Capabilities | tool calling, vision, **audio** |
| Nginx | `client_max_body_size=100m`, `proxy_read_timeout=1800s` |

```yaml
profile_name: gemma-vllm
frameworks:
  - framework: vllm
    mode: full
    model:
      name: cyankiwi/gemma-4-E4B-it-AWQ-INT4
      context_length: 80000
      quantization: awq
    capabilities: { text: true, vision: true, audio: true, tool_calling: true }
    port: 8000
    publish_port: 8002
    gpu_device_ids: ["0"]
    ipc: host
    shm_size: 32gb
    vllm:
      gpu_memory_utilization: 0.3
      tool_call_parser: gemma4
      reasoning_parser: gemma4
      limit_mm_per_prompt: '{"image": 4, "audio": 1}'
hf_token: hf_xxxxxxxx
```

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

Each profile writes to **`llm_local/output/{profile_name}/docker-compose.yaml`**. Services join a per-profile bridge network (`local-llm-setup-{profile}-local_llm`) with explicit `container_name` values so multiple stacks can run on one host.

```bash
cd llm_local/output/smollm-1
docker compose -p local-llm-smollm-1 pull
docker compose -p local-llm-smollm-1 up -d
docker compose ps
docker compose logs -f nginx ollama
docker compose down          # stop
docker compose down -v       # stop + remove volumes
```

When **nginx is enabled**, nginx exposes the main HTTP port and the provider publishes its listen port (e.g. `0.0.0.0:11434:11434`). Nginx still proxies to `service_name:port` inside the stack. An optional **cloudflared** sidecar provides a public `trycloudflare.com` URL per instance.

When **nginx is disabled**, only the framework port is published (e.g. `127.0.0.1:11434`).

CLI shortcuts:

```bash
local-llm-setup generate --config llm_local/profiles/smollm-1.yaml --run
local-llm-setup run --config llm_local/profiles/smollm-1.yaml
local-llm-setup stop --config llm_local/profiles/smollm-1.yaml
local-llm-setup stop --all
local-llm-setup stop --config llm_local/profiles/smollm-1.yaml --volumes
local-llm-setup instances
```

## Output files

Per profile under `llm_local/output/{profile_name}/`:

- `docker-compose.yaml` — isolated services, healthchecks, GPU reservations, model-cache bind mounts
- `model-{provider}/` — downloaded models (Ollama blobs, Hugging Face cache, etc.) when using the default cache path
- `.env` — secrets (e.g. `HF_TOKEN`)
- `nginx.conf` — reverse proxy (if enabled)
- `api_keys.map` — API key map for nginx (if enabled)
- `RUN.md` — copy-paste run commands
- `commands.log` — append-only log of every shell command executed during deploy/stop/test (for debugging)
- `ACCESS.md` — access URLs and example curl commands

When nginx is enabled, the framework binds on `0.0.0.0` inside the container (`OLLAMA_HOST=0.0.0.0:<port>`) and publishes that port on the host alongside nginx. An optional **cloudflared** sidecar provides a public `trycloudflare.com` URL.

## Troubleshooting

**Docker not found** — Install Docker Desktop (macOS/Windows) or run the [Docker install script](https://get.docker.com) on Linux.

**GPU not available in container** — Install NVIDIA drivers and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

**vLLM/SGLang validation errors on Mac** — Use Ollama or llama.cpp on Apple Silicon.

**Port already in use** — Ports are auto-adjusted to the next free value during `generate` (warnings are printed). Reserved ports include other profiles' nginx and provider listen ports, so running two Ollama stacks yields `11434` and `11435`. `/test` and `ACCESS.md` read the actual port from `docker-compose.yaml`.

**Running multiple stacks** — Use distinct `profile_name` values in Full mode (or save separate YAML profiles). Each instance has its own output folder and Docker project. Stop one with `/stop my-profile` or `local-llm-setup stop --config llm_local/profiles/my-profile.yaml`; stop all with `/stop` → **Stop all** or `local-llm-setup stop --all`.

**Stale tunnel URL** — Cloudflare quick-tunnel URLs change every time the tunnel container restarts. Run `docker logs local-llm-{profile}-tunnel 2>&1 | grep trycloudflare` or redeploy to refresh `ACCESS.md`.

**`401 Unauthorized` on `/api/*` or `/v1/*`** — nginx API key auth is enabled. Pass `X-API-Key` or `Authorization: Bearer` with the key from `llm_local/output/api_keys.map`. OpenAI SDK users set `api_key=` to that value. Regenerate nginx with `/deploy` after upgrading if Bearer auth was added recently.

**`502 Bad Gateway` on `/api/*` while `/health` is ok** — nginx is up but cannot reach the LLM backend. Regenerate and redeploy so `docker-compose.yaml` and `nginx.conf` use the same provider port (`OLLAMA_HOST: 0.0.0.0:<port>` must match the upstream in `nginx.conf`). Confirm with `docker exec local-llm-{profile}-nginx wget -qO- http://ollama:11434/api/tags` (replace `11434` with your configured port) and check `docker logs local-llm-{profile}-ollama` if the container is crashing (RAM/GPU).

**Cannot reach the API from outside** — Use the **Cloudflare tunnel** URL (`https://….trycloudflare.com`) or ensure the **public IP** port is allowed in the host firewall and forwarded on the router. Do not use `192.168.x.x` from outside your LAN. The `openai` / `ollama` lines in the TUI follow public IP (or LAN if public IP could not be detected).

**Gated Hugging Face models** — Set `HF_TOKEN` in the wizard or `.env`.

**`curl: (56) ... 404` on install** — The GitHub repo must be **public** for `raw.githubusercontent.com/.../install.sh` to work. Private repos return 404 to anonymous curl. Fix: **Settings → Change repository visibility → Public**, wait a minute, then retry. Until then, install from a local clone: `bash install.sh`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
