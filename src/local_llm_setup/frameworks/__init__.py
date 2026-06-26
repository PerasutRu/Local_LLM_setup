"""Framework registry."""

from __future__ import annotations

from local_llm_setup.frameworks.base import FrameworkPlugin
from local_llm_setup.frameworks.llamacpp import LlamaCppPlugin
from local_llm_setup.frameworks.ollama import OllamaPlugin
from local_llm_setup.frameworks.sglang import SglangPlugin
from local_llm_setup.frameworks.vllm import VllmPlugin
from local_llm_setup.models.config import Framework, FrameworkConfig, HostInfo, ValidationIssue

_PLUGINS: dict[Framework, FrameworkPlugin] = {
    Framework.OLLAMA: OllamaPlugin(),
    Framework.VLLM: VllmPlugin(),
    Framework.LLAMACPP: LlamaCppPlugin(),
    Framework.SGLANG: SglangPlugin(),
}


def get_plugin(framework: Framework) -> FrameworkPlugin:
    return _PLUGINS[framework]


def list_frameworks() -> list[FrameworkPlugin]:
    return list(_PLUGINS.values())


def default_docker_image(framework: Framework, host: HostInfo | None = None) -> str:
    """Return the provider image used when image_tag is not overridden."""
    return get_plugin(framework).image_for_host(host, None)


def resolve_docker_image(framework: Framework, image_tag: str | None, host: HostInfo | None = None) -> str:
    """Resolve the Docker image name for compose rendering."""
    return get_plugin(framework).image_for_host(host, image_tag)


def validate_setup(framework_configs: list[FrameworkConfig], host: HostInfo | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ports: dict[int, str] = {}
    for fc in framework_configs:
        plugin = get_plugin(fc.framework)
        issues.extend(plugin.validate(fc, host))
        if fc.port in ports:
            issues.append(
                ValidationIssue(
                    level="error",
                    message=f"Port {fc.port} used by both {ports[fc.port]} and {fc.framework.value}.",
                    field="port",
                )
            )
        ports[fc.port] = fc.framework.value
    return issues
