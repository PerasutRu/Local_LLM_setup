"""Model source validation."""

from __future__ import annotations

import re
from pathlib import Path

from local_llm_setup.models.config import Framework, ValidationIssue

HF_REPO_RE = re.compile(r"^[\w\.\-]+/[\w\.\-]+$")
GGUF_RE = re.compile(r"\.gguf$", re.IGNORECASE)
OLLAMA_NAME_RE = re.compile(r"^[\w\.\-]+(/[\w\.\-]+)?(:[\w\.\-]+)?$")


def validate_model_name(framework: Framework, name: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    name = name.strip()

    if framework == Framework.OLLAMA:
        if not OLLAMA_NAME_RE.match(name):
            issues.append(
                ValidationIssue(
                    level="error",
                    message=(
                        f"Invalid Ollama model name: {name!r}. "
                        "Use format like 'llama3.2', 'llama3.2:latest', or 'namespace/model:tag'."
                    ),
                    field="model.name",
                )
            )
    elif framework in (Framework.VLLM, Framework.SGLANG):
        if not HF_REPO_RE.match(name):
            issues.append(
                ValidationIssue(
                    level="error",
                    message=f"Invalid Hugging Face repo id: {name!r}. Use format 'org/model-name'.",
                    field="model.name",
                )
            )
        if GGUF_RE.search(name):
            issues.append(
                ValidationIssue(
                    level="error",
                    message=f"{framework.value} does not support GGUF format directly. Use safetensors HF repo.",
                    field="model.name",
                )
            )
    elif framework == Framework.LLAMACPP:
        is_path = Path(name).exists() or name.startswith(("/", "./", "../"))
        is_url = name.startswith(("http://", "https://"))
        is_gguf = GGUF_RE.search(name)
        if not (is_path or is_url or is_gguf):
            issues.append(
                ValidationIssue(
                    level="error",
                    message="llama.cpp requires a GGUF file path or URL.",
                    field="model.name",
                )
            )
        if HF_REPO_RE.match(name) and not is_gguf:
            issues.append(
                ValidationIssue(
                    level="warn",
                    message="Hugging Face repo id without .gguf — provide full GGUF path or URL.",
                    field="model.name",
                )
            )
    return issues
