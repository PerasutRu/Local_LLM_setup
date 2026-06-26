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

from local_llm_setup.tui.widgets import CommandInput, CopyableRichLog, LOG_FOOTER_HINT
from local_llm_setup.tui.styles import linkify_text, style_section
from textual.worker import Worker, WorkerState

from local_llm_setup.detect import detect_host
from local_llm_setup.frameworks import default_docker_image, get_plugin, list_frameworks, validate_setup
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
from local_llm_setup.paths import OUTPUT_DIR, normalize_output_dir, resolve_model_cache_host_path
from local_llm_setup.instances import list_instances, list_running_instances
from local_llm_setup.profiles import delete_profile, load_profile, save_profile
from local_llm_setup.renderers import generate, prepare_config
from local_llm_setup.runner import DeployResult, deploy, run_curl_tests, stop_all_stacks, stop_stack
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
from local_llm_setup.tui.commands import (
    PROVIDER_CHOICES,
    SLASH_COMMANDS,
    command_placeholder,
    format_help_lines,
    format_suggestions,
    match_commands,
    match_commands_for_tab,
    parse_command,
    resolve_submit_command,
    selected_match,
)
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
        self.model_cache_host_path_text: str = ""

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
            self.model_cache_host_path_text = (
                str(fc.model_cache_host_path) if fc.model_cache_host_path else ""
            )
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
            if self.framework == Framework.OLLAMA:
                self.ollama_host = config.frameworks[0].extra_env.get(
                    "OLLAMA_HOST",
                    f"0.0.0.0:{config.frameworks[0].port}",
                )
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
        fc.image_tag = self.image_tag or None
        cache_path = self.model_cache_host_path_text.strip()
        fc.model_cache_host_path = Path(cache_path) if cache_path else None

        if self.mode == ConfigMode.FULL:
            if self.port is not None:
                fc.port = self.port
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
            output_dir=normalize_output_dir(self.profile_name, self.output_dir),
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
        self._remove_volumes_on_delete = False
        self._remove_model_cache_on_delete = False
        self._stop_target: str = "current"
        self._delete_targets: list[str] = []
        self._command_suggest_index = 0
        self._command_bar_active = False
        self._command_input_sync = False
        self._editing_instance: str | None = None
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
                yield Static("", id="command-suggest")
                yield CommandInput(
                    placeholder=command_placeholder(),
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
        if not self._command_bar_active and not self._command_input_active():
            self.call_after_refresh(cl.focus)
        return cl

    def _section_label(self, text: str) -> Static:
        return Static(style_section(text), classes="section-label")

    def _skill_line(self, key: str, val: str) -> Static:
        return Static(f"[#c9a227]{key}:[/] {val}", classes="skill-line")

    def _focus_next_field(self, current_id: str, field_ids: list[str]) -> None:
        if current_id not in field_ids:
            return
        next_index = field_ids.index(current_id) + 1
        if next_index >= len(field_ids):
            return
        body = self.query_one("#step-body", VerticalScroll)
        try:
            body.query_one(f"#{field_ids[next_index]}", Input).focus()
        except Exception:
            return

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
        if self._command_input_active():
            self._cycle_command_suggestion(-1)
            return
        self._forward_to_choices("cursor_up")

    def action_nav_down(self) -> None:
        if self._command_input_active():
            self._cycle_command_suggestion(1)
            return
        self._forward_to_choices("cursor_down")

    def action_nav_toggle(self) -> None:
        if self._command_input_active():
            return
        self._forward_to_choices("toggle")

    def action_nav_submit(self) -> None:
        if self._command_input_active():
            self.query_one("#command-input", CommandInput).action_submit_command()
            return
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
            body.mount(
                self._skill_line(
                    p.meta.framework.value,
                    f"{p.meta.description} · default image: {p.meta.default_image}",
                )
            )

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
            "output-dir-input": str(normalize_output_dir(s.profile_name, s.output_dir)),
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
            "model-cache-path-input": s.model_cache_host_path_text,
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
        self.state.model_cache_host_path_text = read_field(body, "model-cache-path-input")
        self.state.profile_name = read_field(body, "profile-name-input", "default") or "default"
        self.state.output_dir = normalize_output_dir(self.state.profile_name, self.state.output_dir)

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
        default_image = default_docker_image(fw, self.state.host) if fw else ""
        body.mount(self._section_label("model · name and parameters"))
        body.mount(Static(f"  {hint}", classes="skill-line"))
        inp = Input(value=self.state.model_name or default, placeholder=hint, id="model-input")
        body.mount(inp)
        body.mount(Static(f"  Docker image — default: {default_image}", classes="skill-line"))
        body.mount(
            Input(
                value=self.state.image_tag,
                placeholder=default_image,
                id="image-tag-input",
            )
        )
        default_cache = normalize_output_dir(self.state.profile_name, self.state.output_dir) / f"model-{fw.value}"
        body.mount(Static("  Model cache host path (optional)", classes="skill-line"))
        body.mount(
            Input(
                value=self.state.model_cache_host_path_text,
                placeholder=str(default_cache),
                id="model-cache-path-input",
            )
        )
        self._update_footer(
            "Set model, Docker image, and optional cache path · Enter to continue.",
            "Tab through fields · empty cache = default under output/",
        )
        self.call_after_refresh(inp.focus)

    def _step_runtime(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        fw = self.state.framework
        if not fw:
            return
        body.mount(self._section_label("setup · profile and output"))
        mount_fields(body, setup_fields(self.state.profile_name), self._model_field_values())
        body.mount(self._section_label("runtime · Docker & networking"))
        values = self._model_field_values()
        fields = runtime_fields(fw, self.state.host, self.state.profile_name)
        for spec in fields:
            if not values.get(spec.id) and spec.default:
                values[spec.id] = spec.default
        mount_fields(body, fields, values)
        last_id = fields[-1].id
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
        resolved_image = default_docker_image(fc.framework, config.host)
        if fc.image_tag:
            body.mount(self._skill_line("docker_image", fc.image_tag))
            if fc.image_tag != resolved_image:
                body.mount(self._skill_line("docker_image_default", f"provider default: {resolved_image}"))
        else:
            body.mount(self._skill_line("docker_image", f"{resolved_image} (default)"))
        if self.state.mode == ConfigMode.FULL:
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
        cache_path = resolve_model_cache_host_path(
            config.output_dir, fc.framework.value, fc.model_cache_host_path
        )
        body.mount(self._skill_line("model_cache", str(cache_path)))
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

        if self._stop_target == "__all__":
            return stop_all_stacks(
                remove_volumes=self._remove_volumes_on_stop,
                on_output=on_output,
                on_status=on_status,
            )

        if self._stop_target not in ("", "current"):
            for inst in list_instances():
                if inst.profile_name != self._stop_target:
                    continue
                config = None
                if inst.profile_path.is_file():
                    try:
                        config = load_profile(inst.profile_path)
                    except OSError:
                        config = None
                return stop_stack(
                    inst.output_dir,
                    config=config,
                    remove_volumes=self._remove_volumes_on_stop,
                    on_output=on_output,
                    on_status=on_status,
                )
            return DeployResult(success=False, error=f"Instance not found: {self._stop_target}")

        return stop_stack(
            self.state.output_dir,
            config=self.state.build_config() if self.state.framework else None,
            remove_volumes=self._remove_volumes_on_stop,
            on_output=on_output,
            on_status=on_status,
        )

    def _do_delete_profiles(self) -> DeployResult:
        def on_output(line: str) -> None:
            def _write() -> None:
                if self._deploy_log is not None:
                    self._deploy_log.write(line)
                    self._deploy_log.scroll_end(animate=False)

            self.call_from_thread(_write)

        def on_status(msg: str) -> None:
            self.call_from_thread(self._update_footer, msg, "please wait")

        instances = {inst.profile_name: inst for inst in list_instances()}
        errors: list[str] = []
        deleted_count = 0

        for name in self._delete_targets:
            inst = instances.get(name)
            if inst is None:
                errors.append(f"{name}: not found")
                continue

            if on_output:
                on_output(f"\n[bold #c9a227]→ {name}[/bold #c9a227]")

            config = None
            if inst.profile_path.is_file():
                try:
                    config = load_profile(inst.profile_path)
                except OSError:
                    config = None

            if inst.status == "running" or self._remove_volumes_on_delete:
                stop_result = stop_stack(
                    inst.output_dir,
                    config=config,
                    remove_volumes=self._remove_volumes_on_delete,
                    on_output=on_output,
                    on_status=on_status,
                )
                if not stop_result.success:
                    errors.append(f"{name}: stop failed — {stop_result.error or 'unknown error'}")
                    continue

            removed = delete_profile(
                name,
                config=config,
                remove_output=True,
                remove_model_cache=self._remove_model_cache_on_delete,
            )
            if not removed:
                errors.append(f"{name}: nothing to delete")
                continue

            deleted_count += 1
            if on_output:
                for path in removed:
                    on_output(f"  [dim]removed {path}[/dim]")

        if on_output:
            on_output("")
            if errors:
                on_output(f"[yellow]Deleted {deleted_count} profile(s); {len(errors)} error(s)[/yellow]")
                for err in errors:
                    on_output(f"  [red]{err}[/red]")
            elif deleted_count:
                on_output(f"[bold green]✓ Deleted {deleted_count} profile(s)[/bold green]")
            else:
                on_output("[dim]No profiles deleted.[/dim]")

        if errors:
            return DeployResult(success=False, error="; ".join(errors))
        return DeployResult(success=True, steps=[])

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

    def _set_command_mode(self, active: bool) -> None:
        """Shrink step content so slash-command menus are not covered by deploy logs."""
        root = self.query_one("#root", Container)
        if active:
            root.add_class("command-mode")
        else:
            root.remove_class("command-mode")

    def _exit_command_mode_if_needed(self) -> None:
        if self._command_input_active() or self._command_bar_active:
            return
        self._clear_command_suggestions()
        self._set_command_mode(False)

    def action_focus_command(self) -> None:
        self._command_bar_active = True
        self._set_command_mode(True)
        inp = self.query_one("#command-input", CommandInput)
        if not inp.value.startswith("/"):
            inp.value = "/" + inp.value
        inp.focus()
        self.call_after_refresh(self._update_command_suggestions)

    def action_autocomplete_command(self) -> None:
        if not self._command_input_active():
            return
        inp = self.query_one("#command-input", CommandInput)
        matches = match_commands_for_tab(inp.value)
        if not matches:
            return
        row = selected_match(inp.value, self._command_suggest_index, matches=matches)
        if row is None:
            return
        if inp.value == row.display and len(matches) > 1:
            self._command_suggest_index = (self._command_suggest_index + 1) % len(matches)
            row = matches[self._command_suggest_index]
        self._command_input_sync = True
        inp.value = row.display
        self._command_input_sync = False
        self._update_command_suggestions()

    def _command_input_active(self) -> bool:
        focused = self.focused
        return isinstance(focused, CommandInput) and focused.id == "command-input"

    def _cycle_command_suggestion(self, delta: int) -> None:
        inp = self.query_one("#command-input", CommandInput)
        matches = match_commands(inp.value)
        if not matches:
            return
        self._command_suggest_index = (self._command_suggest_index + delta) % len(matches)
        self._update_command_suggestions()

    def _update_command_suggestions(self) -> None:
        suggest = self.query_one("#command-suggest", Static)
        if not (self._command_input_active() or self._command_bar_active):
            suggest.update("")
            return
        inp = self.query_one("#command-input", CommandInput)
        if not inp.value.strip().startswith("/"):
            suggest.update("")
            return
        lines = format_suggestions(inp.value, selected=self._command_suggest_index)
        suggest.update("\n".join(lines))
        row = selected_match(inp.value, self._command_suggest_index)
        if row is not None:
            self.query_one("#hint-bar", Static).update(row.description)

    def _clear_command_suggestions(self) -> None:
        self._command_suggest_index = 0
        self.query_one("#command-suggest", Static).update("")

    def _go_to_step(self, step_name: str) -> None:
        steps = self._wizard_steps()
        if step_name in steps:
            self._step_idx = steps.index(step_name)
            self._show_step()

    def _show_instances(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        body.mount(self._section_label("instances · saved profiles & running stacks"))

        instances = list_instances()
        if not instances:
            body.mount(Static("  [dim]ยังไม่มี profile — สร้างใหม่จาก wizard[/dim]", classes="skill-line"))
        else:
            for inst in instances:
                status_color = {"running": "green", "stopped": "yellow", "not_deployed": "dim"}.get(
                    inst.status, "white"
                )
                fw = ", ".join(inst.frameworks) if inst.frameworks else "—"
                body.mount(
                    Static(
                        f"  [#c9a227]{inst.profile_name}[/] "
                        f"[{status_color}]{inst.status}[/{status_color}] · {fw} · ports: {inst.ports_summary}",
                        classes="skill-line",
                    )
                )

        choices: list[tuple[str, str]] = []
        for inst in instances:
            choices.append((f"edit:{inst.profile_name}", f"Edit · {inst.profile_name}"))
            if inst.status == "running":
                choices.append((f"stop:{inst.profile_name}", f"Stop · {inst.profile_name}"))
            else:
                choices.append((f"deploy:{inst.profile_name}", f"Deploy · {inst.profile_name}"))
        choices.append(("__new__", "Create new profile →"))
        if instances:
            choices.append(("delete:__picker__", "Delete profiles…"))

        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        cl = ChoiceList(choices, id="instances-choice")
        panel.mount(cl)
        self._active_choices = cl
        self.call_after_refresh(cl.focus)
        self._update_footer(
            "เลือก profile เพื่อแก้ไขหรือ deploy — แต่ละ profile ใช้ output folder แยกกัน",
            "↑↓ Enter confirm · Esc cancel",
        )

    def _load_profile(self, profile_name: str) -> bool:
        profile_path = Path("llm_local/profiles") / f"{profile_name}.yaml"
        if not profile_path.is_file():
            self._write_command_output([f"[red]Profile not found: {profile_name}[/red]"])
            return False
        try:
            config = load_profile(profile_path)
        except Exception as exc:
            self._write_command_output([f"[red]Failed to load profile: {exc}[/red]"])
            return False
        config.output_dir = normalize_output_dir(config.profile_name, config.output_dir)
        self.state = WizardState(config.output_dir, config)
        self._editing_instance = profile_name
        self._deploy_succeeded = False
        return True

    def _deploy_profile(self, profile_name: str) -> None:
        if not self._load_profile(profile_name):
            return
        try:
            config = self.state.to_config()
            generate(config)
            save_profile(config)
        except (ValueError, Exception) as exc:
            self._write_command_output([f"[red]{exc}[/red]"])
            return
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        body.mount(self._section_label(f"deploy · {profile_name}"))
        self._mount_deploy_log(body)
        self._deploy_succeeded = False
        self._update_footer("Starting Docker containers...", "please wait")
        self.run_worker(partial(self._do_deploy, config), name="deploy", thread=True, exclusive=True)

    def _stop_profile(self, profile_name: str) -> None:
        self._remove_volumes_on_stop = False
        self._stop_target = profile_name
        self._begin_stop(label=f"stop · {profile_name}")

    def _show_stop_picker(self, *, remove_volumes: bool = False) -> None:
        self._remove_volumes_on_stop = remove_volumes
        running = list_running_instances()
        deployed = [inst for inst in list_instances() if inst.status != "not_deployed"]

        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        title = "delete · choose instance" if remove_volumes else "stop · choose instance"
        body.mount(self._section_label(title))

        if not running:
            body.mount(Static("  [dim]ไม่มี stack ที่รันอยู่[/dim]", classes="skill-line"))
            if deployed:
                body.mount(Static("  [dim]deployed แต่ stopped:[/dim]", classes="skill-line"))
                for inst in deployed:
                    body.mount(
                        Static(
                            f"    [#c9a227]{inst.profile_name}[/] · ports: {inst.ports_summary}",
                            classes="skill-line",
                        )
                    )
            self.query_one("#choices-panel", Container).remove_children()
            self._active_choices = None
            self._clear_command_suggestions()
            self._update_footer("No running stacks.", "/stop smollm-1 · /instances · /help")
            return

        for inst in running:
            fw = ", ".join(inst.frameworks) if inst.frameworks else "—"
            body.mount(
                Static(
                    f"  [#c9a227]{inst.profile_name}[/] · {fw} · ports: {inst.ports_summary}",
                    classes="skill-line",
                )
            )

        choices: list[tuple[str, str]] = [
            ("__all__", f"Stop all ({len(running)} running)"),
        ]
        for inst in running:
            verb = "Delete" if remove_volumes else "Stop"
            choices.append((inst.profile_name, f"{verb} · {inst.profile_name}"))
        choices.append(("__cancel__", "Cancel"))

        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        cl = ChoiceList(choices, id="stop-choice")
        panel.mount(cl)
        self._active_choices = cl
        self.call_after_refresh(cl.focus)
        self._update_footer(
            "เลือก instance ที่จะหยุด หรือ Stop all · /stop ชื่อ-profile",
            "↑↓ Enter confirm · Esc cancel",
        )

    def _show_delete_profile_picker(self) -> None:
        instances = list_instances()
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        body.mount(self._section_label("delete profile · saved configs"))

        if not instances:
            body.mount(Static("  [dim]ยังไม่มี profile ที่จะลบ[/dim]", classes="skill-line"))
            self.query_one("#choices-panel", Container).remove_children()
            self._active_choices = None
            self._update_footer("No profiles to delete.", "/instances · /help")
            return

        for inst in instances:
            has_yaml = inst.profile_path.is_file()
            detail = "yaml + output" if has_yaml and inst.status != "not_deployed" else (
                "yaml only" if has_yaml else "output only"
            )
            status_color = {"running": "yellow", "stopped": "dim", "not_deployed": "dim"}.get(
                inst.status, "white"
            )
            body.mount(
                Static(
                    f"  [#c9a227]{inst.profile_name}[/] "
                    f"[{status_color}]{inst.status}[/{status_color}] · {detail}",
                    classes="skill-line",
                )
            )

        choices: list[tuple[str, str]] = [
            ("__all__", f"Delete all ({len(instances)} profiles)"),
        ]
        for inst in instances:
            choices.append((inst.profile_name, f"Delete · {inst.profile_name}"))
        choices.append(("__cancel__", "Cancel"))

        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        cl = ChoiceList(choices, id="delete-profile-choice", multi=True)
        panel.mount(cl)
        self._active_choices = cl
        self.call_after_refresh(cl.focus)
        self._update_footer(
            "Space เลือกหลาย profile · Enter ยืนยัน · ขั้นถัดไปจะถาม volumes และ model cache",
            "↑↓ navigate · Esc cancel",
        )

    def _show_delete_volumes_picker(self) -> None:
        count = len(self._delete_targets)
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        body.mount(self._section_label(f"delete profile · {count} selected · docker volumes"))

        names = ", ".join(self._delete_targets[:5])
        if count > 5:
            names += f", … (+{count - 5})"
        body.mount(Static(f"  [#c9a227]{names}[/]", classes="skill-line"))
        body.mount(
            Static(
                "  [dim]Model cache อยู่ใน path ที่ตั้งไว้ต่อ profile (default: output/model-{provider}/)[/dim]",
                classes="skill-line",
            )
        )
        body.mount(
            Static(
                "  [dim]เลือกลบ Docker volumes ถ้ามี named volumes จาก compose เก่า[/dim]",
                classes="skill-line",
            )
        )

        choices: list[tuple[str, str]] = [
            ("volumes:yes", "ลบ Docker volumes ด้วย (compose down -v)"),
            ("volumes:no", "เก็บ Docker volumes ไว้"),
            ("__cancel__", "Cancel"),
        ]

        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        cl = ChoiceList(choices, id="delete-volumes-choice")
        panel.mount(cl)
        self._active_choices = cl
        self.call_after_refresh(cl.focus)
        self._update_footer("เลือกว่าจะลบ Docker volumes หรือไม่", "↑↓ Enter confirm · Esc cancel")

    def _show_delete_model_cache_picker(self) -> None:
        count = len(self._delete_targets)
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        body.mount(self._section_label(f"delete profile · {count} selected · model cache"))

        names = ", ".join(self._delete_targets[:5])
        if count > 5:
            names += f", … (+{count - 5})"
        body.mount(Static(f"  [#c9a227]{names}[/]", classes="skill-line"))
        body.mount(
            Static(
                "  [dim]ลบ model cache = ลบโฟลเดอร์โมเดลที่ดาวน์โหลดไว้ (รวม custom path นอก output)[/dim]",
                classes="skill-line",
            )
        )
        body.mount(
            Static(
                "  [dim]ถ้าเลือกเก็บ cache ไว้ จะลบแค่ profile YAML และไฟล์ deploy[/dim]",
                classes="skill-line",
            )
        )

        choices: list[tuple[str, str]] = [
            ("cache:yes", "ลบ model cache ด้วย"),
            ("cache:no", "เก็บ model cache ไว้"),
            ("__cancel__", "Cancel"),
        ]

        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        cl = ChoiceList(choices, id="delete-model-cache-choice")
        panel.mount(cl)
        self._active_choices = cl
        self.call_after_refresh(cl.focus)
        self._update_footer("เลือกว่าจะลบ model cache หรือไม่", "↑↓ Enter confirm · Esc cancel")

    def _begin_delete_profiles(self, *, label: str) -> None:
        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        self._active_choices = None
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        body.mount(self._section_label(label))
        self._mount_deploy_log(body)
        if self._editing_instance in self._delete_targets:
            self._editing_instance = None
        self._update_footer("Deleting profiles...", "please wait")
        self.run_worker(self._do_delete_profiles, name="delete-profiles", thread=True, exclusive=True)

    def _show_providers(self) -> None:
        panel = self.query_one("#choices-panel", Container)
        panel.remove_children()
        cl = ChoiceList(list(PROVIDER_CHOICES), id="provider-command")
        panel.mount(cl)
        self._active_choices = cl
        self.call_after_refresh(cl.focus)
        self._update_footer("เลือก provider (ollama / vllm)", "↑↓ Enter confirm · Esc cancel")

    def _handle_slash_command(self, raw: str) -> None:
        cmd, args = parse_command(raw)
        if not cmd:
            return
        resolved = self._command_aliases.get(cmd, cmd)
        self._clear_command_suggestions()
        self._command_bar_active = False
        self._set_command_mode(False)

        if resolved == "help":
            self._write_command_output(format_help_lines())
            self._update_footer("Slash command help", command_placeholder())
            return

        if resolved == "providers":
            self._show_providers()
            return

        if resolved == "instances":
            self._show_instances()
            return

        if resolved == "delete-profile":
            if args:
                self._delete_targets = args
                self._show_delete_volumes_picker()
                return
            self._show_delete_profile_picker()
            return

        if resolved == "doctor":
            self._go_to_step("doctor")
            return

        if resolved == "stop":
            if args:
                self._stop_target = args[0]
                self._remove_volumes_on_stop = False
                self._begin_stop(label=f"stop · {args[0]}")
                return
            self._show_stop_picker(remove_volumes=False)
            return

        if resolved == "delete-container":
            if args:
                self._stop_target = args[0]
                self._remove_volumes_on_stop = True
                self._begin_stop(label=f"delete · {args[0]}")
                return
            self._show_stop_picker(remove_volumes=True)
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
            self._show_stop_picker(remove_volumes=False)

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
                label = "All stacks stopped." if self._stop_target == "__all__" else "Docker stack stopped."
                self._update_footer(label, "q quit")
                if self._deploy_log is not None:
                    self._deploy_log.write(f"\n[bold green]✓ {label}[/bold green]")
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
            self._show_stop_picker(remove_volumes=False)
        else:
            self._next()

    @on(ChoiceList.Submitted, "#framework-choice")
    def on_framework(self, event: ChoiceList.Submitted) -> None:
        self.state.framework = Framework(event.selected_ids[0])
        self.state.image_tag = ""
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
        if not self.state.model_name:
            return
        try:
            self.query_one("#image-tag-input", Input).focus()
        except Exception:
            self._next()

    @on(Input.Submitted, "#image-tag-input")
    def on_image_submitted(self, event: Input.Submitted) -> None:
        if self.step != "model" or self.state.mode == ConfigMode.FULL:
            return
        self.state.image_tag = event.value.strip()
        if not self.state.model_name:
            return
        try:
            self.query_one("#model-cache-path-input", Input).focus()
        except Exception:
            self._next()

    @on(Input.Submitted, "#model-cache-path-input")
    def on_model_cache_path_submitted(self, event: Input.Submitted) -> None:
        if self.step != "model" or self.state.mode == ConfigMode.FULL:
            return
        self.state.model_cache_host_path_text = event.value.strip()
        if self.state.model_name:
            self._next()

    @on(Input.Submitted)
    def on_full_field_submitted(self, event: Input.Submitted) -> None:
        iid = event.input.id
        if iid in ("command-input", "model-input", "image-tag-input"):
            return
        fw = self.state.framework
        if self.step == "model" and self.state.mode == ConfigMode.FULL and fw:
            self._sync_model_fields()
            fields = model_fields(fw)
            if iid == fields[-1].id and self.state.model_name:
                self._next()
            else:
                self._focus_next_field(iid, [f.id for f in fields])
        elif self.step == "runtime" and fw:
            self._sync_runtime_fields()
            fields = runtime_fields(fw, self.state.host, self.state.profile_name)
            if iid == fields[-1].id:
                self._next()
            else:
                self._focus_next_field(iid, [f.id for f in fields])

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

    @on(ChoiceList.Submitted, "#stop-choice")
    def on_stop_choice(self, event: ChoiceList.Submitted) -> None:
        choice = event.selected_ids[0]
        if choice == "__cancel__":
            self._update_footer("Cancelled.", "/help · /instances")
            return
        self._stop_target = choice
        label = "delete · all" if choice == "__all__" and self._remove_volumes_on_stop else (
            "stop · all" if choice == "__all__" else (
                f"delete · {choice}" if self._remove_volumes_on_stop else f"stop · {choice}"
            )
        )
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()
        body.mount(self._section_label(label))
        self._mount_deploy_log(body)
        self._deploy_succeeded = False
        self._update_footer("Stopping Docker stack...", "please wait")
        self.run_worker(self._do_stop, name="stop", thread=True, exclusive=True)

    @on(ChoiceList.Submitted, "#instances-choice")
    def on_instances_choice(self, event: ChoiceList.Submitted) -> None:
        choice = event.selected_ids[0]
        if choice == "__new__":
            self._editing_instance = None
            self._go_to_step("framework")
            self._update_footer("เลือก framework สำหรับ profile ใหม่", "Esc back")
            return
        action, _, name = choice.partition(":")
        if action == "edit":
            if self._load_profile(name):
                self._go_to_step("summary")
                self._update_footer(
                    f"Editing profile [#c9a227]{name}[/] — แก้ไขแล้วเลือก Generate & deploy",
                    "/deploy เพื่อ update stack โดยไม่กระทบตัวอื่น",
                )
        elif action == "deploy":
            self._deploy_profile(name)
        elif action == "stop":
            self._stop_profile(name)
        elif action == "delete" and name == "__picker__":
            self._show_delete_profile_picker()

    @on(ChoiceList.Submitted, "#delete-profile-choice")
    def on_delete_profile_choice(self, event: ChoiceList.Submitted) -> None:
        selected = set(event.selected_ids)
        if not selected or "__cancel__" in selected:
            self._update_footer("Cancelled.", "/help · /instances")
            return

        if "__all__" in selected:
            self._delete_targets = [inst.profile_name for inst in list_instances()]
        else:
            self._delete_targets = sorted(selected - {"__all__", "__cancel__"})

        if not self._delete_targets:
            self._update_footer("No profiles selected.", "/delete-profile · /instances")
            return

        count = len(self._delete_targets)
        self._update_footer(
            f"Selected {count} profile(s) — choose volume removal next",
            "/delete-profile · Esc cancel",
        )
        self._show_delete_volumes_picker()

    @on(ChoiceList.Submitted, "#delete-volumes-choice")
    def on_delete_volumes_choice(self, event: ChoiceList.Submitted) -> None:
        choice = event.selected_ids[0]
        if choice == "__cancel__":
            self._update_footer("Cancelled.", "/help · /instances")
            return

        self._remove_volumes_on_delete = choice == "volumes:yes"
        self._show_delete_model_cache_picker()

    @on(ChoiceList.Submitted, "#delete-model-cache-choice")
    def on_delete_model_cache_choice(self, event: ChoiceList.Submitted) -> None:
        choice = event.selected_ids[0]
        if choice == "__cancel__":
            self._update_footer("Cancelled.", "/help · /instances")
            return

        self._remove_model_cache_on_delete = choice == "cache:yes"
        count = len(self._delete_targets)
        parts: list[str] = []
        if self._remove_volumes_on_delete:
            parts.append("volumes")
        if self._remove_model_cache_on_delete:
            parts.append("cache")
        suffix = f" + {' + '.join(parts)}" if parts else ""
        label = (
            f"delete profile · all{suffix}"
            if count > 1 and count == len(list_instances())
            else f"delete profile · {count} selected{suffix}"
        )
        self._begin_delete_profiles(label=label)

    @on(ChoiceList.Submitted, "#provider-command")
    def on_provider_command(self, event: ChoiceList.Submitted) -> None:
        fw = Framework(event.selected_ids[0])
        self.state.framework = fw
        self.state.image_tag = ""
        plugin = get_plugin(fw)
        if not self.state.model_name:
            self.state.model_name = plugin.meta.quick_defaults.get("model", "")
        self._go_to_step("model")
        self._update_footer(
            f"Provider: [#c9a227]{fw.value}[/] — type model name, Enter to continue.",
            "/providers · Esc back",
        )

    @on(CommandInput.Autocomplete)
    def on_command_autocomplete(self, event: CommandInput.Autocomplete) -> None:
        self.action_autocomplete_command()

    @on(CommandInput.Focused)
    def on_command_focused(self, event: CommandInput.Focused) -> None:
        self._command_bar_active = True
        self._set_command_mode(True)
        self.call_after_refresh(self._update_command_suggestions)

    @on(CommandInput.Blurred)
    def on_command_blurred(self, event: CommandInput.Blurred) -> None:
        def _maybe_exit() -> None:
            if not self._command_input_active():
                self._command_bar_active = False
            self._exit_command_mode_if_needed()

        self.call_after_refresh(_maybe_exit)

    @on(Input.Changed, "#command-input")
    def on_command_changed(self, event: Input.Changed) -> None:
        if self._command_input_sync:
            return
        self._command_suggest_index = 0
        self._update_command_suggestions()

    @on(Input.Submitted, "#command-input")
    def on_command_submitted(self, event: Input.Submitted) -> None:
        raw = resolve_submit_command(event.value, self._command_suggest_index).strip()
        event.input.value = ""
        self._command_bar_active = False
        self._clear_command_suggestions()
        self._set_command_mode(False)
        if not raw:
            return
        self._handle_slash_command(raw)


def run_tui(output_dir: Path = OUTPUT_DIR, initial_config: SetupConfig | None = None) -> None:
    app = LocalLLMSetupApp(output_dir=output_dir, initial_config=initial_config)
    app.run()
