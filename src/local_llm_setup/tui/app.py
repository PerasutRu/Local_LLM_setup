"""Textual TUI wizard."""

from __future__ import annotations

import secrets
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, RichLog, Static

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
        self.nginx_port: int = 80
        self.nginx_api_keys: bool = False
        self.bind_public: bool = False
        self.hf_token: str = ""

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
        fc.bind_host = "0.0.0.0" if self.bind_public else "127.0.0.1"

        nginx = NginxConfig(
            enabled=self.nginx_enabled,
            listen_port=self.nginx_port,
            upstream_port=fc.port,
            api_key_auth=self.nginx_api_keys,
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


class LocalLLMSetupApp(App):
    """Local LLM Setup TUI wizard."""

    TITLE = "Local LLM Setup"
    SUB_TITLE = "Host local LLMs with Docker"

    CSS = """
    Screen {
        background: $surface;
    }
    #content {
        height: 1fr;
    }
    #doctor-log {
        height: 1fr;
        border: solid $primary;
    }
    .info {
        color: $text-muted;
        margin-bottom: 1;
    }
    Input {
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "back", "Back"),
    ]

    def __init__(self, output_dir: Path = Path("./output"), initial_config: SetupConfig | None = None) -> None:
        super().__init__()
        self.state = WizardState(output_dir, initial_config)
        self._step_idx = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="content"):
            yield Static(id="step-label", classes="info")
            yield VerticalScroll(id="step-body")
        yield Footer()

    def on_mount(self) -> None:
        self._show_step()

    @property
    def step(self) -> str:
        return STEPS[self._step_idx]

    def _set_step_label(self, text: str) -> None:
        self.query_one("#step-label", Static).update(text)

    def _clear_body(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.remove_children()

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

    def _show_step(self) -> None:
        self._clear_body()
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
        self._set_step_label(f"Step {self._step_idx + 1}/{len(STEPS)}: {self.step}")
        handlers[self.step]()

    def _step_doctor(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        log = RichLog(id="doctor-log", highlight=True, markup=True)
        body.mount(log)

        host = self.state.host
        log.write(f"[bold]OS:[/bold] {host.os_type.value} {host.arch}")
        if host.is_wsl:
            log.write("[dim]WSL detected[/dim]")
        if host.gpu_name:
            log.write(f"[bold]GPU:[/bold] {host.gpu_name} ({host.vram_gb or '?'} GB)")
        if host.ram_gb:
            log.write(f"[bold]RAM:[/bold] {host.ram_gb} GB")

        for check in host.checks:
            color = {"ok": "green", "warn": "yellow", "fail": "red"}.get(check.status.value, "white")
            log.write(f"[{color}]{check.status.value.upper()}[/{color}] {check.name}: {check.message}")
            if check.hint:
                log.write(f"  [dim]hint: {check.hint}[/dim]")

        choices = ChoiceList([("continue", "Continue →")], id="doctor-continue")
        body.mount(choices)
        choices.focus()

    def _step_framework(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(Static("Select inference framework:"))
        choices = [
            (p.meta.framework.value, f"{p.meta.display_name} — {p.meta.description}")
            for p in list_frameworks()
        ]
        cl = ChoiceList(choices, id="framework-choice")
        body.mount(cl)
        cl.focus()

    def _step_mode(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(Static("Configuration mode:"))
        cl = ChoiceList(
            [
                ("quick", "Quick — sensible defaults"),
                ("full", "Full — all options in following steps"),
            ],
            id="mode-choice",
        )
        body.mount(cl)
        cl.focus()

    def _step_model(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        fw = self.state.framework
        plugin = get_plugin(fw) if fw else None
        hint = "Ollama model name (e.g. llama3.2)"
        if fw == Framework.VLLM or fw == Framework.SGLANG:
            hint = "Hugging Face repo id (e.g. meta-llama/Meta-Llama-3-8B-Instruct)"
        elif fw == Framework.LLAMACPP:
            hint = "GGUF path or URL (e.g. /models/model.gguf)"

        default = plugin.meta.quick_defaults.get("model", "") if plugin else ""
        body.mount(Static(hint))
        inp = Input(value=self.state.model_name or default, placeholder=hint, id="model-input")
        body.mount(inp)

        if self.state.mode == ConfigMode.FULL:
            body.mount(Static("Context length:"))
            ctx = Input(value=str(self.state.context_length), id="ctx-input")
            body.mount(ctx)
            if fw in (Framework.VLLM, Framework.SGLANG):
                body.mount(Static("Tensor parallel size:"))
                tp = Input(value=str(self.state.tensor_parallel), id="tp-input")
                body.mount(tp)
            if fw in (Framework.VLLM, Framework.SGLANG):
                body.mount(Static("Hugging Face token (optional, for gated models):"))
                body.mount(Input(password=True, placeholder="hf_...", id="hf-token-input"))

        body.mount(Static("Press Enter to continue"))
        inp.focus()

    def _step_capabilities(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        fw = self.state.framework
        plugin = get_plugin(fw) if fw else None
        body.mount(Static("Select capabilities (Space to toggle, Enter to confirm):"))

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

        cl = ChoiceList(opts, multi=True, id="cap-choice")
        body.mount(cl)

        if plugin and plugin.meta.supports_mtp:
            body.mount(Static("MTP drafter model (if MTP selected):"))
            body.mount(Input(placeholder="org/drafter-model", id="drafter-input"))

        body.mount(Static("Expose API on 0.0.0.0 (public)? Space on choice below:"))
        pub = ChoiceList([("public", "Bind to 0.0.0.0 (all interfaces)")], id="public-choice")
        body.mount(pub)
        cl.focus()

    def _step_nginx(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        body.mount(Static("Enable nginx reverse proxy? (↑/↓ Space to select, configure below)"))
        body.mount(
            ChoiceList(
                [
                    ("yes", "Yes — generate nginx.conf"),
                    ("no", "No — connect directly to framework port"),
                ],
                id="nginx-choice",
            )
        )
        body.mount(Static("nginx listen port (if enabled):"))
        body.mount(Input(value=str(self.state.nginx_port), id="nginx-port"))
        body.mount(Static("API key authentication via api_keys.map?"))
        body.mount(
            ChoiceList(
                [("yes", "Yes — generate api_keys.map"), ("no", "No API key auth")],
                id="apikey-choice",
            )
        )
        cont = ChoiceList([("continue", "Continue →")], id="nginx-continue")
        body.mount(cont)
        cont.focus()

    def _step_summary(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        try:
            config = self.state.to_config()
            issues = validate_setup(config.frameworks, config.host)
        except ValueError as exc:
            body.mount(Static(f"Config error: {exc}"))
            return

        log = RichLog(highlight=True, markup=True)
        body.mount(log)
        fc = config.frameworks[0]
        log.write(f"[bold]Framework:[/bold] {fc.framework.value}")
        log.write(f"[bold]Model:[/bold] {fc.model.name}")
        log.write(f"[bold]Mode:[/bold] {fc.mode.value}")
        log.write(f"[bold]Port:[/bold] {fc.bind_host}:{fc.port}")
        log.write(f"[bold]Capabilities:[/bold] vision={fc.capabilities.vision} tools={fc.capabilities.tool_calling} mtp={fc.capabilities.mtp}")
        log.write(f"[bold]Nginx:[/bold] {config.nginx.enabled}")
        log.write(f"[bold]Output:[/bold] {config.output_dir}")

        for issue in issues:
            color = "red" if issue.level == "error" else "yellow"
            log.write(f"[{color}]{issue.level.upper()}:[/{color}] {issue.message}")

        errors = [i for i in issues if i.level == "error"]
        if errors:
            body.mount(Static("Fix errors before generating. Press Esc to go back."))
            return

        cl = ChoiceList(
            [("generate", "Generate docker-compose.yaml and configs")],
            id="generate-choice",
        )
        body.mount(cl)
        cl.focus()

    def _step_done(self) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        log = RichLog(highlight=True, markup=True)
        body.mount(log)
        try:
            config = self.state.to_config()
            result = generate(config)
            profile_path = save_profile(config)
            log.write(f"[green]Generated in {config.output_dir.resolve()}[/green]")
            log.write(f"[green]Profile saved: {profile_path}[/green]")
            for w in result.warnings:
                log.write(f"[yellow]Warning:[/yellow] {w}")
            log.write("\n[bold]Run commands:[/bold]")
            for cmd in result.run_commands:
                log.write(f"  {cmd}")
            if result.api_keys_map and config.nginx.api_keys:
                log.write("\n[bold]API key:[/bold]")
                for k in config.nginx.api_keys:
                    log.write(f"  {k.key}  ({k.label})")
        except Exception as exc:
            log.write(f"[red]Error:[/red] {exc}")

    @on(ChoiceList.Submitted, "#doctor-continue")
    def on_doctor_continue(self, _: ChoiceList.Submitted) -> None:
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
            ctx_inp = body.query_one("#ctx-input", Input)
            self.state.context_length = int(ctx_inp.value or "8192")
        except Exception:
            pass
        try:
            tp_inp = body.query_one("#tp-input", Input)
            self.state.tensor_parallel = int(tp_inp.value or "1")
        except Exception:
            pass
        try:
            hf_inp = body.query_one("#hf-token-input", Input)
            if hf_inp.value:
                self.state.hf_token = hf_inp.value
        except Exception:
            pass
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
        body = self.query_one("#step-body", VerticalScroll)
        try:
            drafter = body.query_one("#drafter-input", Input)
            if self.state.capabilities.mtp:
                self.state.capabilities.mtp_drafter_model = drafter.value or None
        except Exception:
            pass
        try:
            pub = body.query_one("#public-choice", ChoiceList)
            self.state.bind_public = "public" in pub.selected_ids()
        except Exception:
            pass
        self._next()

    @on(ChoiceList.Submitted, "#nginx-continue")
    def on_nginx(self, _: ChoiceList.Submitted) -> None:
        body = self.query_one("#step-body", VerticalScroll)
        try:
            ngx = body.query_one("#nginx-choice", ChoiceList)
            self.state.nginx_enabled = ngx.selected_ids()[0] == "yes"
        except Exception:
            pass
        try:
            port_inp = body.query_one("#nginx-port", Input)
            self.state.nginx_port = int(port_inp.value or "80")
        except Exception:
            pass
        try:
            ak = body.query_one("#apikey-choice", ChoiceList)
            self.state.nginx_api_keys = self.state.nginx_enabled and "yes" in ak.selected_ids()
        except Exception:
            pass
        self._next()

    @on(ChoiceList.Submitted, "#generate-choice")
    def on_generate(self, _: ChoiceList.Submitted) -> None:
        self._next()


def run_tui(output_dir: Path = Path("./output"), initial_config: SetupConfig | None = None) -> None:
    app = LocalLLMSetupApp(output_dir=output_dir, initial_config=initial_config)
    app.run()
