"""Full-mode TUI field definitions and helpers."""

from __future__ import annotations

from dataclasses import dataclass

from textual.containers import VerticalScroll
from textual.widgets import Input, Static

from local_llm_setup.markup import style_section
from local_llm_setup.models.config import Framework


@dataclass(frozen=True)
class FieldSpec:
    id: str
    label: str
    placeholder: str = ""
    hint: str = ""
    password: bool = False
    default: str = ""


def _common_model_fields() -> list[FieldSpec]:
    return [
        FieldSpec("ctx-input", "context_length", default="8192", hint="Max context window (tokens)"),
        FieldSpec(
            "quant-input",
            "quantization",
            placeholder="awq, gptq, fp8, ...",
            hint="Optional quantization mode (vLLM/SGLang)",
        ),
    ]


def model_fields(framework: Framework) -> list[FieldSpec]:
    fields = [
        FieldSpec(
            "model-input",
            "model.name",
            placeholder=_model_placeholder(framework),
            hint=_model_hint(framework),
        ),
        *_common_model_fields(),
    ]
    if framework in (Framework.VLLM, Framework.SGLANG):
        fields.extend(
            [
                FieldSpec("tp-input", "tensor_parallel", default="1", hint="Tensor parallel size (GPU count)"),
                FieldSpec(
                    "hf-token-env-input",
                    "hf_token_env",
                    default="HF_TOKEN",
                    hint="Environment variable name for Hugging Face token",
                ),
                FieldSpec(
                    "hf-token-input",
                    "hf_token",
                    placeholder="hf_...",
                    hint="Hugging Face token (gated/private models)",
                    password=True,
                ),
            ]
        )
    if framework == Framework.VLLM:
        fields.extend(vllm_serve_fields())
    if framework == Framework.OLLAMA:
        fields.append(
            FieldSpec(
                "ollama-parallel-input",
                "OLLAMA_NUM_PARALLEL",
                default="1",
                hint="Ollama env: concurrent request slots (extra_env)",
            )
        )
    if framework == Framework.LLAMACPP:
        fields.append(
            FieldSpec(
                "llama-ngl-input",
                "n_gpu_layers",
                placeholder="99",
                hint="GPU layers — added to extra_args as --n-gpu-layers",
            )
        )
    return fields


def vllm_serve_fields() -> list[FieldSpec]:
    return [
        FieldSpec(
            "vllm-gpu-mem-input",
            "gpu_memory_utilization",
            placeholder="0.3",
            hint="--gpu-memory-utilization (fraction of VRAM, e.g. 0.3)",
        ),
        FieldSpec(
            "vllm-max-seqs-input",
            "max_num_seqs",
            placeholder="1",
            hint="--max-num-seqs concurrent sequences",
        ),
        FieldSpec(
            "vllm-tool-parser-input",
            "tool_call_parser",
            placeholder="gemma4",
            hint="--tool-call-parser (e.g. gemma4, hermes)",
        ),
        FieldSpec(
            "vllm-reasoning-parser-input",
            "reasoning_parser",
            placeholder="gemma4",
            hint="--reasoning-parser",
        ),
        FieldSpec(
            "vllm-kv-cache-input",
            "kv_cache_dtype",
            placeholder="auto",
            hint="--kv-cache-dtype",
        ),
        FieldSpec(
            "vllm-mm-limit-input",
            "limit_mm_per_prompt",
            placeholder='{"image": 4, "audio": 1}',
            hint="--limit-mm-per-prompt JSON for vision/audio",
        ),
        FieldSpec(
            "vllm-trust-remote-input",
            "trust_remote_code",
            default="false",
            hint="--trust-remote-code (true/false)",
        ),
        FieldSpec(
            "vllm-prefix-cache-input",
            "enable_prefix_caching",
            default="false",
            hint="--enable-prefix-caching (true/false)",
        ),
    ]


def vllm_runtime_fields() -> list[FieldSpec]:
    return [
        FieldSpec(
            "publish-port-input",
            "publish_port",
            hint="Host port published (container listens on port above, e.g. 8002:8000)",
        ),
        FieldSpec(
            "gpu-device-ids-input",
            "gpu_device_ids",
            placeholder="0",
            hint="Comma-separated GPU ids → device_ids + NVIDIA_VISIBLE_DEVICES",
        ),
        FieldSpec("ipc-input", "ipc", placeholder="host", hint="Docker ipc mode (e.g. host)"),
        FieldSpec(
            "volumes-input",
            "extra_volumes",
            placeholder="/host/path:/container/path",
            hint="Volume mounts, one per line",
        ),
        FieldSpec(
            "command-shell-input",
            "command_shell",
            placeholder="exec vllm serve ...",
            hint="Optional: full bash -lc script (overrides generated vllm serve)",
        ),
    ]


def runtime_fields(framework: Framework) -> list[FieldSpec]:
    fields = [
        FieldSpec("port-input", "port", hint="Container listen port (e.g. 8000)"),
        FieldSpec("bind-host-input", "bind_host", default="127.0.0.1", hint="Host bind address (127.0.0.1 or 0.0.0.0)"),
        FieldSpec("image-tag-input", "image_tag", hint="Docker image override (empty = provider default)"),
        FieldSpec("shm-input", "shm_size", default=_default_shm(framework), hint="Docker shm_size"),
        FieldSpec(
            "extra-env-input",
            "extra_env",
            placeholder="HF_HOME=/root/.cache/huggingface",
            hint="Extra container environment variables (one KEY=value per line)",
        ),
        FieldSpec(
            "extra-args-input",
            "extra_args",
            placeholder="--dtype auto",
            hint="Extra CLI args appended to vllm serve",
        ),
    ]
    if framework in (Framework.VLLM, Framework.SGLANG):
        fields.insert(
            4,
            FieldSpec("gpu-count-input", "gpu_count", default="1", hint="GPU devices reserved (when gpu_device_ids empty)"),
        )
    if framework == Framework.VLLM:
        fields.extend(vllm_runtime_fields())
    if framework == Framework.OLLAMA:
        fields.extend(
            [
                FieldSpec(
                    "ollama-models-input",
                    "OLLAMA_MODELS",
                    default="/root/.ollama",
                    hint="Ollama models path inside container (volume is fixed)",
                ),
                FieldSpec(
                    "ollama-host-input",
                    "OLLAMA_HOST",
                    default="0.0.0.0:11434",
                    hint="Ollama listen address inside container",
                ),
            ]
        )
    return fields


def setup_fields() -> list[FieldSpec]:
    return [
        FieldSpec("profile-name-input", "profile_name", default="default", hint="Saved profile filename"),
        FieldSpec("output-dir-input", "output_dir", default="./output", hint="Generated compose output directory"),
    ]


def nginx_basic_fields() -> list[FieldSpec]:
    return [
        FieldSpec("nginx-port", "listen_port", default="8080", hint="Host port exposed by nginx"),
    ]


def nginx_advanced_fields() -> list[FieldSpec]:
    return [
        FieldSpec("nginx-server-name", "server_name", default="_", hint="nginx server_name (_ = any host)"),
        FieldSpec("nginx-bind-host", "bind_host", default="0.0.0.0", hint="Host bind for nginx published port"),
        FieldSpec(
            "nginx-body-size",
            "client_max_body_size",
            default="50m",
            hint="Max upload body size (e.g. 50m, 1g)",
        ),
        FieldSpec(
            "nginx-proxy-timeout",
            "proxy_read_timeout",
            default="600s",
            hint="Proxy read/send timeout",
        ),
    ]


def _model_placeholder(framework: Framework) -> str:
    return {
        Framework.OLLAMA: "llama3.2",
        Framework.VLLM: "meta-llama/Meta-Llama-3-8B-Instruct",
        Framework.LLAMACPP: "/models/model.gguf",
        Framework.SGLANG: "meta-llama/Meta-Llama-3-8B-Instruct",
    }[framework]


def _model_hint(framework: Framework) -> str:
    return {
        Framework.OLLAMA: "Ollama registry name (e.g. llama3.2:latest)",
        Framework.VLLM: "Hugging Face model id — safetensors, not GGUF",
        Framework.LLAMACPP: "Path or URL to GGUF file (mounted at ./models)",
        Framework.SGLANG: "Hugging Face model id",
    }[framework]


def _default_shm(framework: Framework) -> str:
    return "16gb" if framework in (Framework.VLLM, Framework.SGLANG) else "8gb"


def mount_fields(body: VerticalScroll, fields: list[FieldSpec], values: dict[str, str]) -> None:
    for spec in fields:
        body.mount(Static(style_section(spec.label + ":"), classes="section-label"))
        if spec.hint:
            body.mount(Static(f"  {spec.hint}", classes="skill-line"))
        body.mount(
            Input(
                value=values.get(spec.id, spec.default),
                placeholder=spec.placeholder,
                id=spec.id,
                password=spec.password,
            )
        )


def read_field(body: VerticalScroll, field_id: str, default: str = "") -> str:
    try:
        return body.query_one(f"#{field_id}", Input).value.strip()
    except Exception:
        return default


def parse_extra_env(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            env[key] = value.strip()
    return env


def format_extra_env(env: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in env.items())


def parse_extra_args(text: str) -> list[str]:
    import shlex

    text = text.strip()
    if not text:
        return []
    return shlex.split(text)


def format_extra_args(args: list[str]) -> str:
    import shlex

    return shlex.join(args) if args else ""


def format_volume_lines(volumes: list[str]) -> str:
    return "\n".join(volumes)


def parse_bool(text: str) -> bool:
    return text.strip().lower() in ("1", "true", "yes", "on")


def parse_volume_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def parse_csv_ids(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]
