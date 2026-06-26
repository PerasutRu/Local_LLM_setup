"""Docker Compose renderer."""

from __future__ import annotations

from typing import Any

import yaml

from local_llm_setup.frameworks import get_plugin
from local_llm_setup.models.config import (
    Framework,
    FrameworkConfig,
    HostInfo,
    GPUVendor,
    SetupConfig,
    VllmServeOptions,
)

COMPOSE_NETWORK = "local_llm"


def _needs_gpu(fc: FrameworkConfig, host: HostInfo | None) -> bool:
    plugin = get_plugin(fc.framework)
    if fc.gpu_device_ids and plugin.meta.requires_gpu:
        return True
    if not plugin.meta.requires_gpu:
        return host is not None and host.gpu_vendor == GPUVendor.NVIDIA
    if host is None:
        return True
    return host.gpu_vendor in (GPUVendor.NVIDIA, GPUVendor.AMD)


def _attach_network(service: dict[str, Any]) -> dict[str, Any]:
    service["networks"] = [COMPOSE_NETWORK]
    return service


def _framework_depends_on(config: SetupConfig) -> dict[str, dict[str, str]]:
    return {
        _service_name(fc): {"condition": "service_healthy"}
        for fc in config.frameworks
    }


def _service_name(fc: FrameworkConfig) -> str:
    return fc.framework.value.replace(".", "")


def _published_port(fc: FrameworkConfig) -> int:
    return fc.publish_port if fc.publish_port is not None else fc.port


def _build_vllm_serve_args(fc: FrameworkConfig) -> list[str]:
    m = fc.model
    caps = fc.capabilities
    v = fc.vllm or VllmServeOptions()

    args = [
        m.name,
        "--host", "0.0.0.0",
        "--port", str(fc.port),
        "--max-model-len", str(m.context_length),
    ]
    if m.tensor_parallel > 1:
        args.extend(["--tensor-parallel-size", str(m.tensor_parallel)])
    if m.quantization:
        args.extend(["--quantization", m.quantization])
    if v.gpu_memory_utilization is not None:
        args.extend(["--gpu-memory-utilization", str(v.gpu_memory_utilization)])
    if v.max_num_seqs is not None:
        args.extend(["--max-num-seqs", str(v.max_num_seqs)])
    if v.trust_remote_code:
        args.append("--trust-remote-code")
    if v.enable_prefix_caching:
        args.append("--enable-prefix-caching")
    if caps.tool_calling:
        args.append("--enable-auto-tool-choice")
    if v.tool_call_parser:
        args.extend(["--tool-call-parser", v.tool_call_parser])
    if v.reasoning_parser:
        args.extend(["--reasoning-parser", v.reasoning_parser])
    if v.kv_cache_dtype:
        args.extend(["--kv-cache-dtype", v.kv_cache_dtype])
    if v.limit_mm_per_prompt:
        args.extend(["--limit-mm-per-prompt", v.limit_mm_per_prompt])
    if caps.mtp and caps.mtp_drafter_model:
        args.extend(["--speculative-model", caps.mtp_drafter_model])
    args.extend(fc.extra_args)
    return args


def _vllm_serve_shell(fc: FrameworkConfig) -> str:
    args = _build_vllm_serve_args(fc)
    flag_line = " \\\n  ".join(args)
    bootstrap = ""
    v = fc.vllm or VllmServeOptions()
    if v.install_audio_extras or fc.capabilities.audio:
        bootstrap = (
            'if ! python3 -c "import librosa" >/dev/null 2>&1; then\n'
            '  uv pip install --system "vllm[audio]==$(python3 -c \'import vllm; print(vllm.__version__)\')"\n'
            "fi\n"
        )
    return f"{bootstrap}exec vllm serve \\\n  {flag_line}"


def _build_command(fc: FrameworkConfig) -> list[str] | str | None:
    m = fc.model
    caps = fc.capabilities

    if fc.framework == Framework.OLLAMA:
        return None  # uses default entrypoint; model pulled separately

    if fc.framework == Framework.VLLM:
        if fc.command_shell:
            return None
        v = fc.vllm or VllmServeOptions()
        if v.install_audio_extras or fc.capabilities.audio:
            return None
        return _build_vllm_serve_args(fc)

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
        if m.quantization:
            cmd.extend(["--quantization", m.quantization])
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
    expose_internal_only = config.nginx.enabled

    service: dict[str, Any] = {
        "image": image,
        "container_name": f"local-llm-{name}",
        "restart": "unless-stopped",
        "shm_size": fc.shm_size,
        "healthcheck": {
            "test": ["CMD-SHELL", f"curl -sf http://127.0.0.1:{fc.port}/health || curl -sf http://127.0.0.1:{fc.port}/ || exit 1"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 5,
            "start_period": "120s",
        },
    }
    if not expose_internal_only:
        host_port = _published_port(fc)
        service["ports"] = [f"{fc.bind_host}:{host_port}:{fc.port}"]

    env: dict[str, str] = dict(fc.extra_env)
    if config.hf_token and fc.framework in (Framework.VLLM, Framework.SGLANG):
        env[fc.model.hf_token_env] = "${HF_TOKEN}"

    if fc.framework == Framework.OLLAMA:
        service["volumes"] = ["ollama_data:/root/.ollama"]
        # Ollama defaults to 127.0.0.1; bind all interfaces so nginx/other containers can reach it.
        env.setdefault("OLLAMA_HOST", f"0.0.0.0:{fc.port}")
        service["healthcheck"]["test"] = [
            "CMD-SHELL",
            (
                f"curl -sf http://127.0.0.1:{fc.port}/api/tags >/dev/null 2>&1"
                f" || ollama list >/dev/null 2>&1 || exit 1"
            ),
        ]
    elif fc.framework == Framework.LLAMACPP:
        service["volumes"] = ["./models:/models:ro"]
        service["command"] = _build_command(fc)
    elif fc.framework == Framework.VLLM and fc.extra_volumes:
        service["volumes"] = list(fc.extra_volumes)

    if fc.ipc:
        service["ipc"] = fc.ipc

    cmd = _build_command(fc)
    if fc.framework == Framework.VLLM:
        if fc.command_shell:
            service["entrypoint"] = ["/bin/bash", "-lc"]
            service["command"] = [fc.command_shell]
        elif fc.capabilities.audio or (fc.vllm and fc.vllm.install_audio_extras):
            service["entrypoint"] = ["/bin/bash", "-lc"]
            service["command"] = [_vllm_serve_shell(fc)]
        elif cmd:
            service["entrypoint"] = ["vllm", "serve"]
            service["command"] = cmd
    elif cmd and fc.framework != Framework.LLAMACPP:
        service["command"] = cmd

    if env:
        service["environment"] = env

    if _needs_gpu(fc, host):
        device: dict[str, Any]
        if fc.gpu_device_ids:
            device = {
                "driver": "nvidia" if host and host.gpu_vendor == GPUVendor.NVIDIA else "nvidia",
                "device_ids": fc.gpu_device_ids,
                "capabilities": ["gpu"],
            }
            env.setdefault("NVIDIA_VISIBLE_DEVICES", ",".join(fc.gpu_device_ids))
        else:
            device = {
                "driver": "nvidia" if host and host.gpu_vendor == GPUVendor.NVIDIA else "nvidia",
                "count": fc.gpu_count,
                "capabilities": ["gpu"],
            }
        service["deploy"] = {
            "resources": {
                "reservations": {
                    "devices": [device],
                }
            }
        }

    return _attach_network(service)


def render_compose(config: SetupConfig) -> str:
    services: dict[str, Any] = {}
    volumes: dict[str, Any] = {}

    for fc in config.frameworks:
        services[_service_name(fc)] = _build_service(fc, config)

    if config.nginx.enabled:
        nginx_service: dict[str, Any] = {
            "image": "nginx:1.27-alpine",
            "container_name": "local-llm-nginx",
            "restart": "unless-stopped",
            "ports": [f"{config.nginx.bind_host}:{config.nginx.listen_port}:80"],
            "volumes": [
                "./nginx.conf:/etc/nginx/nginx.conf:ro",
            ],
            "depends_on": _framework_depends_on(config),
            "healthcheck": {
                "test": ["CMD-SHELL", "wget -q --spider http://127.0.0.1/health || exit 1"],
                "interval": "15s",
                "timeout": "5s",
                "retries": 5,
                "start_period": "10s",
            },
        }
        if config.nginx.api_key_auth:
            nginx_service["volumes"].append("./api_keys.map:/etc/nginx/api_keys.map:ro")
        services["nginx"] = _attach_network(nginx_service)

        if config.nginx.tunnel_enabled:
            services["cloudflared"] = _attach_network({
                "image": "cloudflare/cloudflared:latest",
                "container_name": "local-llm-tunnel",
                "restart": "unless-stopped",
                "command": f"tunnel --no-autoupdate --url http://nginx:80",
                "depends_on": {
                    "nginx": {"condition": "service_healthy"},
                },
            })

    if any(fc.framework == Framework.OLLAMA for fc in config.frameworks):
        volumes["ollama_data"] = {}

    compose: dict[str, Any] = {
        "services": services,
        "networks": {
            COMPOSE_NETWORK: {
                "driver": "bridge",
                "name": f"local-llm-setup-{COMPOSE_NETWORK}",
            },
        },
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
            cmds.append(
                "until docker compose exec -T ollama ollama list >/dev/null 2>&1; do sleep 3; done"
            )
            cmds.append(f"docker compose exec ollama ollama pull {fc.model.name}")
    if config.nginx.enabled:
        cmds.append(f"curl -sS http://{config.nginx.server_name}:{config.nginx.listen_port}/health")
    else:
        fc = config.frameworks[0]
        cmds.append(f"curl -sS http://{fc.bind_host}:{fc.port}/")
    cmds.append("docker compose down")
    return cmds
