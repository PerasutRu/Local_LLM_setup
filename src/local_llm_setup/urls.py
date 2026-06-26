"""Build access URLs after deploy."""

from __future__ import annotations

import json
import shlex
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from ipaddress import ip_address
from pathlib import Path

from local_llm_setup.markup import DIM, END, style_heading, style_url
from local_llm_setup.models.config import Framework, SetupConfig

_PUBLIC_IP_SERVICES = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
)


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
    service_urls: list[tuple[str, str]] = field(default_factory=list)
    uses_public_ip: bool = False
    private_lan_url: str | None = None


def get_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1.0)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def _is_public_ipv4(host: str) -> bool:
    try:
        addr = ip_address(host)
    except ValueError:
        return False
    return addr.version == 4 and addr.is_global


def get_public_ip(*, timeout: float = 3.0) -> str | None:
    """Best-effort public IPv4 via outbound HTTPS (needs internet)."""
    for service in _PUBLIC_IP_SERVICES:
        try:
            with urllib.request.urlopen(service, timeout=timeout) as resp:
                host = resp.read().decode().strip()
        except (OSError, urllib.error.URLError, TimeoutError):
            continue
        if _is_public_ipv4(host):
            return host
    return None


def _external_hosts() -> tuple[str | None, str | None, bool]:
    """Return (preferred_host, private_lan_ip, uses_public_ip)."""
    lan_ip = get_lan_ip()
    public_ip = get_public_ip()
    if public_ip:
        return public_ip, lan_ip, True
    return lan_ip, lan_ip, False


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


def _read_api_key_from_map(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith('"'):
                end = stripped.find('"', 1)
                if end > 1:
                    return stripped[1:end]
    except OSError:
        return None
    return None


def resolve_api_key(config: SetupConfig, output_dir: Path | str | None = None) -> str | None:
    """Return the deployed API key when nginx auth is enabled."""
    if not config.nginx.enabled or not config.nginx.api_key_auth:
        return None

    out = Path(output_dir or config.output_dir)
    map_path = out / "api_keys.map"
    if map_path.is_file():
        key = _read_api_key_from_map(map_path)
        if key:
            return key

    if config.nginx.api_keys:
        return config.nginx.api_keys[0].key
    return None


def _curl_command(
    url: str,
    *,
    api_key: str | None = None,
    data: str | None = None,
    auth_style: str = "x-api-key",
) -> str:
    parts = ["curl", "-sSf"]
    if api_key:
        if auth_style == "bearer":
            parts.extend(["-H", f"Authorization: Bearer {api_key}"])
        else:
            parts.extend(["-H", f"X-API-Key: {api_key}"])
    if data is not None:
        parts.extend(["-d", data])
    parts.append(url)
    return shlex.join(parts)


def build_curl_test_commands(
    config: SetupConfig,
    *,
    base: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    output_dir: Path | str | None = None,
) -> list[str]:
    """Build copy-paste curl commands for health, models, and chat."""
    fc = config.frameworks[0]
    model = fc.model.name or "tinyllama:1.1b"
    base_url = (base or f"http://{host}:{port}").rstrip("/")
    api_key = resolve_api_key(config, output_dir)
    cmds: list[str] = []

    if config.nginx.enabled:
        cmds.append(_curl_command(f"{base_url}/health"))

    if fc.framework == Framework.OLLAMA:
        cmds.append(_curl_command(f"{base_url}/api/tags", api_key=api_key))
    else:
        cmds.append(_curl_command(f"{base_url}/", api_key=api_key))

    if fc.framework in (Framework.OLLAMA, Framework.VLLM, Framework.SGLANG):
        cmds.append(_curl_command(f"{base_url}/v1/models", api_key=api_key, auth_style="bearer"))

    if fc.framework == Framework.OLLAMA:
        payload = _chat_payload(model, ollama=True)
        cmds.append(_curl_command(f"{base_url}/api/chat", api_key=api_key, data=payload))

    if fc.framework in (Framework.OLLAMA, Framework.VLLM, Framework.SGLANG, Framework.LLAMACPP):
        payload = _chat_payload(model)
        cmds.append(
            _curl_command(
                f"{base_url}/v1/chat/completions",
                api_key=api_key,
                data=payload,
                auth_style="bearer",
            )
        )

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
        external_host, lan_ip, uses_public_ip = _external_hosts()
        if external_host:
            updates["test_commands"] = build_curl_test_commands(
                config,
                host=external_host,
                port=ngx.listen_port,
                output_dir=config.output_dir,
            )

    if tunnel_url:
        base = tunnel_url.rstrip("/")
        updates["tunnel_url"] = tunnel_url
        updates["tunnel_openai_base_url"] = f"{base}/v1"
        updates["tunnel_test_commands"] = build_curl_test_commands(
            config, base=base, output_dir=config.output_dir
        )
        updates["primary_url"] = tunnel_url

    if not updates:
        return urls
    return AccessUrls(**{**urls.__dict__, **updates})


def build_access_urls(config: SetupConfig) -> AccessUrls:
    fc = config.frameworks[0]
    external_host, lan_ip, uses_public_ip = _external_hosts()
    ngx = config.nginx

    if ngx.enabled:
        local_url = _url("127.0.0.1", ngx.listen_port)
        external_urls = [_url(external_host, ngx.listen_port)] if external_host else []
        private_lan_url = (
            _url(lan_ip, ngx.listen_port)
            if lan_ip and uses_public_ip and lan_ip != external_host
            else None
        )
        primary = external_urls[0] if external_urls else local_url
        health = _url("127.0.0.1", ngx.listen_port, "/health")
        base = primary.rstrip("/")
        ollama_base = base if fc.framework == Framework.OLLAMA else None
        openai_base = f"{base}/v1" if fc.framework == Framework.OLLAMA else base
        test_host = external_host or "127.0.0.1"
        test_port = ngx.listen_port
        service_urls = [
            (item.framework.value, _url("127.0.0.1", ngx.listen_port, f"/{item.framework.value}/"))
            if len(config.frameworks) > 1
            else (item.framework.value, _url("127.0.0.1", ngx.listen_port))
            for item in config.frameworks
        ]
        return AccessUrls(
            primary_url=primary,
            local_url=local_url,
            lan_urls=external_urls,
            direct_local_url=None,
            direct_lan_urls=[],
            health_url=health,
            ollama_base_url=ollama_base,
            openai_base_url=openai_base,
            api_hint=_api_hint(fc.framework),
            external=True,
            test_commands=build_curl_test_commands(
                config, host=test_host, port=test_port, output_dir=config.output_dir
            ),
            service_urls=service_urls,
            uses_public_ip=uses_public_ip,
            private_lan_url=private_lan_url,
        )

    local_url = _url("127.0.0.1", fc.port)
    external = fc.bind_host == "0.0.0.0"
    external_urls = [_url(external_host, fc.port)] if external_host and external else []
    private_lan_url = (
        _url(lan_ip, fc.port)
        if lan_ip and uses_public_ip and external and lan_ip != external_host
        else None
    )
    primary = external_urls[0] if external_urls else local_url
    base = primary.rstrip("/")
    ollama_base = base if fc.framework == Framework.OLLAMA else None
    openai_base = f"{base}/v1" if fc.framework in (Framework.OLLAMA, Framework.VLLM, Framework.SGLANG) else base
    test_host = external_host if external and external_host else "127.0.0.1"
    service_urls = [
        (item.framework.value, _url("127.0.0.1", item.port))
        for item in config.frameworks
    ]
    return AccessUrls(
        primary_url=primary,
        local_url=local_url,
        lan_urls=external_urls,
        direct_local_url=None,
        direct_lan_urls=[],
        health_url=None,
        ollama_base_url=ollama_base,
        openai_base_url=openai_base,
        api_hint=_api_hint(fc.framework),
        external=external,
        test_commands=build_curl_test_commands(
            config, host=test_host, port=fc.port, output_dir=config.output_dir
        ),
        service_urls=service_urls,
        uses_public_ip=uses_public_ip and external,
        private_lan_url=private_lan_url,
    )


def format_access_lines(urls: AccessUrls, *, markup: bool = True) -> list[str]:
    lines = ["", style_heading("Access URLs", markup=markup)]
    lines.append(f"  local:   {style_url(urls.local_url, markup=markup)}")
    if urls.lan_urls:
        network_label = "public IP" if urls.uses_public_ip else "LAN"
        for external in urls.lan_urls:
            lines.append(f"  {network_label}:  {style_url(external, markup=markup)}")
    elif urls.external:
        lines.append(f"  {DIM}public IP: unavailable (could not detect IP){END}")
    elif not urls.external:
        lines.append(f"  {DIM}LAN: not exposed (bind 127.0.0.1 only){END}")

    if urls.private_lan_url:
        lines.append(
            f"  LAN:     {style_url(urls.private_lan_url, markup=markup)}  {DIM}(WiFi เดียวกัน){END}"
        )

    if urls.tunnel_url:
        lines.append(
            f"  {style_heading('public', markup=markup)}:  "
            f"{style_url(urls.tunnel_url, markup=markup)}  {DIM}(เข้าจากอินเทอร์เน็ต นอก LAN){END}"
        )
        if urls.tunnel_openai_base_url:
            lines.append(f"  public openai: {style_url(urls.tunnel_openai_base_url, markup=markup)}")

    if urls.health_url:
        lines.append(f"  health:  {style_url(urls.health_url, markup=markup)}")

    if urls.openai_base_url:
        lines.append(
            f"  openai:  {style_url(urls.openai_base_url, markup=markup)}  "
            f"{DIM}(OpenAI client — api_key = Bearer token · ไม่ต้องต่อ /models){END}"
        )
    if urls.ollama_base_url:
        lines.append(
            f"  ollama:  {style_url(urls.ollama_base_url, markup=markup)}  "
            f"{DIM}(base URL สำหรับ Ollama API){END}"
        )

    if urls.direct_local_url and urls.lan_urls:
        lines.append(
            f"  {DIM}direct (bypass nginx): {style_url(urls.direct_local_url, markup=markup)}{END}"
        )

    if len(urls.service_urls) > 1:
        lines.append(f"  {style_heading('services', markup=markup)}:")
        for name, url in urls.service_urls:
            lines.append(f"    {name}: {style_url(url, markup=markup)}")

    lines.append(f"  {DIM}{urls.api_hint}{END}")
    if urls.test_commands:
        if urls.uses_public_ip:
            label = "test curl (public IP):"
        elif urls.lan_urls:
            label = "test curl (LAN IP):"
        else:
            label = "test curl:"
        lines.append(f"  {DIM}{label}{END}")
        for cmd in urls.test_commands:
            lines.append(f"    {DIM}{cmd}{END}")
    if urls.tunnel_test_commands:
        lines.append(f"  {DIM}test curl (public tunnel):{END}")
        for cmd in urls.tunnel_test_commands:
            lines.append(f"    {DIM}{cmd}{END}")
    if urls.external and urls.lan_urls:
        if urls.uses_public_ip:
            lines.append(
                f"  {DIM}public IP: ต้องเปิด firewall ให้ port นี้ · "
                f"ถ้า server อยู่หลัง router ต้องตั้ง port forward · "
                f"หรือใช้ Cloudflare tunnel URL ด้านบน{END}"
            )
        else:
            lines.append(
                f"  {DIM}LAN: same WiFi only · ถ้าเข้าไม่ได้ เปิด firewall ให้ Docker "
                f"· ใช้ Cloudflare tunnel URL สำหรับนอก LAN{END}"
            )
    return lines


def render_access_md(config: SetupConfig, urls: AccessUrls | None = None) -> str:
    urls = urls or build_access_urls(config)
    fc = config.frameworks[0]
    lines = ["# Access URLs", ""]
    lines.append(f"- **Local:** {urls.local_url}")
    for external in urls.lan_urls:
        if urls.uses_public_ip:
            lines.append(f"- **Public IP:** {external}")
        else:
            lines.append(f"- **LAN (same WiFi):** {external}")
    if urls.private_lan_url:
        lines.append(f"- **LAN (same WiFi):** {urls.private_lan_url}")
    if urls.tunnel_url:
        lines.append(f"- **Public (outside LAN):** {urls.tunnel_url}")
        lines.append(f"- **Public OpenAI base URL:** `{urls.tunnel_openai_base_url}`")
    if urls.health_url:
        lines.append(f"- **Health:** {urls.health_url}")
    if urls.openai_base_url:
        lines.append(f"- **OpenAI client base URL:** `{urls.openai_base_url}`")
    if urls.ollama_base_url:
        lines.append(f"- **Ollama base URL:** `{urls.ollama_base_url}`")

    if len(urls.service_urls) > 1:
        lines.extend(["", "## Services", ""])
        for name, url in urls.service_urls:
            lines.append(f"- **{name}:** {url}")

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
        if urls.uses_public_ip:
            label = "public IP"
        elif urls.lan_urls:
            label = "LAN IP"
        else:
            label = "host"
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
        if urls.uses_public_ip:
            lines.append(
                "Use the **Public IP** URL when the host port is reachable from the internet "
                "(firewall open, port forwarded if behind NAT). "
                "Otherwise use the **Cloudflare** URL."
            )
        else:
            lines.append("Devices on the same network can access the **LAN** URL.")
    elif not urls.external:
        lines.append("Service is bound to localhost only. Enable nginx or public bind for LAN access.")
    return "\n".join(lines) + "\n"
