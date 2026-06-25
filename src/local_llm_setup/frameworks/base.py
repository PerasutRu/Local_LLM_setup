"""Framework plugins: defaults, constraints, validation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from local_llm_setup.models.config import (
    Capabilities,
    Framework,
    FrameworkConfig,
    HostInfo,
    ValidationIssue,
)


@dataclass
class FrameworkMeta:
    framework: Framework
    display_name: str
    description: str
    default_port: int
    default_image: str
    supports_gguf: bool
    supports_hf: bool
    supports_ollama_registry: bool
    supports_vision: bool
    supports_audio: bool
    supports_tool_calling: bool
    supports_mtp: bool
    requires_gpu: bool = False
    quick_defaults: dict = field(default_factory=dict)


class FrameworkPlugin(ABC):
    meta: FrameworkMeta

    @abstractmethod
    def default_config(self, model_name: str = "", mode: str = "quick") -> FrameworkConfig:
        ...

    @abstractmethod
    def validate(
        self, config: FrameworkConfig, host: HostInfo | None = None
    ) -> list[ValidationIssue]:
        ...

    def image_for_host(self, host: HostInfo | None, tag: str | None = None) -> str:
        return tag or self.meta.default_image


def check_capabilities(meta: FrameworkMeta, caps: Capabilities) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if caps.vision and not meta.supports_vision:
        issues.append(
            ValidationIssue(
                level="error",
                message=f"{meta.display_name} does not support vision/image input.",
                field="capabilities.vision",
            )
        )
    if caps.audio and not meta.supports_audio:
        issues.append(
            ValidationIssue(
                level="error",
                message=f"{meta.display_name} does not support audio.",
                field="capabilities.audio",
            )
        )
    if caps.tool_calling and not meta.supports_tool_calling:
        issues.append(
            ValidationIssue(
                level="warn",
                message=f"{meta.display_name} has limited tool-calling support; verify model compatibility.",
                field="capabilities.tool_calling",
            )
        )
    if caps.mtp and not meta.supports_mtp:
        issues.append(
            ValidationIssue(
                level="error",
                message=f"{meta.display_name} does not support speculative decoding / MTP.",
                field="capabilities.mtp",
            )
        )
    if caps.mtp and not caps.mtp_drafter_model:
        issues.append(
            ValidationIssue(
                level="error",
                message="MTP enabled but drafter model name is missing.",
                field="capabilities.mtp_drafter_model",
            )
        )
    return issues
