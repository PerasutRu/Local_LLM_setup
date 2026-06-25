# Local LLM Setup

TUI wizard for hosting local LLMs with **Ollama**, **vLLM**, **llama.cpp**, and **SGLang**. Detects your OS and hardware, checks dependencies, generates `docker-compose.yaml`, optional `nginx.conf`, and can deploy the stack with one command.

## Features

- Auto-detect OS (Linux, macOS, Windows/WSL), GPU, Docker, CUDA, ROCm, nginx
- Keyboard-driven TUI (↑/↓ navigate, Space select, Enter confirm, `/` slash commands)
- Quick or full configuration per framework
- Model validation (Ollama registry, Hugging Face, GGUF for llama.cpp)
- Capability flags: vision, audio, tool calling, speculative decoding (MTP)
- Optional nginx reverse proxy with API key auth and Cloudflare quick tunnel
- Generate & deploy from TUI or CLI (`generate --run`, `run`, `stop`)
- Access URLs for localhost, LAN, and tunnel — plus curl smoke tests
- Save/load YAML profiles

## Quick start

```bash
# Install
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Interactive wizard (generate + start Docker by default)
local-llm-setup tui

# Check host dependencies
local-llm-setup doctor

# Generate from profile
local-llm-setup generate --config profiles/sample.yaml

# Generate and deploy in one step
local-llm-setup generate --config profiles/sample.yaml --run

# Start or stop an existing stack
local-llm-setup run --config profiles/sample.yaml
local-llm-setup stop
```

**Full guide (Thai):** [GUIDE.md](GUIDE.md) · **Architecture:** [UML.md](UML.md)

## CLI commands

| Command | Description |
|---------|-------------|
| `tui` | Interactive wizard |
| `doctor` | Check Docker, GPU, CUDA, nginx (`--json` for machine output) |
| `detect` | Alias for `doctor` |
| `generate` | Write `output/` from a profile (`--run` to deploy, `--dry-run` to validate) |
| `run` | Start a generated stack (`--no-pull` to skip image pull) |
| `stop` | Stop the stack (`--volumes` to remove data volumes) |
| `save` | Save a config as a named profile |

After `generate` or `run`, the CLI prints **access URLs** (localhost, LAN IP, and Cloudflare tunnel when nginx is enabled).

## TUI slash commands

Press `/` in the wizard to open the command bar:

| Command | Action |
|---------|--------|
| `/help` | List commands |
| `/providers` | Switch Ollama / vLLM |
| `/deploy` | Regenerate and start the stack |
| `/test` | Run curl smoke tests against the running API |
| `/stop` | Stop containers (keep volumes) |
| `/delete-container` | Stop and remove containers + volumes |
| `/doctor` | Jump back to Host Doctor |

Press `s` to stop the running stack from any screen.

## Dockerized setup app

Run the wizard without installing Python on the host:

```bash
docker build -t local-llm-setup .
docker run -it --rm -v "$(pwd)/output:/workspace/output" local-llm-setup tui
```

Generated files appear in `./output/`.

## Framework notes

| Framework   | Model source        | GGUF | GPU required |
|------------|---------------------|------|--------------|
| Ollama     | Ollama model name   | No   | No           |
| vLLM       | Hugging Face repo   | No   | Yes (NVIDIA/AMD) |
| llama.cpp  | GGUF path/URL       | Yes  | No           |
| SGLang     | Hugging Face repo   | No   | Yes          |

## Output files

- `docker-compose.yaml` — services with healthchecks and GPU reservations
- `.env` — secrets (e.g. `HF_TOKEN`)
- `nginx.conf` — reverse proxy (if enabled)
- `api_keys.map` — API key map for nginx (if enabled)
- `RUN.md` — copy-paste run commands
- `ACCESS.md` — access URLs and example curl commands

When nginx is enabled, the framework binds to `127.0.0.1` internally and only nginx is exposed on `0.0.0.0`. An optional **cloudflared** sidecar provides a public `trycloudflare.com` URL.

## Troubleshooting

**Docker not found** — Install Docker Desktop (macOS/Windows) or run the [Docker install script](https://get.docker.com) on Linux.

**GPU not available in container** — Install NVIDIA drivers and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

**vLLM/SGLang validation errors on Mac** — Use Ollama or llama.cpp on Apple Silicon.

**Port already in use** — Default nginx port is `8080`. Change it in full config mode or stop the conflicting service.

**Gated Hugging Face models** — Set `HF_TOKEN` in the wizard or `.env`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
