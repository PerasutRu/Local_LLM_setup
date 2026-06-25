"""Generate deployment artifacts."""

from __future__ import annotations

from pathlib import Path

from local_llm_setup.frameworks import validate_setup
from local_llm_setup.models.config import GeneratedOutput, SetupConfig
from local_llm_setup.renderers.compose import render_compose, render_env, render_run_commands
from local_llm_setup.renderers.nginx import render_api_keys_map, render_nginx_conf


def generate(config: SetupConfig, dry_run: bool = False) -> GeneratedOutput:
    issues = validate_setup(config.frameworks, config.host)
    errors = [i for i in issues if i.level == "error"]
    warnings = [i.message for i in issues if i.level in ("warn", "info")]

    if errors:
        raise ValueError("Validation failed:\n" + "\n".join(f"  - {e.message}" for e in errors))

    compose_yaml = render_compose(config)
    env_file = render_env(config)
    nginx_conf = render_nginx_conf(config) if config.nginx.enabled else None
    api_keys_map = (
        render_api_keys_map(config)
        if config.nginx.enabled and config.nginx.api_key_auth and config.nginx.api_keys
        else None
    )
    run_commands = render_run_commands(config)

    if not dry_run:
        out = Path(config.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "docker-compose.yaml").write_text(compose_yaml, encoding="utf-8")
        (out / ".env").write_text(env_file, encoding="utf-8")
        if nginx_conf:
            (out / "nginx.conf").write_text(nginx_conf, encoding="utf-8")
        if api_keys_map:
            (out / "api_keys.map").write_text(api_keys_map, encoding="utf-8")
        (out / "RUN.md").write_text(
            "# Run commands\n\n```bash\n" + "\n".join(run_commands) + "\n```\n",
            encoding="utf-8",
        )

    return GeneratedOutput(
        compose_yaml=compose_yaml,
        env_file=env_file,
        nginx_conf=nginx_conf,
        api_keys_map=api_keys_map,
        run_commands=run_commands,
        warnings=warnings,
    )
