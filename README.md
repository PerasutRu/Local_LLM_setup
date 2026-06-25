# Local LLM Setup

TUI wizard for hosting local LLMs with **Ollama**, **vLLM**, **llama.cpp**, and **SGLang**. Detects your OS and hardware, checks dependencies, and generates `docker-compose.yaml`, optional `nginx.conf`, `api_keys.map`, and run commands.

## Features

- Auto-detect OS (Linux, macOS, Windows/WSL), GPU, Docker, CUDA, ROCm, nginx
- Keyboard-driven TUI (↑/↓ navigate, Space select, Enter confirm)
- Quick or full configuration per framework
- Model validation (Ollama registry, Hugging Face, GGUF for llama.cpp)
- Capability flags: vision, audio, tool calling, speculative decoding (MTP)
- Optional nginx reverse proxy with API key auth
- Save/load YAML profiles

## Quick start

```bash
# Install
pip install -e ".[dev]"

# Interactive wizard
local-llm-setup tui

# Check host dependencies
local-llm-setup doctor

# Generate from profile
local-llm-setup generate --config profiles/sample.yaml
```

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

## Troubleshooting

**Docker not found** — Install Docker Desktop (macOS/Windows) or run the [Docker install script](https://get.docker.com) on Linux.

**GPU not available in container** — Install NVIDIA drivers and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

**vLLM/SGLang validation errors on Mac** — Use Ollama or llama.cpp on Apple Silicon.

**Port already in use** — Change the framework port in full config mode or stop the conflicting service.

**Gated Hugging Face models** — Set `HF_TOKEN` in the wizard or `.env`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
