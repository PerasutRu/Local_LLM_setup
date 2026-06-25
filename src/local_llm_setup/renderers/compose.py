"""Docker Compose renderer."""

from __future__ import annotations

from typing import Any

import yaml

from local_llm_setup.frameworks import get_plugin
from local_llm_setup.models.config import Framework, FrameworkConfig, HostInfo, GPUVendor, SetupConfig


def _needs_gpu(fc: FrameworkConfig, host: HostInfo | None) -> bool:
    plugin = get_plugin(fc.framework)
    if not plugin.meta.requires_gpu:
        return host is not None and host.gpu_vendor == GPUVendor.NVIDIA
    return host is not None and host.gpu_vendor in (GPUVendor.NVIDIA, GPUVendor.AMD)


def _service_name(fc: FrameworkConfig) -> str:
    return fc.framework.value.replace(".", "")


def _build_command(fc: FrameworkConfig) -> list[str] | str | None:
    m = fc.model
    caps = fc.capabilities

    if fc.framework == Framework.OLLAMA:
        return None  # uses default entrypoint; model pulled separately

    if fc.framework == Framework.VLLM:
        cmd = [
            "--model", m.name,
            "--host", "0.0.0.0",
            "--port", str(fc.port),
            "--max-model-len", str(m.context_length),
        ]
        if m.tensor_parallel > 1:
            cmd.extend(["--tensor-parallel-size", str(m.tensor_parallel)])
        if caps.tool_calling:
            cmd.append("--enable-auto-tool-choice")
        if caps.vision:
            cmd.append("--enable-multimodal")
        if caps.mtp and caps.mtp_drafter_model:
            cmd.extend(["--speculative-model", caps.mtp_drafter_model])
        cmd.extend(fc.extra_args)
        return cmd

    if fc.framework == Framework.LLAMACPP:
        cmd = [
            "--model", m.name,
            "--host", "0.0.0.0",
            "--port", str(fc.port),
            "--ctx-size", str(m.context_length),
        ]
        if caps.tool_calling:
            cmd.append("--jinja")
        cmd.extend(fc.extra_args)
        return cmd

    if fc.framework == Framework.SGLANG:
        cmd = [
            "python3", "-m", "sglang.launch_server",
            "--model-path", m.name,
            "--host", "0.0.0.0",
            "--port", str(fc.port),
            "--context-length", str(m.context_length),
            "--tp", str(m.tensor_parallel),
        ]
        if caps.tool_calling:
            cmd.append("--tool-call-parser")
        if caps.mtp and caps.mtp_drafter_model:
            cmd.extend(["--speculative-draft-model-path", caps.mtp_drafter_model])
        cmd.extend(fc.extra_args)
        return cmd

    return fc.extra_args or None


def _build_service(fc: FrameworkConfig, config: SetupConfig) -> dict[str, Any]:
    host = config.host
    plugin = get_plugin(fc.framework)
    image = plugin.image_for_host(host, fc.image_tag)
    name = _service_name(fc)

    service: dict[str, Any] = {
        "image": image,
        "container_name": f"local-llm-{name}",
        "restart": "unless-stopped",
        "ports": [f"{fc.bind_host}:{fc.port}:{fc.port}"],
        "shm_size": fc.shm_size,
        "healthcheck": {
            "test": ["CMD-SHELL", f"curl -sf http://127.0.0.1:{fc.port}/health || curl -sf http://127.0.0.1:{fc.port}/ || exit 1"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 5,
            "start_period": "120s",
        },
    }

    env: dict[str, str] = dict(fc.extra_env)
    if config.hf_token and fc.framework in (Framework.VLLM, Framework.SGLANG):
        env[fc.model.hf_token_env] = "${HF_TOKEN}"

    if fc.framework == Framework.OLLAMA:
        service["volumes"] = ["ollama_data:/root/.ollama"]
        service["healthcheck"]["test"] = ["CMD-SHELL", "curl -sf http://127.0.0.1:11434/ || exit 1"]
    elif fc.framework == Framework.LLAMACPP:
        service["volumes"] = ["./models:/models:ro"]
        service["command"] = _build_command(fc)

    cmd = _build_command(fc)
    if cmd and fc.framework != Framework.LLAMACPP:
        service["command"] = cmd

    if env:
        service["environment"] = env

    if _needs_gpu(fc, host):
        service["deploy"] = {
            "resources": {
                "reservations": {
                    "devices": [
                        {
                            "driver": "nvidia" if host and host.gpu_vendor == GPUVendor.NVIDIA else "nvidia",
                            "count": fc.gpu_count,
                            "capabilities": ["gpu"],
                        }
                    ]
                }
            }
        }

    return service


def render_compose(config: SetupConfig) -> str:
    services: dict[str, Any] = {}
    volumes: dict[str, Any] = {}

    for fc in config.frameworks:
        services[_service_name(fc)] = _build_service(fc, config)

    if config.nginx.enabled:
        services["nginx"] = {
            "image": "nginx:1.27-alpine",
            "container_name": "local-llm-nginx",
            "restart": "unless-stopped",
            "ports": [f"{config.nginx.bind_host}:{config.nginx.listen_port}:80"],
            "volumes": [
                "./nginx.conf:/etc/nginx/nginx.conf:ro",
            ],
            "depends_on": [_service_name(config.frameworks[0])],
        }
        if config.nginx.api_key_auth:
            services["nginx"]["volumes"].append("./api_keys.map:/etc/nginx/api_keys.map:ro")

    if any(fc.framework == Framework.OLLAMA for fc in config.frameworks):
        volumes["ollama_data"] = {}

    compose: dict[str, Any] = {
        "services": services,
    }
    if volumes:
        compose["volumes"] = volumes

    return yaml.dump(compose, default_flow_style=False, sort_keys=False, allow_unicode=True)


def render_env(config: SetupConfig) -> str:
    lines = ["# Generated by local-llm-setup", ""]
    if config.hf_token:
        lines.append(f"HF_TOKEN={config.hf_token}")
    for fc in config.frameworks:
        lines.append(f"# {fc.framework.value} port={fc.port}")
    return "\n".join(lines) + "\n"


def render_run_commands(config: SetupConfig) -> list[str]:
    out_dir = config.output_dir.resolve()
    cmds = [
        f"cd {out_dir}",
        "docker compose pull",
        "docker compose up -d",
    ]
    for fc in config.frameworks:
        if fc.framework == Framework.OLLAMA:
            cmds.append(f"docker compose exec ollama ollama pull {fc.model.name}")
    if config.nginx.enabled:
        cmds.append(f"curl http://{config.nginx.server_name}:{config.nginx.listen_port}/health")
    else:
        fc = config.frameworks[0]
        cmds.append(f"curl http://{fc.bind_host}:{fc.port}/")
    return cmds
