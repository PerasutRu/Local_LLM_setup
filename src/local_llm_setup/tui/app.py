"""Textual TUI wizard — Hermes-inspired layout."""

from __future__ import annotations

import secrets
from datetime import datetime
from functools import partial
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Static

from local_llm_setup.tui.widgets import CopyableRichLog, LOG_FOOTER_HINT
from local_llm_setup.tui.styles import linkify_text, style_section
from textual.worker import Worker, WorkerState

from local_llm_setup.detect import detect_host
from local_llm_setup.frameworks import get_plugin, list_frameworks, validate_setup
from local_llm_setup.models.config import (
    ApiKeyEntry,
    Capabilities,
    ConfigMode,
    Framework,
    ModelConfig,
    NginxConfig,
    SetupConfig,
    VllmServeOptions,
)
from local_llm_setup.paths import OUTPUT_DIR
from local_llm_setup.profiles import save_profile
from local_llm_setup.renderers import generate, prepare_config
from local_llm_setup.runner import DeployResult, deploy, run_curl_tests, stop_stack
from local_llm_setup.urls import build_access_urls, format_access_lines
from local_llm_setup.tui.full_config import (
    format_extra_args,
    format_extra_env,
    format_volume_lines,
    model_fields,
    mount_fields,
    nginx_advanced_fields,
    nginx_basic_fields,
    parse_bool,
    parse_csv_ids,
    parse_extra_args,
    parse_extra_env,
    parse_volume_lines,
    read_field,
    runtime_fields,
    setup_fields,
)
from local_llm_setup.tui.commands import PROVIDER_CHOICES, SLASH_COMMANDS, format_help_lines, normalize_command
from local_llm_setup.tui.theme import APP_CSS, LOGO
from local_llm_setup.tui.widgets import ChoiceList


class WizardState:
    def __init__(self, output_dir: Path, initial: SetupConfig | None = None) -> None:
        self.output_dir = output_dir
        self.host = detect_host()
        self.framework: Framework | None = None
        self.mode: ConfigMode = ConfigMode.QUICK
        self.model_name: str = ""
        self.context_length: int = 8192
        self.tensor_parallel: int = 1
        self.quantization: str = ""
        self.hf_token_env: str = "HF_TOKEN"
        self.capabilities = Capabilities(text=True)
        self.nginx_enabled: bool = False
        self.nginx_port: int = 8080
        self.nginx_api_keys: bool = False
        self.nginx_server_name: str = "_"
        self.nginx_bind_host: str = "0.0.0.0"
        self.nginx_client_max_body_size: str = "50m"
        self.nginx_proxy_read_timeout: str = "600s"
        self.nginx_enable_cors: bool = True
        self.nginx_tunnel_enabled: bool = True
        self.bind_public: bool = False
        self.hf_token: str = ""
        self.auto_run: bool = True
        self.port_warnings: list[str] = []
        self.profile_name: str = "default"
        self.port: int | None = None
        self.bind_host_override: str = "127.0.0.1"
        self.image_tag: str = ""
        self.shm_size: str = ""
        self.gpu_count: int = 1
        self.extra_env_text: str = ""
        self.extra_args_text: str = ""
        self.ollama_parallel: str = "1"
        self.ollama_models: str = "/root/.ollama"
        self.ollama_host: str = "0.0.0.0:11434"
        self.llama_ngl: str = ""
        self.publish_port: int | None = None
        self.gpu_device_ids_text: str = ""
        self.ipc: str = ""
        self.extra_volumes_text: str = ""
        self.command_shell: str = ""
        self.vllm_gpu_mem: str = ""
        self.vllm_max_seqs: str = ""
        self.vllm_tool_parser: str = ""
        self.vllm_reasoning_parser: str = ""
        self.vllm_kv_cache: str = ""
        self.vllm_mm_limit: str = ""
        self.vllm_trust_remote: str = "false"
        self.vllm_prefix_cache: str = "false"

        if initial and initial.frameworks:
            fc = initial.frameworks[0]
            self.framework = fc.framework
            self.mode = fc.mode
            self.model_name = fc.model.name
            self.context_length = fc.model.context_length
            self.tensor_parallel = fc.model.tensor_parallel
            self.quantization = fc.model.quantization or ""
            self.hf_token_env = fc.model.hf_token_env
            self.capabilities = fc.capabilities
            self.port = fc.port
            self.bind_host_override = fc.bind_host
            self.image_tag = fc.image_tag or ""
            self.shm_size = fc.shm_size
            self.gpu_count = fc.gpu_count
            self.extra_env_text = format_extra_env(fc.extra_env)
            self.extra_args_text = format_extra_args(fc.extra_args)
            self.ollama_parallel = fc.extra_env.get("OLLAMA_NUM_PARALLEL", "1")
            self.ollama_models = fc.extra_env.get("OLLAMA_MODELS", "/root/.ollama")
            self.ollama_host = fc.extra_env.get("OLLAMA_HOST", "0.0.0.0:11434")
            self.publish_port = fc.publish_port
            self.gpu_device_ids_text = ",".join(fc.gpu_device_ids)
            self.ipc = fc.ipc or ""
            self.extra_volumes_text = format_volume_lines(fc.extra_volumes)
            self.command_shell = fc.command_shell or ""
            if fc.vllm:
                v = fc.vllm
                self.vllm_gpu_mem = str(v.gpu_memory_utilization) if v.gpu_memory_utilization is not None else ""
                self.vllm_max_seqs = str(v.max_num_seqs) if v.max_num_seqs is not None else ""
                self.vllm_tool_parser = v.tool_call_parser or ""
                self.vllm_reasoning_parser = v.reasoning_parser or ""
                self.vllm_kv_cache = v.kv_cache_dtype or ""
                self.vllm_mm_limit = v.limit_mm_per_prompt or ""
                self.vllm_trust_remote = "true" if v.trust_remote_code else "false"
                self.vllm_prefix_cache = "true" if v.enable_prefix_caching else "false"
            self.nginx_enabled = initial.nginx.enabled
            self.nginx_port = initial.nginx.listen_port
            self.nginx_api_keys = initial.nginx.api_key_auth
            self.nginx_server_name = initial.nginx.server_name
            self.nginx_bind_host = initial.nginx.bind_host
            self.nginx_client_max_body_size = initial.nginx.client_max_body_size
            self.nginx_proxy_read_timeout = initial.nginx.proxy_read_timeout
            self.nginx_enable_cors = initial.nginx.enable_cors
            self.nginx_tunnel_enabled = initial.nginx.tunnel_enabled
            self.hf_token = initial.hf_token or ""
            self.profile_name = initial.profile_name
            self.output_dir = initial.output_dir

    def to_config(self) -> SetupConfig:
        if not self.framework:
            raise ValueError("Framework not selected")
        config, self.port_warnings = prepare_config(self.build_config())
        self.nginx_port = config.nginx.listen_port
        if config.frameworks:
            self.port = config.frameworks[0].port
        return config

    def build_config(self) -> SetupConfig:
        if not self.framework:
            raise ValueError("Framework not selected")
        plugin = get_plugin(self.framework)
        fc = plugin.default_config(self.model_name, self.mode.value)
        fc.model = ModelConfig(
            name=self.model_name,
            context_length=self.context_length,
            tensor_parallel=self.tensor_parallel,
            quantization=self.quantization or None,
            hf_token_env=self.hf_token_env or "HF_TOKEN",
        )
        fc.capabilities = self.capabilities

        if self.mode == ConfigMode.FULL:
            if self.port is not None:
                fc.port = self.port
            fc.image_tag = self.image_tag or None
            if self.shm_size:
                fc.shm_size = self.shm_size
            fc.gpu_count = self.gpu_count
            extra_env = parse_extra_env(self.extra_env_text)
            if self.framework == Framework.OLLAMA:
                if self.ollama_parallel:
                    extra_env["OLLAMA_NUM_PARALLEL"] = self.ollama_parallel
                if self.ollama_models:
                    extra_env["OLLAMA_MODELS"] = self.ollama_models
                if self.ollama_host:
                    extra_env["OLLAMA_HOST"] = self.ollama_host
            fc.extra_env = extra_env
            extra_args = parse_extra_args(self.extra_args_text)
            if self.framework == Framework.LLAMACPP and self.llama_ngl:
                extra_args = ["--n-gpu-layers", self.llama_ngl, *extra_args]
            fc.extra_args = extra_args
            fc.publish_port = self.publish_port
            fc.gpu_device_ids = parse_csv_ids(self.gpu_device_ids_text)
            fc.ipc = self.ipc or None
            fc.extra_volumes = parse_volume_lines(self.extra_volumes_text)
            fc.command_shell = self.command_shell or None
            if self.framework == Framework.VLLM:
                fc.vllm = self._build_vllm_options()

        if self.nginx_enabled:
            fc.bind_host = "127.0.0.1"
        elif self.mode == ConfigMode.FULL:
            fc.bind_host = self.bind_host_override
        else:
            fc.bind_host = "0.0.0.0" if self.bind_public else "127.0.0.1"

        nginx = NginxConfig(
            enabled=self.nginx_enabled,
            listen_port=self.nginx_port,
            upstream_port=fc.port,
            api_key_auth=self.nginx_api_keys,
            bind_host=self.nginx_bind_host if self.mode == ConfigMode.FULL else (
                "0.0.0.0" if self.nginx_enabled else "127.0.0.1"
            ),
            server_name=self.nginx_server_name,
            client_max_body_size=self.nginx_client_max_body_size,
            proxy_read_timeout=self.nginx_proxy_read_timeout,
            enable_cors=self.nginx_enable_cors,
            tunnel_enabled=self.nginx_tunnel_enabled,
        )
        if self.nginx_api_keys:
            nginx.api_keys = [ApiKeyEntry(key=secrets.token_urlsafe(32), label="default")]

        return SetupConfig(
            profile_name=self.profile_name,
            output_dir=self.output_dir,
            host=self.host,
            frameworks=[fc],
            nginx=nginx,
            hf_token=self.hf_token or None,
        )

    def _build_vllm_options(self) -> VllmServeOptions:
        gpu_mem: float | None = None
        if self.vllm_gpu_mem:
            try:
                gpu_mem = float(self.vllm_gpu_mem)
            except ValueError:
                pass
        max_seqs: int | None = None
        if self.vllm_max_seqs:
            try:
                max_seqs = int(self.vllm_max_seqs)
            except ValueError:
                pass
        return VllmServeOptions(
            gpu_memory_utilization=gpu_mem,
            max_num_seqs=max_seqs,
            trust_remote_code=parse_bool(self.vllm_trust_remote),
            enable_prefix_caching=parse_bool(self.vllm_prefix_cache),
            tool_call_parser=self.vllm_tool_parser or None,
            reasoning_parser=self.vllm_reasoning_parser or None,
            kv_cache_dtype=self.vllm_kv_cache or None,
            limit_mm_per_prompt=self.vllm_mm_limit or None,
            install_audio_extras=self.capabilities.audio,
        )


STEP_TITLES = {
    "doctor": "Host Doctor",
    "framework": "Available Frameworks",
    "mode": "Configuration Mode",
    "model": "Model Setup",
    "runtime": "Runtime & Docker",
    "capabilities": "Capabilities",
    "nginx": "Nginx & API Keys",
    "summary": "Review & Generate",
    "done": "Complete",
}


class LocalLLMSetupApp(App):
    """Local LLM Setup TUI wizard."""

    CSS = APP_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "back", "Back"),
        Binding("up", "nav_up", "Up", show=False),
        Binding("down", "nav_down", "Down", show=False),
        Binding("k", "nav_up", "Up", show=False),
        Binding("j", "nav_down", "Down", show=False),
        Binding("space", "nav_toggle", "Select", show=False),
        Binding("tab", "next_choice_list", "Next", show=False),
        Binding("enter", "nav_submit", "Confirm", show=False),
        Binding("s", "stop_stack", "Stop", show=True),
        Binding("slash", "focus_command", "Command", show=False),
    ]

    def __init__(self, output_dir: Path = OUTPUT_DIR, initial_config: SetupConfig | None = None) -> None:
        super().__init__()
        self.state = WizardState(output_dir, initial_config)
        self._step_idx = 0
        self._active_choices: ChoiceList | None = None
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._deploy_log: CopyableRichLog | None = None
        self._deploy_succeeded = False
        self._remove_volumes_on_stop = False
        self._command_aliases = {
            sc.name: sc.name for sc in SLASH_COMMANDS
        }
        for sc in SLASH_COMMANDS:
            for alias in sc.aliases:
                self._command_aliases[alias] = sc.name

    def compose(self) -> ComposeResult:
        with Container(id="root"):
            with Horizontal(id="header"):
                yield Static(LOGO, id="logo")
                yield Static(id="meta")
            with Vertical(id="main"):
                yield Static(id="step-title")
                yield VerticalScroll(id="step-body")
                yield Container(id="choices-panel")
            with Vertical(id="footer-panel"):
                yield Static(id="welcome")
                yield Static(id="status-bar")
                yield Static(id="hint-bar")
                yield Input(
                    placeholder="/help · /providers · /delete-container · /test",
                    id="command-input",
                )

    def on_mount(self) -> None:
        self._update_header()
        self._show_step()

    @property
    def step(self) -> str:
        return self._wizard_steps()[self._step_idx]

    def _wizard_steps(self) -> list[str]:
        steps = ["doctor", "framework", "mode", "model"]
        if self.state.mode == ConfigMode.FULL:
            steps.append("runtime")
        steps.extend(["capabilities", "nginx", "summary", "done"])
        return steps

    def _progress_bar(self) -> str:
        steps = self._wizard_steps()
        total = len(steps)
        filled = self._step_idx + 1
        width = 10
        n = int(filled / total * width)
        return "█" * n + "░" * (width - n)

    def _update_header(self) -> None:
        host = self.state.host
        gpu = host.gpu_name or "no GPU"
        meta = self.query_one("#meta", Static)
        meta.update(
            f"[#c9a227]Local LLM Setup[/] · Docker deploy wizard\n"
            f"{Path.cwd()} · {host.os_type.value}/{host.arch}\n"
            f"Session: {self._session_id} · {gpu}"
        )

    def _update_footer(self, welcome: str, hint: str) -> None:
        step_name = STEP_TITLES.get(self.step, self.step)
        self.query_one("#welcome", Static).update(linkify_text(welcome))
        self.query_one("#status-bar", Static).update(
            f"⚡ [#c9a227]{step_name}[/] · step {self._step_idx + 1}/{len(self._wizard_steps())} "
            f"[{self._progress_bar()}]"
        )
        self.query_one("#hint-bar", Static).update(hint)

    def _set_step_title(self, title: str) -> None:
        self.query_one("#step-title", Static).update(style_section(title))

    def _clear_step(self) -> None:
        self.query_one("#step-body", VerticalScroll).remove_children()
        self.query_one("#choices-panel", Container).remove_children()
        self._active_choices = None

    def _mount_choices(self, choices: list[tuple[str, str]], *, multi: bool = False, id: str = "choice") -> ChoiceList:
        panel = self.query_one("#choices-panel", Container)
        cl = ChoiceList(choices, multi=multi, id=id)
        panel.mount(cl)
        self._active_choices = cl
        self.call_after_refresh(cl.focus)
        return cl

    def _section_label(self, text: str) -> Static:
        return Static(style_section(text), classes="section-label")

    def _skill_line(self, key: str, val: str) -> Static:
        return Static(f"[#c9a227]{key}:[/] {val}", classes="skill-line")

    def _next(self) -> None:
        if self._step_idx < len(self._wizard_steps()) - 1:
            self._step_idx += 1
            self._show_step()

    def _back(self) -> None:
        if self._step_idx > 0:
            self._step_idx -= 1
            self._show_step()

    def action_back(self) -> None:
        self._back()

    def _forward_to_choices(self, action: str) -> None:
        target = self._get_target_choices()
        if target is None:
            return
        if not target.has_focus:
            target.focus()
        getattr(target, f"action_{action}")()

    def _get_target_choices(self) -> ChoiceList | None:
        focused = self.focused
        if isinstance(focused, ChoiceList):
            return focused
        panel = self.query_one("#choices-panel", Container)
        lists = list(panel.query(ChoiceList))
        return lists[0] if lists else self._active_choices

    def action_next_choice_list(self) -> None:
        panel = self.query_one("#choices-panel", Container)
        lists = list(panel.query(ChoiceList))
        if len(lists) <= 1:
            return
        for i, cl in enumerate(lists):
            if cl.has_focus:
                lists[(i + 1) % len(lists)].focus()
                return
        lists[0].focus()

    def action_nav_up(self) -> None:
        self._forward_to_choices("cursor_up")

    def action_nav_down(self) -> None:
        self._forward_to_choices("cursor_down")

    def action_nav_toggle(self) -> None:
        self._forward_to_choices("toggle")

    def action_nav_submit(self) -> None:
        if self._active_choices is not None:
            self._forward_to_choices("submit")
            return
        focused = self.focused
        if isinstance(focused, Input):
            focused.action_submit()

    def _show_step(self) -> None:
        self._clear_step()
        handlers = {
            "doctor": self._step_doctor,
            "framework": self._step_framework,
            "mode": self._step_mode,
            "model": self._step_model,
            "runtime": self._step_runtime,
            "capabilities": self._step_capabilities,
            "nginx": self._step_nginx,
            "summary": self._step_summary,
            "done": self._step_done,
        }
        self._set_step_title(STEP_TITLES[self.step])
        handlers[self.step]()

    def _step_doctor(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(self._section_label("Doctor checks · Docker, GPU, CUDA, nginx"))

        host = self.state.host
        body.mount(self._skill_line("os", f"{host.os_type.value} {host.arch}"))
        if host.is_wsl:
            body.mount(Static("  [dim]WSL detected[/dim]", classes="skill-line"))
        if host.gpu_name:
            body.mount(self._skill_line("gpu", f"{host.gpu_name} ({host.vram_gb or '?'} GB VRAM)"))
        if host.ram_gb:
            body.mount(self._skill_line("ram", f"{host.ram_gb} GB"))

        for check in host.checks:
            color = {"ok": "green", "warn": "yellow", "fail": "red"}.get(check.status.value, "white")
            body.mount(
                Static(
                    f"  [{color}]{check.status.value.upper()}[/{color}] [#c9a227]{check.name}:[/] {check.message}",
                    classes="skill-line",
                )
            )
            if check.hint:
                body.mount(Static(f"    [dim]→ {check.hint}[/dim]", classes="skill-line"))

        self._mount_choices(
            [("continue", "Continue setup →"), ("stop", "Stop running Docker stack")],
            id="doctor-continue",
        )
        self._update_footer(
            "Welcome to Local LLM Setup! Use ↑↓ or j/k to navigate, Space to select, Enter to confirm.",
            "Esc back · q quit · / commands",
        )

    def _step_framework(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(self._section_label("frameworks · inference backends"))
        for p in list_frameworks():
            body.mount(self._skill_line(p.meta.framework.value, p.meta.description))

        choices = [(p.meta.framework.value, p.meta.display_name) for p in list_frameworks()]
        self._mount_choices(choices, id="framework-choice")
        self._update_footer("Select a framework to host your local LLM.", "↑↓ j/k navigate · Enter confirm")

    def _step_mode(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(self._section_label("config · setup depth"))
        body.mount(self._skill_line("quick", "Sensible defaults — fastest path"))
        body.mount(self._skill_line("full", "Every option — model, runtime, Docker, nginx"))

        self._mount_choices(
            [("quick", "Quick — sensible defaults"), ("full", "Full — all provider options")],
            id="mode-choice",
        )
        self._update_footer("Choose quick or full configuration.", "↑↓ j/k navigate · Enter confirm")

    def _model_field_values(self) -> dict[str, str]:
        s = self.state
        port = str(s.port) if s.port is not None else ""
        return {
            "model-input": s.model_name,
            "ctx-input": str(s.context_length),
            "quant-input": s.quantization,
            "tp-input": str(s.tensor_parallel),
            "hf-token-env-input": s.hf_token_env,
            "hf-token-input": s.hf_token,
            "ollama-parallel-input": s.ollama_parallel,
            "llama-ngl-input": s.llama_ngl,
            "port-input": port,
            "bind-host-input": s.bind_host_override,
            "image-tag-input": s.image_tag,
            "shm-input": s.shm_size,
            "gpu-count-input": str(s.gpu_count),
            "extra-env-input": s.extra_env_text,
            "extra-args-input": s.extra_args_text,
            "ollama-models-input": s.ollama_models,
            "ollama-host-input": s.ollama_host,
            "profile-name-input": s.profile_name,
            "output-dir-input": str(s.output_dir),
            "nginx-port": str(s.nginx_port),
            "nginx-server-name": s.nginx_server_name,
            "nginx-bind-host": s.nginx_bind_host,
            "nginx-body-size": s.nginx_client_max_body_size,
            "nginx-proxy-timeout": s.nginx_proxy_read_timeout,
            "publish-port-input": str(s.publish_port) if s.publish_port is not None else "",
            "gpu-device-ids-input": s.gpu_device_ids_text,
            "ipc-input": s.ipc,
            "volumes-input": s.extra_volumes_text,
            "command-shell-input": s.command_shell,
            "vllm-gpu-mem-input": s.vllm_gpu_mem,
            "vllm-max-seqs-input": s.vllm_max_seqs,
            "vllm-tool-parser-input": s.vllm_tool_parser,
            "vllm-reasoning-parser-input": s.vllm_reasoning_parser,
            "vllm-kv-cache-input": s.vllm_kv_cache,
            "vllm-mm-limit-input": s.vllm_mm_limit,
            "vllm-trust-remote-input": s.vllm_trust_remote,
            "vllm-prefix-cache-input": s.vllm_prefix_cache,
        }

    def _sync_model_fields(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        self.state.model_name = read_field(body, "model-input")
        if self.state.mode != ConfigMode.FULL:
            return
        try:
            self.state.context_length = int(read_field(body, "ctx-input", "8192") or "8192")
        except ValueError:
            pass
        self.state.quantization = read_field(body, "quant-input")
        try:
            self.state.tensor_parallel = int(read_field(body, "tp-input", "1") or "1")
        except ValueError:
            pass
        self.state.hf_token_env = read_field(body, "hf-token-env-input", "HF_TOKEN") or "HF_TOKEN"
        token = read_field(body, "hf-token-input")
        if token:
            self.state.hf_token = token
        self.state.ollama_parallel = read_field(body, "ollama-parallel-input", "1")
        self.state.llama_ngl = read_field(body, "llama-ngl-input")
        self.state.vllm_gpu_mem = read_field(body, "vllm-gpu-mem-input")
        self.state.vllm_max_seqs = read_field(body, "vllm-max-seqs-input")
        self.state.vllm_tool_parser = read_field(body, "vllm-tool-parser-input")
        self.state.vllm_reasoning_parser = read_field(body, "vllm-reasoning-parser-input")
        self.state.vllm_kv_cache = read_field(body, "vllm-kv-cache-input")
        self.state.vllm_mm_limit = read_field(body, "vllm-mm-limit-input")
        self.state.vllm_trust_remote = read_field(body, "vllm-trust-remote-input", "false")
        self.state.vllm_prefix_cache = read_field(body, "vllm-prefix-cache-input", "false")

    def _sync_runtime_fields(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        port_text = read_field(body, "port-input")
        if port_text:
            try:
                self.state.port = int(port_text)
            except ValueError:
                pass
        bind = read_field(body, "bind-host-input")
        if bind:
            self.state.bind_host_override = bind
        self.state.image_tag = read_field(body, "image-tag-input")
        shm = read_field(body, "shm-input")
        if shm:
            self.state.shm_size = shm
        try:
            self.state.gpu_count = int(read_field(body, "gpu-count-input", "1") or "1")
        except ValueError:
            pass
        self.state.extra_env_text = read_field(body, "extra-env-input")
        self.state.extra_args_text = read_field(body, "extra-args-input")
        publish = read_field(body, "publish-port-input")
        if publish:
            try:
                self.state.publish_port = int(publish)
            except ValueError:
                pass
        else:
            self.state.publish_port = None
        self.state.gpu_device_ids_text = read_field(body, "gpu-device-ids-input")
        self.state.ipc = read_field(body, "ipc-input")
        self.state.extra_volumes_text = read_field(body, "volumes-input")
        self.state.command_shell = read_field(body, "command-shell-input")
        self.state.ollama_models = read_field(body, "ollama-models-input", "/root/.ollama")
        self.state.ollama_host = read_field(body, "ollama-host-input", "0.0.0.0:11434")
        self.state.profile_name = read_field(body, "profile-name-input", "default") or "default"
        out = read_field(body, "output-dir-input")
        if out:
            self.state.output_dir = Path(out)

    def _sync_nginx_fields(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        try:
            self.state.nginx_port = int(read_field(body, "nginx-port", "8080") or "8080")
        except ValueError:
            pass
        if self.state.mode != ConfigMode.FULL:
            return
        self.state.nginx_server_name = read_field(body, "nginx-server-name", "_") or "_"
        bind = read_field(body, "nginx-bind-host")
        if bind:
            self.state.nginx_bind_host = bind
        body_size = read_field(body, "nginx-body-size")
        if body_size:
            self.state.nginx_client_max_body_size = body_size
        timeout = read_field(body, "nginx-proxy-timeout")
        if timeout:
            self.state.nginx_proxy_read_timeout = timeout

    def _step_model(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        fw = self.state.framework
        plugin = get_plugin(fw) if fw else None

        if self.state.mode == ConfigMode.FULL and fw:
            body.mount(self._section_label("model · name and parameters"))
            mount_fields(body, model_fields(fw), self._model_field_values())
            last_id = model_fields(fw)[-1].id
            self._update_footer(
                "Tab through fields · Enter on last field to continue.",
                f"last field: {last_id}",
            )
            self.call_after_refresh(lambda: body.query_one(f"#{model_fields(fw)[0].id}", Input).focus())
            return

        hint = "Ollama model name (e.g. llama3.2)"
        if fw in (Framework.VLLM, Framework.SGLANG):
            hint = "Hugging Face repo id (e.g. meta-llama/Meta-Llama-3-8B-Instruct)"
        elif fw == Framework.LLAMACPP:
            hint = "GGUF path or URL (e.g. /models/model.gguf)"

        default = plugin.meta.quick_defaults.get("model", "") if plugin else ""
        body.mount(self._section_label("model · name and parameters"))
        body.mount(Static(f"  {hint}", classes="skill-line"))
        inp = Input(value=self.state.model_name or default, placeholder=hint, id="model-input")
        body.mount(inp)
        self._update_footer("Type model name, then press Enter to continue.", "Enter submit")
        self.call_after_refresh(inp.focus)

    def _step_runtime(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        fw = self.state.framework
        if not fw:
            return
        body.mount(self._section_label("setup · profile and output"))
        mount_fields(body, setup_fields(), self._model_field_values())
        body.mount(self._section_label("runtime · Docker & networking"))
        values = self._model_field_values()
        for spec in runtime_fields(fw):
            if not values.get(spec.id) and spec.default:
                values[spec.id] = spec.default
        mount_fields(body, runtime_fields(fw), values)
        last_id = runtime_fields(fw)[-1].id
        self._update_footer(
            "Tab through fields · Enter on last field to continue.",
            f"last field: {last_id}",
        )
        self.call_after_refresh(lambda: body.query_one("#profile-name-input", Input).focus())

    def _step_capabilities(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        fw = self.state.framework
        plugin = get_plugin(fw) if fw else None
        body.mount(self._section_label("capabilities · model features"))

        opts: list[tuple[str, str]] = [("text", "Text generation (always on)")]
        if plugin:
            if plugin.meta.supports_vision:
                opts.append(("vision", "Vision / image input"))
            if plugin.meta.supports_audio:
                opts.append(("audio", "Audio input"))
            if plugin.meta.supports_tool_calling:
                opts.append(("tool_calling", "Tool calling"))
            if plugin.meta.supports_mtp:
                opts.append(("mtp", "Speculative decoding / MTP"))
        if self.state.mode != ConfigMode.FULL:
            opts.append(("public", "Bind to 0.0.0.0 (expose publicly)"))

        for cid, label in opts:
            body.mount(self._skill_line(cid, label))

        if plugin and plugin.meta.supports_mtp:
            body.mount(self._section_label("mtp_drafter: (if MTP enabled)"))
            body.mount(Input(placeholder="org/drafter-model", id="drafter-input"))

        self._mount_choices(opts, multi=True, id="cap-choice")
        self._update_footer("Space toggles options · Enter confirms.", "↑↓ j/k navigate · Tab next list")

    def _step_nginx(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(self._section_label("nginx · reverse proxy"))
        body.mount(self._skill_line("no", "Direct to framework port"))
        body.mount(self._skill_line("yes_nokey", "nginx.conf without API keys"))
        body.mount(self._skill_line("yes_key", "nginx.conf + api_keys.map"))

        if self.state.mode == ConfigMode.FULL:
            mount_fields(
                body,
                nginx_basic_fields() + nginx_advanced_fields(),
                self._model_field_values(),
            )
            self._mount_choices(
                [
                    ("cors", "Enable CORS headers"),
                    ("tunnel", "Include cloudflared tunnel in compose"),
                ],
                multi=True,
                id="nginx-extra-choice",
            )
            checked: set[str] = set()
            if self.state.nginx_enable_cors:
                checked.add("cors")
            if self.state.nginx_tunnel_enabled:
                checked.add("tunnel")

            def _preset_nginx_extra() -> None:
                self.query_one("#nginx-extra-choice", ChoiceList).set_checked(checked)

            self.call_after_refresh(_preset_nginx_extra)
        else:
            body.mount(self._section_label("listen_port:"))
            body.mount(Input(value=str(self.state.nginx_port), id="nginx-port"))

        self._mount_choices(
            [
                ("no", "No nginx — direct access"),
                ("yes_nokey", "Yes nginx — no API key"),
                ("yes_key", "Yes nginx — with API key auth"),
            ],
            id="nginx-choice",
        )
        self._update_footer("Select nginx option and press Enter.", "↑↓ j/k navigate · Enter confirm")

    def _step_summary(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        try:
            config = self.state.to_config()
            issues = validate_setup(config.frameworks, config.host)
        except ValueError as exc:
            body.mount(Static(f"[red]Config error: {exc}[/red]", classes="skill-line"))
            self._update_footer("Fix errors and press Esc to go back.", "")
            return

        fc = config.frameworks[0]
        body.mount(self._skill_line("framework", fc.framework.value))
        body.mount(self._skill_line("model", fc.model.name))
        body.mount(self._skill_line("mode", fc.mode.value))
        if fc.model.quantization:
            body.mount(self._skill_line("quantization", fc.model.quantization))
        body.mount(self._skill_line("context", str(fc.model.context_length)))
        if fc.framework in (Framework.VLLM, Framework.SGLANG):
            body.mount(self._skill_line("tensor_parallel", str(fc.model.tensor_parallel)))
        if len(config.frameworks) == 1:
            body.mount(self._skill_line("port", f"{fc.bind_host}:{fc.port}"))
        else:
            for item in config.frameworks:
                body.mount(
                    self._skill_line(
                        f"port-{item.framework.value}",
                        f"{item.bind_host}:{item.port}",
                    )
                )
        if self.state.mode == ConfigMode.FULL:
            body.mount(self._skill_line("image", fc.image_tag or "(provider default)"))
            body.mount(self._skill_line("shm_size", fc.shm_size))
            if fc.framework in (Framework.VLLM, Framework.SGLANG):
                body.mount(self._skill_line("gpu_count", str(fc.gpu_count)))
            if fc.extra_env:
                body.mount(self._skill_line("extra_env", format_extra_env(fc.extra_env)))
            if fc.extra_args:
                body.mount(self._skill_line("extra_args", format_extra_args(fc.extra_args)))
            if fc.publish_port is not None:
                body.mount(self._skill_line("publish_port", f"{fc.publish_port}:{fc.port}"))
            if fc.gpu_device_ids:
                body.mount(self._skill_line("gpu_device_ids", ",".join(fc.gpu_device_ids)))
            if fc.ipc:
                body.mount(self._skill_line("ipc", fc.ipc))
            if fc.extra_volumes:
                body.mount(self._skill_line("volumes", ", ".join(fc.extra_volumes)))
            if fc.vllm:
                v = fc.vllm
                if v.gpu_memory_utilization is not None:
                    body.mount(self._skill_line("gpu_memory_utilization", str(v.gpu_memory_utilization)))
                if v.tool_call_parser:
                    body.mount(self._skill_line("tool_call_parser", v.tool_call_parser))
                if v.limit_mm_per_prompt:
                    body.mount(self._skill_line("limit_mm_per_prompt", v.limit_mm_per_prompt))
        body.mount(
            self._skill_line(
                "capabilities",
                f"vision={fc.capabilities.vision} tools={fc.capabilities.tool_calling} mtp={fc.capabilities.mtp}",
            )
        )
        body.mount(self._skill_line("nginx", str(config.nginx.enabled)))
        if config.nginx.enabled and self.state.mode == ConfigMode.FULL:
            body.mount(self._skill_line("nginx_port", str(config.nginx.listen_port)))
            body.mount(self._skill_line("server_name", config.nginx.server_name))
            body.mount(self._skill_line("client_max_body_size", config.nginx.client_max_body_size))
            body.mount(self._skill_line("proxy_read_timeout", config.nginx.proxy_read_timeout))
            body.mount(self._skill_line("cors", str(config.nginx.enable_cors)))
            body.mount(self._skill_line("tunnel", str(config.nginx.tunnel_enabled)))
        body.mount(self._skill_line("profile", config.profile_name))
        body.mount(self._skill_line("output", str(config.output_dir)))

        for issue in issues:
            color = "red" if issue.level == "error" else "yellow"
            body.mount(Static(f"  [{color}]{issue.level.upper()}:[/{color}] {issue.message}", classes="skill-line"))

        for warning in self.state.port_warnings:
            body.mount(Static(f"  [yellow]PORT:[/yellow] {warning}", classes="skill-line"))

        errors = [i for i in issues if i.level == "error"]
        if errors:
            self._update_footer("Fix validation errors. Press Esc to go back.", "")
            return

        self._mount_choices(
            [
                ("generate_run", "Generate & start Docker"),
                ("generate", "Generate files only"),
            ],
            id="generate-choice",
        )
        self._update_footer("Review config, then press Enter to deploy.", "↑↓ Enter confirm")

    def _step_done(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        try:
            config = self.state.to_config()
            result = generate(config)
            profile_path = save_profile(config)
            body.mount(Static("[green]✓ Generated successfully[/green]", classes="skill-line"))
            body.mount(self._skill_line("output", str(config.output_dir.resolve())))
            body.mount(self._skill_line("profile", str(profile_path)))
            for w in result.warnings:
                body.mount(Static(f"  [yellow]warn:[/yellow] {w}", classes="skill-line"))

            if self.state.auto_run:
                body.mount(self._section_label("deploy · docker compose"))
                self._mount_deploy_log(body)
                self._update_footer("Starting Docker containers...", "please wait")
                self.run_worker(
                    partial(self._do_deploy, config),
                    name="deploy",
                    thread=True,
                    exclusive=True,
                )
            else:
                body.mount(self._section_label("run:"))
                for cmd in result.run_commands:
                    body.mount(Static(f"  {cmd}", classes="skill-line"))
                urls = build_access_urls(config)
                body.mount(self._section_label("access:"))
                for line in format_access_lines(urls, markup=True):
                    if line.strip():
                        body.mount(Static(line.strip(), classes="access-line"))
                self._update_footer(f"Ready · {urls.primary_url}", LOG_FOOTER_HINT)

            if result.api_keys_map and config.nginx.api_keys:
                body.mount(self._section_label("api_keys:"))
                for k in config.nginx.api_keys:
                    body.mount(Static(f"  {k.key}  ({k.label})", classes="skill-line"))
        except Exception as exc:
            body.mount(Static(f"[red]Error: {exc}[/red]", classes="skill-line"))
            self._update_footer("Generation failed.", "Esc to go back")

    def _do_deploy(self, config: SetupConfig) -> DeployResult:
        def on_output(line: str) -> None:
            def _write() -> None:
                self._deploy_log.write(line)
                self._deploy_log.scroll_end(animate=False)

            self.call_from_thread(_write)

        def on_status(msg: str) -> None:
            self.call_from_thread(self._update_footer, msg, "please wait")

        return deploy(config, pull=True, on_output=on_output, on_status=on_status)

    def _do_stop(self) -> DeployResult:
        def on_output(line: str) -> None:
            def _write() -> None:
                if self._deploy_log is not None:
                    self._deploy_log.write(line)
                    self._deploy_log.scroll_end(animate=False)

            self.call_from_thread(_write)

        def on_status(msg: str) -> None:
            self.call_from_thread(self._update_footer, msg, "please wait")

        return stop_stack(
            self.state.output_dir,
            remove_volumes=self._remove_volumes_on_stop,
            on_output=on_output,
            on_status=on_status,
        )

    def _do_curl_test(self, config: SetupConfig) -> DeployResult:
        def on_output(line: str) -> None:
            def _write() -> None:
                if self._deploy_log is not None:
                    self._deploy_log.write(line)
                    self._deploy_log.scroll_end(animate=False)

            self.call_from_thread(_write)

        def on_status(msg: str) -> None:
            self.call_from_thread(self._update_footer, msg, "please wait")

        return run_curl_tests(config, on_output=on_output, on_status=on_status)

    def _mount_deploy_log(self, body: VerticalScroll) -> CopyableRichLog:
        log = CopyableRichLog(id="deploy-log")
        panel = Container(id="log-panel")
        body.mount(panel)
        panel.mount(log)
        self._deploy_log = log
        return log

    def _ensure_deploy_log(self) -> CopyableRichLog:
        if self._deploy_log is not None:
            return self._deploy_log
        body = self.query_one("#step-body", VerticalScroll)
        return self._mount_deploy_log(body)

    def _write_command_output(self, lines: list[str]) -> None:
        log = self._ensure_deploy_log()
        for line in lines:
            log.write(line)
        log.scroll_end(animate=False)

    def action_focus_command(self) -> None:
        inp = self.query_one("#command-input", Input)
        inp.focus()
        if not inp.value.startswith("/"):
            inp.value = "/" + inp.value

    def _go_to_step(self, step_name: str) -> None:
        steps = self._wizard_steps()
        if step_name in steps:
            self._step_idx = steps.index(step_name)
            self._show_step()

    def _show_providers(self) -> None:
        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        cl = ChoiceList(list(PROVIDER_CHOICES), id="provider-command")
        panel.mount(cl)
        self._active_choices = cl
        self.call_after_refresh(cl.focus)
        self._update_footer("เลือก provider (ollama / vllm)", "↑↓ Enter confirm · Esc cancel")

    def _handle_slash_command(self, raw: str) -> None:
        cmd = normalize_command(raw)
        if not cmd:
            return
        resolved = self._command_aliases.get(cmd, cmd)

        if resolved == "help":
            self._write_command_output(format_help_lines())
            self._update_footer("Slash command help", "/help · /providers · /delete-container · /test")
            return

        if resolved == "providers":
            self._show_providers()
            return

        if resolved == "doctor":
            self._go_to_step("doctor")
            return

        if resolved == "stop":
            self._remove_volumes_on_stop = False
            self._begin_stop()
            return

        if resolved == "delete-container":
            self._remove_volumes_on_stop = True
            self._begin_stop(label="delete · docker compose down -v")
            return

        if resolved in ("test", "curl"):
            if not self._deploy_succeeded:
                self._write_command_output(["[yellow]Stack is not running — deploy first with /deploy[/yellow]"])
                return
            try:
                config = self.state.to_config()
            except ValueError as exc:
                self._write_command_output([f"[red]{exc}[/red]"])
                return
            log = self._ensure_deploy_log()
            self._update_footer("Running curl tests...", "please wait")
            self.run_worker(partial(self._do_curl_test, config), name="curl-test", thread=True, exclusive=True)
            return

        if resolved == "deploy":
            try:
                config = self.state.to_config()
                generate(config)
                save_profile(config)
            except (ValueError, Exception) as exc:
                self._write_command_output([f"[red]{exc}[/red]"])
                return
            body = self.query_one("#step-body", VerticalScroll)
            body.remove_children()
            body.mount(self._section_label("deploy · docker compose"))
            self._mount_deploy_log(body)
            self._deploy_succeeded = False
            self._update_footer("Starting Docker containers...", "please wait")
            self.run_worker(partial(self._do_deploy, config), name="deploy", thread=True, exclusive=True)
            return

        self._write_command_output([f"[red]Unknown command: /{cmd}[/red]", "Type /help for available commands."])

    def _begin_stop(self, *, label: str = "stop · docker compose") -> None:
        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        self._active_choices = None
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        body.mount(self._section_label(label))
        self._mount_deploy_log(body)
        self._deploy_succeeded = False
        self._update_footer("Stopping Docker stack...", "please wait")
        self.run_worker(self._do_stop, name="stop", thread=True, exclusive=True)

    def action_stop_stack(self) -> None:
        if self.step in ("done", "doctor"):
            self._remove_volumes_on_stop = False
            self._begin_stop()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name not in ("deploy", "stop", "curl-test"):
            return
        if event.state != WorkerState.SUCCESS:
            if event.state == WorkerState.ERROR:
                labels = {"deploy": "Deploy", "stop": "Stop", "curl-test": "Curl test"}
                label = labels.get(event.worker.name, event.worker.name)
                self._update_footer(f"[red]{label} worker failed[/red]", "q quit · /help")
            return
        result: DeployResult = event.worker.result
        if event.worker.name == "curl-test":
            if self._deploy_log is not None:
                self._deploy_log.focus()
            if result.success:
                self._update_footer("Curl tests passed.", LOG_FOOTER_HINT)
            else:
                self._update_footer(
                    f"Curl test failed: {result.error or 'unknown error'}",
                    "c copy mode · drag select · Ctrl+C · v/Esc pretty",
                )
            return
        if event.worker.name == "stop":
            if result.success:
                self._deploy_succeeded = False
                self._update_footer("Docker stack stopped.", "q quit")
                if self._deploy_log is not None:
                    self._deploy_log.write("\n[bold green]✓ Stack stopped[/bold green]")
            else:
                self._update_footer(f"Stop failed: {result.error or 'unknown error'}", "q quit")
                if self._deploy_log is not None:
                    self._deploy_log.write(f"\n[bold red]✗ {result.error or 'stop failed'}[/bold red]")
            return
        if result.success:
            self._deploy_succeeded = True
            urls = result.access_urls
            footer = urls.primary_url if urls else "Docker stack is running!"
            self._update_footer(f"Running · {footer}", LOG_FOOTER_HINT)
            self._deploy_log.write("\n[bold green]✓ Deploy complete[/bold green]")
            if urls:
                for line in format_access_lines(urls):
                    self._deploy_log.write(line)
        else:
            self._deploy_succeeded = False
            self._update_footer(f"Deploy failed: {result.error or 'unknown error'}", "q quit")
            self._deploy_log.write(f"\n[bold red]✗ {result.error or 'deploy failed'}[/bold red]")

    @on(ChoiceList.Submitted, "#doctor-continue")
    def on_doctor_continue(self, event: ChoiceList.Submitted) -> None:
        if event.selected_ids[0] == "stop":
            self._begin_stop()
        else:
            self._next()

    @on(ChoiceList.Submitted, "#framework-choice")
    def on_framework(self, event: ChoiceList.Submitted) -> None:
        self.state.framework = Framework(event.selected_ids[0])
        self._next()

    @on(ChoiceList.Submitted, "#mode-choice")
    def on_mode(self, event: ChoiceList.Submitted) -> None:
        self.state.mode = ConfigMode(event.selected_ids[0])
        self._next()

    @on(Input.Submitted, "#model-input")
    def on_model_submitted(self, event: Input.Submitted) -> None:
        if self.state.mode == ConfigMode.FULL:
            self._sync_model_fields()
            return
        self.state.model_name = event.value.strip()
        if self.state.model_name:
            self._next()

    @on(Input.Submitted)
    def on_full_field_submitted(self, event: Input.Submitted) -> None:
        iid = event.input.id
        if iid in ("command-input", "model-input"):
            return
        fw = self.state.framework
        if self.step == "model" and self.state.mode == ConfigMode.FULL and fw:
            self._sync_model_fields()
            if iid == model_fields(fw)[-1].id and self.state.model_name:
                self._next()
        elif self.step == "runtime" and fw:
            self._sync_runtime_fields()
            if iid == runtime_fields(fw)[-1].id:
                self._next()

    @on(ChoiceList.Submitted, "#cap-choice")
    def on_capabilities(self, event: ChoiceList.Submitted) -> None:
        ids = set(event.selected_ids)
        self.state.capabilities = Capabilities(
            text=True,
            vision="vision" in ids,
            audio="audio" in ids,
            tool_calling="tool_calling" in ids,
            mtp="mtp" in ids,
        )
        self.state.bind_public = "public" in ids
        body = self.query_one("#step-body", VerticalScroll)
        try:
            drafter = body.query_one("#drafter-input", Input)
            if self.state.capabilities.mtp:
                self.state.capabilities.mtp_drafter_model = drafter.value or None
        except Exception:
            pass
        self._next()

    @on(ChoiceList.Submitted, "#nginx-choice")
    def on_nginx(self, event: ChoiceList.Submitted) -> None:
        choice = event.selected_ids[0]
        self.state.nginx_enabled = choice != "no"
        self.state.nginx_api_keys = choice == "yes_key"
        self._sync_nginx_fields()
        if self.state.mode == ConfigMode.FULL:
            try:
                extra = self.query_one("#nginx-extra-choice", ChoiceList)
                ids = set(extra.selected_ids())
                self.state.nginx_enable_cors = "cors" in ids
                self.state.nginx_tunnel_enabled = "tunnel" in ids
            except Exception:
                pass
        self._next()

    @on(ChoiceList.Submitted, "#generate-choice")
    def on_generate(self, event: ChoiceList.Submitted) -> None:
        self.state.auto_run = event.selected_ids[0] == "generate_run"
        self._next()

    @on(ChoiceList.Submitted, "#provider-command")
    def on_provider_command(self, event: ChoiceList.Submitted) -> None:
        fw = Framework(event.selected_ids[0])
        self.state.framework = fw
        plugin = get_plugin(fw)
        if not self.state.model_name:
            self.state.model_name = plugin.meta.quick_defaults.get("model", "")
        self._go_to_step("model")
        self._update_footer(
            f"Provider: [#c9a227]{fw.value}[/] — type model name, Enter to continue.",
            "/providers · Esc back",
        )

    @on(Input.Submitted, "#command-input")
    def on_command_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return
        self._handle_slash_command(raw)


def run_tui(output_dir: Path = OUTPUT_DIR, initial_config: SetupConfig | None = None) -> None:
    app = LocalLLMSetupApp(output_dir=output_dir, initial_config=initial_config)
    app.run()
