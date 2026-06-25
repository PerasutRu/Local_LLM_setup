"""Ollama framework plugin."""

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


class OllamaPlugin(FrameworkPlugin):
    meta = FrameworkMeta(
        framework=Framework.OLLAMA,
        display_name="Ollama",
        description="Easy local model hosting with built-in model registry",
        default_port=11434,
        default_image="ollama/ollama:latest",
        supports_gguf=False,
        supports_hf=False,
        supports_ollama_registry=True,
        supports_vision=True,
        supports_audio=False,
        supports_tool_calling=True,
        supports_mtp=False,
        requires_gpu=False,
        quick_defaults={"model": "llama3.2", "context_length": 8192},
    )

    def default_config(self, model_name: str = "llama3.2", mode: str = "quick") -> FrameworkConfig:
        return FrameworkConfig(
            framework=Framework.OLLAMA,
            mode=ConfigMode(mode),
            model=ModelConfig(name=model_name or "llama3.2", context_length=8192),
            capabilities=Capabilities(text=True),
            port=11434,
            bind_host="127.0.0.1",
            image_tag=self.meta.default_image,
            shm_size="8gb",
        )

    def validate(self, config: FrameworkConfig, host: HostInfo | None = None) -> list[ValidationIssue]:
        issues = validate_model_name(Framework.OLLAMA, config.model.name)
        issues.extend(check_capabilities(self.meta, config.capabilities))
        if host and host.gpu_vendor == GPUVendor.NONE:
            issues.append(
                ValidationIssue(
                    level="info",
                    message="Ollama runs on CPU but will be slower without GPU.",
                )
            )
        return issues

    def image_for_host(self, host: HostInfo | None, tag: str | None = None) -> str:
        return tag or self.meta.default_image
