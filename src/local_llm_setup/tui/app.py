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
from textual.widgets import Input, RichLog, Static
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
)
from local_llm_setup.profiles import save_profile
from local_llm_setup.renderers import generate
from local_llm_setup.runner import DeployResult, deploy, run_curl_tests, stop_stack
from local_llm_setup.urls import build_access_urls, format_access_lines
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
        self.capabilities = Capabilities(text=True)
        self.nginx_enabled: bool = False
        self.nginx_port: int = 8080
        self.nginx_api_keys: bool = False
        self.bind_public: bool = False
        self.hf_token: str = ""
        self.auto_run: bool = True

        if initial and initial.frameworks:
            fc = initial.frameworks[0]
            self.framework = fc.framework
            self.mode = fc.mode
            self.model_name = fc.model.name
            self.context_length = fc.model.context_length
            self.tensor_parallel = fc.model.tensor_parallel
            self.capabilities = fc.capabilities
            self.nginx_enabled = initial.nginx.enabled
            self.nginx_port = initial.nginx.listen_port
            self.nginx_api_keys = initial.nginx.api_key_auth
            self.hf_token = initial.hf_token or ""

    def to_config(self) -> SetupConfig:
        if not self.framework:
            raise ValueError("Framework not selected")
        plugin = get_plugin(self.framework)
        fc = plugin.default_config(self.model_name, self.mode.value)
        fc.model = ModelConfig(
            name=self.model_name,
            context_length=self.context_length,
            tensor_parallel=self.tensor_parallel,
        )
        fc.capabilities = self.capabilities
        if self.nginx_enabled:
            # Expose only via nginx on 0.0.0.0; keep framework internal
            fc.bind_host = "127.0.0.1"
        else:
            fc.bind_host = "0.0.0.0" if self.bind_public else "127.0.0.1"

        nginx = NginxConfig(
            enabled=self.nginx_enabled,
            listen_port=self.nginx_port,
            upstream_port=fc.port,
            api_key_auth=self.nginx_api_keys,
            bind_host="0.0.0.0" if self.nginx_enabled else "127.0.0.1",
        )
        if self.nginx_api_keys:
            nginx.api_keys = [ApiKeyEntry(key=secrets.token_urlsafe(32), label="default")]

        return SetupConfig(
            output_dir=self.output_dir,
            host=self.host,
            frameworks=[fc],
            nginx=nginx,
            hf_token=self.hf_token or None,
        )


STEPS = [
    "doctor",
    "framework",
    "mode",
    "model",
    "capabilities",
    "nginx",
    "summary",
    "done",
]

STEP_TITLES = {
    "doctor": "Host Doctor",
    "framework": "Available Frameworks",
    "mode": "Configuration Mode",
    "model": "Model Setup",
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

    def __init__(self, output_dir: Path = Path("./output"), initial_config: SetupConfig | None = None) -> None:
        super().__init__()
        self.state = WizardState(output_dir, initial_config)
        self._step_idx = 0
        self._active_choices: ChoiceList | None = None
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._deploy_log: RichLog | None = None
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
        return STEPS[self._step_idx]

    def _progress_bar(self) -> str:
        total = len(STEPS)
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
        self.query_one("#welcome", Static).update(welcome)
        self.query_one("#status-bar", Static).update(
            f"⚡ [#c9a227]{step_name}[/] · step {self._step_idx + 1}/{len(STEPS)} "
            f"[{self._progress_bar()}]"
        )
        self.query_one("#hint-bar", Static).update(hint)

    def _set_step_title(self, title: str) -> None:
        self.query_one("#step-title", Static).update(title)

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

    def _skill_line(self, key: str, val: str) -> Static:
        return Static(f"[#c9a227]{key}:[/] {val}", classes="skill-line")

    def _next(self) -> None:
        if self._step_idx < len(STEPS) - 1:
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
            "capabilities": self._step_capabilities,
            "nginx": self._step_nginx,
            "summary": self._step_summary,
            "done": self._step_done,
        }
        self._set_step_title(STEP_TITLES[self.step])
        handlers[self.step]()

    def _step_doctor(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(Static("Doctor checks · Docker, GPU, CUDA, nginx", classes="section-label"))

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
        body.mount(Static("frameworks · inference backends", classes="section-label"))
        for p in list_frameworks():
            body.mount(self._skill_line(p.meta.framework.value, p.meta.description))

        choices = [(p.meta.framework.value, p.meta.display_name) for p in list_frameworks()]
        self._mount_choices(choices, id="framework-choice")
        self._update_footer("Select a framework to host your local LLM.", "↑↓ j/k navigate · Enter confirm")

    def _step_mode(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(Static("config · setup depth", classes="section-label"))
        body.mount(self._skill_line("quick", "Sensible defaults — fastest path"))
        body.mount(self._skill_line("full", "All options — context, ports, tokens"))

        self._mount_choices(
            [("quick", "Quick — sensible defaults"), ("full", "Full — all options")],
            id="mode-choice",
        )
        self._update_footer("Choose quick or full configuration.", "↑↓ j/k navigate · Enter confirm")

    def _step_model(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        fw = self.state.framework
        plugin = get_plugin(fw) if fw else None
        hint = "Ollama model name (e.g. llama3.2)"
        if fw in (Framework.VLLM, Framework.SGLANG):
            hint = "Hugging Face repo id (e.g. meta-llama/Meta-Llama-3-8B-Instruct)"
        elif fw == Framework.LLAMACPP:
            hint = "GGUF path or URL (e.g. /models/model.gguf)"

        default = plugin.meta.quick_defaults.get("model", "") if plugin else ""
        body.mount(Static("model · name and parameters", classes="section-label"))
        body.mount(Static(f"  {hint}", classes="skill-line"))
        inp = Input(value=self.state.model_name or default, placeholder=hint, id="model-input")
        body.mount(inp)

        if self.state.mode == ConfigMode.FULL:
            body.mount(Static("context_length:", classes="section-label"))
            body.mount(Input(value=str(self.state.context_length), id="ctx-input"))
            if fw in (Framework.VLLM, Framework.SGLANG):
                body.mount(Static("tensor_parallel:", classes="section-label"))
                body.mount(Input(value=str(self.state.tensor_parallel), id="tp-input"))
                body.mount(Static("hf_token: (optional, gated models)", classes="section-label"))
                body.mount(Input(password=True, placeholder="hf_...", id="hf-token-input"))

        self._update_footer("Type model name, then press Enter to continue.", "Tab between fields · Enter submit")
        self.call_after_refresh(inp.focus)

    def _step_capabilities(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        fw = self.state.framework
        plugin = get_plugin(fw) if fw else None
        body.mount(Static("capabilities · model features", classes="section-label"))

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
        opts.append(("public", "Bind to 0.0.0.0 (expose publicly)"))

        for cid, label in opts:
            body.mount(self._skill_line(cid, label))

        if plugin and plugin.meta.supports_mtp:
            body.mount(Static("mtp_drafter: (if MTP enabled)", classes="section-label"))
            body.mount(Input(placeholder="org/drafter-model", id="drafter-input"))

        self._mount_choices(opts, multi=True, id="cap-choice")
        self._update_footer("Space toggles options · Enter confirms.", "↑↓ j/k navigate · Tab next list")

    def _step_nginx(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(Static("nginx · reverse proxy", classes="section-label"))
        body.mount(self._skill_line("no", "Direct to framework port"))
        body.mount(self._skill_line("yes_nokey", "nginx.conf without API keys"))
        body.mount(self._skill_line("yes_key", "nginx.conf + api_keys.map"))
        body.mount(Static("listen_port:", classes="section-label"))
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
            body.mount(Static(f"[red]Config error: {exc}[/red]"))
            self._update_footer("Fix errors and press Esc to go back.", "")
            return

        fc = config.frameworks[0]
        body.mount(self._skill_line("framework", fc.framework.value))
        body.mount(self._skill_line("model", fc.model.name))
        body.mount(self._skill_line("mode", fc.mode.value))
        body.mount(self._skill_line("port", f"{fc.bind_host}:{fc.port}"))
        body.mount(
            self._skill_line(
                "capabilities",
                f"vision={fc.capabilities.vision} tools={fc.capabilities.tool_calling} mtp={fc.capabilities.mtp}",
            )
        )
        body.mount(self._skill_line("nginx", str(config.nginx.enabled)))
        body.mount(self._skill_line("output", str(config.output_dir)))

        for issue in issues:
            color = "red" if issue.level == "error" else "yellow"
            body.mount(Static(f"  [{color}]{issue.level.upper()}:[/{color}] {issue.message}", classes="skill-line"))

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
                body.mount(Static("deploy · docker compose", classes="section-label"))
                deploy_log = RichLog(highlight=True, markup=True, id="deploy-log", wrap=True)
                body.mount(deploy_log)
                self._deploy_log = deploy_log
                self._update_footer("Starting Docker containers...", "please wait")
                self.run_worker(
                    partial(self._do_deploy, config),
                    name="deploy",
                    thread=True,
                    exclusive=True,
                )
            else:
                body.mount(Static("run:", classes="section-label"))
                for cmd in result.run_commands:
                    body.mount(Static(f"  {cmd}", classes="skill-line"))
                urls = build_access_urls(config)
                body.mount(Static("access:", classes="section-label"))
                for line in format_access_lines(urls, markup=False):
                    if line.strip():
                        body.mount(Static(f"  {line.strip()}", classes="skill-line"))
                self._update_footer(f"Ready · {urls.primary_url}", "s stop · /test · /delete-container · q quit")

            if result.api_keys_map and config.nginx.api_keys:
                body.mount(Static("api_keys:", classes="section-label"))
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

    def _ensure_deploy_log(self) -> RichLog:
        if self._deploy_log is not None:
            return self._deploy_log
        body = self.query_one("#step-body", VerticalScroll)
        deploy_log = RichLog(highlight=True, markup=True, id="deploy-log", wrap=True)
        body.mount(deploy_log)
        self._deploy_log = deploy_log
        return deploy_log

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
        if step_name in STEPS:
            self._step_idx = STEPS.index(step_name)
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
            body.mount(Static("deploy · docker compose", classes="section-label"))
            deploy_log = RichLog(highlight=True, markup=True, id="deploy-log", wrap=True)
            body.mount(deploy_log)
            self._deploy_log = deploy_log
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
        body.mount(Static(label, classes="section-label"))
        deploy_log = RichLog(highlight=True, markup=True, id="deploy-log", wrap=True)
        body.mount(deploy_log)
        self._deploy_log = deploy_log
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
            if result.success:
                self._update_footer("Curl tests passed.", "s stop · /test · q quit")
            else:
                self._update_footer(f"Curl test failed: {result.error or 'unknown error'}", "/test · q quit")
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
            self._update_footer(f"Running · {footer}", "s stop · /test · /delete-container · q quit")
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
        self.state.model_name = event.value.strip()
        body = self.query_one("#step-body", VerticalScroll)
        try:
            self.state.context_length = int(body.query_one("#ctx-input", Input).value or "8192")
        except Exception:
            pass
        try:
            self.state.tensor_parallel = int(body.query_one("#tp-input", Input).value or "1")
        except Exception:
            pass
        try:
            hf = body.query_one("#hf-token-input", Input)
            if hf.value:
                self.state.hf_token = hf.value
        except Exception:
            pass
        if self.state.model_name:
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
        body = self.query_one("#step-body", VerticalScroll)
        try:
            self.state.nginx_port = int(body.query_one("#nginx-port", Input).value or "8080")
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


def run_tui(output_dir: Path = Path("./output"), initial_config: SetupConfig | None = None) -> None:
    app = LocalLLMSetupApp(output_dir=output_dir, initial_config=initial_config)
    app.run()
