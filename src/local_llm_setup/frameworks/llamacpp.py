"""llama.cpp server framework plugin."""

from __future__ import annotations

from local_llm_setup.frameworks.base import FrameworkMeta, FrameworkPlugin, check_capabilities
from local_llm_setup.models.config import (
    Capabilities,
    ConfigMode,
    Framework,
    FrameworkConfig,
    GPUVendor,
    HostInfo,
    ModelConfig,
    ValidationIssue,
)
from local_llm_setup.models.validation import validate_model_name


class LlamaCppPlugin(FrameworkPlugin):
    meta = FrameworkMeta(
        framework=Framework.LLAMACPP,
        display_name="llama.cpp",
        description="Efficient GGUF inference server (CPU/GPU)",
        default_port=8080,
        default_image="ghcr.io/ggerganov/llama.cpp:server",
        supports_gguf=True,
        supports_hf=False,
        supports_ollama_registry=False,
        supports_vision=True,
        supports_audio=False,
        supports_tool_calling=True,
        supports_mtp=False,
        requires_gpu=False,
        quick_defaults={"model": "/models/model.gguf", "context_length": 8192},
    )

    def default_config(self, model_name: str = "/models/model.gguf", mode: str = "quick") -> FrameworkConfig:
        return FrameworkConfig(
            framework=Framework.LLAMACPP,
            mode=ConfigMode(mode),
            model=ModelConfig(name=model_name or "/models/model.gguf", context_length=8192),
            capabilities=Capabilities(text=True),
            port=8080,
            bind_host="127.0.0.1",
            image_tag=self.meta.default_image,
            shm_size="8gb",
            extra_args=["--host", "0.0.0.0", "--port", "8080"],
        )

    def validate(self, config: FrameworkConfig, host: HostInfo | None = None) -> list[ValidationIssue]:
        issues = validate_model_name(Framework.LLAMACPP, config.model.name)
        issues.extend(check_capabilities(self.meta, config.capabilities))

        if host and host.gpu_vendor == GPUVendor.APPLE:
            issues.append(
                ValidationIssue(
                    level="info",
                    message="llama.cpp on Apple Silicon benefits from Metal; mount GGUF and use -ngl flags.",
                )
            )
        return issues
