"""SGLang framework plugin."""

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


class SglangPlugin(FrameworkPlugin):
    meta = FrameworkMeta(
        framework=Framework.SGLANG,
        display_name="SGLang",
        description="Fast structured generation and serving for HF models",
        default_port=30000,
        default_image="lmsysorg/sglang:latest",
        supports_gguf=False,
        supports_hf=True,
        supports_ollama_registry=False,
        supports_vision=True,
        supports_audio=False,
        supports_tool_calling=True,
        supports_mtp=True,
        requires_gpu=True,
        quick_defaults={"model": "meta-llama/Meta-Llama-3-8B-Instruct", "tensor_parallel": 1},
    )

    def default_config(
        self, model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct", mode: str = "quick"
    ) -> FrameworkConfig:
        return FrameworkConfig(
            framework=Framework.SGLANG,
            mode=ConfigMode(mode),
            model=ModelConfig(
                name=model_name or "meta-llama/Meta-Llama-3-8B-Instruct",
                context_length=8192,
                tensor_parallel=1,
            ),
            capabilities=Capabilities(text=True),
            port=30000,
            bind_host="127.0.0.1",
            image_tag=self.meta.default_image,
            shm_size="16gb",
            gpu_count=1,
        )

    def validate(self, config: FrameworkConfig, host: HostInfo | None = None) -> list[ValidationIssue]:
        issues = validate_model_name(Framework.SGLANG, config.model.name)
        issues.extend(check_capabilities(self.meta, config.capabilities))

        if ".gguf" in config.model.name.lower():
            issues.append(
                ValidationIssue(
                    level="error",
                    message="SGLang does not support GGUF. Use Hugging Face safetensors repo.",
                    field="model.name",
                )
            )

        if host:
            if host.gpu_vendor == GPUVendor.NONE:
                issues.append(
                    ValidationIssue(
                        level="error",
                        message="SGLang requires a GPU.",
                    )
                )
            elif host.gpu_vendor == GPUVendor.APPLE:
                issues.append(
                    ValidationIssue(
                        level="error",
                        message="SGLang is not supported on Apple Silicon.",
                    )
                )
        return issues
