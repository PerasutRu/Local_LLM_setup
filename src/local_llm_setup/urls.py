"""Build access URLs after deploy."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field

from local_llm_setup.models.config import Framework, SetupConfig


@dataclass
class AccessUrls:
    primary_url: str
    local_url: str
    lan_urls: list[str]
    direct_local_url: str | None
    direct_lan_urls: list[str]
    health_url: str | None
    ollama_base_url: str | None
    openai_base_url: str | None
    api_hint: str
    external: bool
    test_commands: list[str]
    tunnel_url: str | None = None
    tunnel_openai_base_url: str | None = None
    tunnel_test_commands: list[str] = field(default_factory=list)


def get_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1.0)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def _api_hint(framework: Framework) -> str:
    hints = {
        Framework.OLLAMA: "Ollama API — POST /api/chat · GET /api/tags",
        Framework.VLLM: "OpenAI-compatible — POST /v1/chat/completions",
        Framework.LLAMACPP: "llama.cpp server — POST /completion or /v1/chat/completions",
        Framework.SGLANG: "SGLang — POST /v1/chat/completions",
    }
    return hints.get(framework, "LLM HTTP API")


def _url(host: str, port: int, path: str = "/") -> str:
    return f"http://{host}:{port}{path}"


def _chat_payload(model: str, *, ollama: bool = False) -> str:
    body: dict = {"model": model, "messages": [{"role": "user", "content": "สวัสดี"}]}
    if ollama:
        body["stream"] = False
    return json.dumps(body, ensure_ascii=False)


def build_curl_test_commands(
    config: SetupConfig,
    *,
    base: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> list[str]:
    """Build copy-paste curl commands for health, models, and chat."""
    fc = config.frameworks[0]
    model = fc.model.name or "tinyllama:1.1b"
    base_url = (base or f"http://{host}:{port}").rstrip("/")
    cmds: list[str] = []

    if config.nginx.enabled:
        cmds.append(f"curl -sSf {base_url}/health")

    if fc.framework == Framework.OLLAMA:
        cmds.append(f"curl -sSf {base_url}/api/tags")
    else:
        cmds.append(f"curl -sSf {base_url}/")

    if fc.framework in (Framework.OLLAMA, Framework.VLLM, Framework.SGLANG):
        cmds.append(f"curl -sSf {base_url}/v1/models")

    if fc.framework == Framework.OLLAMA:
        payload = _chat_payload(model, ollama=True)
        cmds.append(f"curl -sSf {base_url}/api/chat -d '{payload}'")

    if fc.framework in (Framework.OLLAMA, Framework.VLLM, Framework.SGLANG, Framework.LLAMACPP):
        payload = _chat_payload(model)
        cmds.append(f"curl -sSf {base_url}/v1/chat/completions -d '{payload}'")

    return cmds


def enrich_access_urls(
    config: SetupConfig,
    urls: AccessUrls,
    *,
    tunnel_url: str | None = None,
) -> AccessUrls:
    """Add LAN and public tunnel URLs after deploy."""
    ngx = config.nginx
    updates: dict = {}

    if ngx.enabled:
        lan_ip = get_lan_ip()
        if lan_ip:
            updates["test_commands"] = build_curl_test_commands(
                config, host=lan_ip, port=ngx.listen_port
            )

    if tunnel_url:
        base = tunnel_url.rstrip("/")
        updates["tunnel_url"] = tunnel_url
        updates["tunnel_openai_base_url"] = f"{base}/v1"
        updates["tunnel_test_commands"] = build_curl_test_commands(config, base=base)
        updates["primary_url"] = tunnel_url

    if not updates:
        return urls
    return AccessUrls(**{**urls.__dict__, **updates})


def build_access_urls(config: SetupConfig) -> AccessUrls:
    fc = config.frameworks[0]
    lan_ip = get_lan_ip()
    ngx = config.nginx

    if ngx.enabled:
        local_url = _url("127.0.0.1", ngx.listen_port)
        lan_urls = [_url(lan_ip, ngx.listen_port)] if lan_ip else []
        primary = lan_urls[0] if lan_urls else local_url
        health = _url("127.0.0.1", ngx.listen_port, "/health")
        direct_local = _url("127.0.0.1", fc.port)
        direct_lan = [_url(lan_ip, fc.port)] if lan_ip and fc.bind_host == "0.0.0.0" else []
        base = primary.rstrip("/")
        ollama_base = base if fc.framework == Framework.OLLAMA else None
        openai_base = f"{base}/v1" if fc.framework == Framework.OLLAMA else base
        test_host = lan_ip or "127.0.0.1"
        test_port = ngx.listen_port
        return AccessUrls(
            primary_url=primary,
            local_url=local_url,
            lan_urls=lan_urls,
            direct_local_url=direct_local,
            direct_lan_urls=direct_lan,
            health_url=health,
            ollama_base_url=ollama_base,
            openai_base_url=openai_base,
            api_hint=_api_hint(fc.framework),
            external=True,
            test_commands=build_curl_test_commands(config, host=test_host, port=test_port),
        )

    local_url = _url("127.0.0.1", fc.port)
    external = fc.bind_host == "0.0.0.0"
    lan_urls = [_url(lan_ip, fc.port)] if lan_ip and external else []
    primary = lan_urls[0] if lan_urls else local_url
    base = primary.rstrip("/")
    ollama_base = base if fc.framework == Framework.OLLAMA else None
    openai_base = f"{base}/v1" if fc.framework in (Framework.OLLAMA, Framework.VLLM, Framework.SGLANG) else base
    test_host = "127.0.0.1"
    return AccessUrls(
        primary_url=primary,
        local_url=local_url,
        lan_urls=lan_urls,
        direct_local_url=None,
        direct_lan_urls=[],
        health_url=None,
        ollama_base_url=ollama_base,
        openai_base_url=openai_base,
        api_hint=_api_hint(fc.framework),
        external=external,
        test_commands=build_curl_test_commands(config, host=test_host, port=fc.port),
    )


def format_access_lines(urls: AccessUrls, *, markup: bool = True) -> list[str]:
    bold = "[bold #c9a227]" if markup else ""
    bold_end = "[/]" if markup else ""
    dim = "[dim]" if markup else ""
    dim_end = "[/]" if markup else ""

    lines = ["", f"{bold}Access URLs{bold_end}"]
    lines.append(f"  local:   {urls.local_url}")
    if urls.lan_urls:
        for lan in urls.lan_urls:
            lines.append(f"  LAN:     {lan}")
    elif urls.external:
        lines.append(f"  {dim}LAN: unavailable (could not detect IP){dim_end}")
    elif not urls.external:
        lines.append(f"  {dim}LAN: not exposed (bind 127.0.0.1 only){dim_end}")

    if urls.tunnel_url:
        lines.append(f"  {bold}public:{bold_end}  {urls.tunnel_url}  [dim](เข้าจากอินเทอร์เน็ต นอก LAN)[/dim]")
        if urls.tunnel_openai_base_url:
            lines.append(f"  public openai: {urls.tunnel_openai_base_url}")

    if urls.health_url:
        lines.append(f"  health:  {urls.health_url}")

    if urls.openai_base_url:
        lines.append(f"  openai:  {urls.openai_base_url}  [dim](ใส่ใน OpenAI client — ไม่ต้องต่อ /models)[/dim]")
    if urls.ollama_base_url:
        lines.append(f"  ollama:  {urls.ollama_base_url}  [dim](base URL สำหรับ Ollama API)[/dim]")

    if urls.direct_local_url and urls.lan_urls:
        lines.append(f"  {dim}direct (bypass nginx): {urls.direct_local_url}{dim_end}")

    lines.append(f"  {dim}{urls.api_hint}{dim_end}")
    if urls.test_commands:
        label = "test curl (LAN IP):" if urls.lan_urls else "test curl:"
        lines.append(f"  {dim}{label}{dim_end}")
        for cmd in urls.test_commands:
            lines.append(f"    {dim}{cmd}{dim_end}")
    if urls.tunnel_test_commands:
        lines.append(f"  {dim}test curl (public tunnel):{dim_end}")
        for cmd in urls.tunnel_test_commands:
            lines.append(f"    {dim}{cmd}{dim_end}")
    if urls.external and urls.lan_urls:
        lines.append(
            f"  {dim}LAN: same WiFi only · ถ้าเข้าไม่ได้ เปิด macOS Firewall ให้ Docker "
            f"· ใช้ public URL สำหรับนอก LAN{dim_end}"
        )
    return lines


def render_access_md(config: SetupConfig, urls: AccessUrls | None = None) -> str:
    urls = urls or build_access_urls(config)
    fc = config.frameworks[0]
    lines = ["# Access URLs", ""]
    lines.append(f"- **Local:** {urls.local_url}")
    for lan in urls.lan_urls:
        lines.append(f"- **LAN (same WiFi):** {lan}")
    if urls.tunnel_url:
        lines.append(f"- **Public (outside LAN):** {urls.tunnel_url}")
        lines.append(f"- **Public OpenAI base URL:** `{urls.tunnel_openai_base_url}`")
    if urls.health_url:
        lines.append(f"- **Health:** {urls.health_url}")
    if urls.openai_base_url:
        lines.append(f"- **OpenAI client base URL:** `{urls.openai_base_url}`")
    if urls.ollama_base_url:
        lines.append(f"- **Ollama base URL:** `{urls.ollama_base_url}`")

    lines.extend(["", "## API endpoints", "", "| Method | Path | คำอธิบาย |", "|--------|------|----------|"])
    if urls.health_url:
        lines.append("| `GET` | `/health` | ตรวจว่า nginx รันอยู่ |")
    if fc.framework == Framework.OLLAMA:
        lines.extend(
            [
                "| `GET` | `/api/tags` | รายการ model (Ollama native) |",
                "| `POST` | `/api/chat` | แชท (Ollama native) |",
            ]
        )
    lines.extend(
        [
            "| `GET` | `/v1/models` | รายการ model (OpenAI compatible) |",
            "| `POST` | `/v1/chat/completions` | แชท (OpenAI compatible) |",
        ]
    )

    if urls.test_commands:
        label = "LAN IP" if urls.lan_urls else "host"
        lines.extend(
            [
                "",
                f"## Test curl ({label})",
                "",
                "```bash",
                *urls.test_commands,
                "```",
            ]
        )
    if urls.tunnel_test_commands:
        lines.extend(
            [
                "",
                "## Test curl (public — outside LAN)",
                "",
                "```bash",
                *urls.tunnel_test_commands,
                "```",
            ]
        )

    lines.append("")
    if urls.tunnel_url:
        lines.append(
            "Use the **Public** URL from any internet connection. "
            "The LAN URL only works on the same local network."
        )
    elif urls.external and urls.lan_urls:
        lines.append("Devices on the same network can access the **LAN** URL.")
    elif not urls.external:
        lines.append("Service is bound to localhost only. Enable nginx or public bind for LAN access.")
    return "\n".join(lines) + "\n"
