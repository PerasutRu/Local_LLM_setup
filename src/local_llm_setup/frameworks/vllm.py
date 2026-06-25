"""vLLM framework plugin."""

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


class VllmPlugin(FrameworkPlugin):
    meta = FrameworkMeta(
        framework=Framework.VLLM,
        display_name="vLLM",
        description="High-throughput serving for Hugging Face models (no GGUF)",
        default_port=8000,
        default_image="vllm/vllm-openai:latest",
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
            framework=Framework.VLLM,
            mode=ConfigMode(mode),
            model=ModelConfig(
                name=model_name or "meta-llama/Meta-Llama-3-8B-Instruct",
                context_length=8192,
                tensor_parallel=1,
            ),
            capabilities=Capabilities(text=True),
            port=8000,
            bind_host="127.0.0.1",
            image_tag=self.meta.default_image,
            shm_size="16gb",
            gpu_count=1,
        )

    def validate(self, config: FrameworkConfig, host: HostInfo | None = None) -> list[ValidationIssue]:
        issues = validate_model_name(Framework.VLLM, config.model.name)
        issues.extend(check_capabilities(self.meta, config.capabilities))

        if ".gguf" in config.model.name.lower():
            issues.append(
                ValidationIssue(
                    level="error",
                    message="vLLM does not support GGUF format. Use Hugging Face safetensors repo.",
                    field="model.name",
                )
            )

        if host:
            if host.gpu_vendor == GPUVendor.NONE:
                issues.append(
                    ValidationIssue(
                        level="error",
                        message="vLLM requires a GPU (NVIDIA CUDA or AMD ROCm).",
                    )
                )
            elif host.gpu_vendor == GPUVendor.NVIDIA and not host.nvidia_container_toolkit:
                issues.append(
                    ValidationIssue(
                        level="warn",
                        message="NVIDIA Container Toolkit not detected — GPU passthrough in Docker may fail.",
                    )
                )
            elif host.gpu_vendor == GPUVendor.APPLE:
                issues.append(
                    ValidationIssue(
                        level="error",
                        message="vLLM is not supported on Apple Silicon.",
                    )
                )
        return issues

    def image_for_host(self, host: HostInfo | None, tag: str | None = None) -> str:
        if tag:
            return tag
        if host and host.gpu_vendor.value == "amd":
            return "rocm/vllm:latest"
        return self.meta.default_image
