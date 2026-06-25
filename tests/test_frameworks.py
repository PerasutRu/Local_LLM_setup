"""Tests for framework validation."""

from __future__ import annotations

from local_llm_setup.frameworks import get_plugin, validate_setup
from local_llm_setup.models.config import (
    Capabilities,
    Framework,
    FrameworkConfig,
    GPUVendor,
    HostInfo,
    ModelConfig,
    OSType,
)
from local_llm_setup.models.validation import validate_model_name


def test_ollama_model_validation_ok():
    issues = validate_model_name(Framework.OLLAMA, "llama3.2:latest")
    assert not any(i.level == "error" for i in issues)


def test_ollama_model_validation_namespace():
    issues = validate_model_name(Framework.OLLAMA, "dommage/gemma4-e4b-qat:latest")
    assert not any(i.level == "error" for i in issues)


def test_ollama_model_validation_rejects_invalid():
    issues = validate_model_name(Framework.OLLAMA, "bad/name/extra:tag")
    assert any(i.level == "error" for i in issues)


def test_vllm_rejects_gguf():
    issues = validate_model_name(Framework.VLLM, "user/model.gguf")
    assert any(i.level == "error" for i in issues)


def test_vllm_requires_gpu():
    plugin = get_plugin(Framework.VLLM)
    fc = plugin.default_config("meta-llama/Meta-Llama-3-8B-Instruct")
    host = HostInfo(os_type=OSType.LINUX, gpu_vendor=GPUVendor.NONE)
    issues = plugin.validate(fc, host)
    assert any("GPU" in i.message for i in issues)


def test_mtp_requires_drafter():
    plugin = get_plugin(Framework.VLLM)
    fc = plugin.default_config()
    fc.capabilities = Capabilities(text=True, mtp=True)
    issues = plugin.validate(fc, None)
    assert any("drafter" in i.message.lower() for i in issues)


def test_port_conflict():
    fc1 = FrameworkConfig(
        framework=Framework.OLLAMA,
        model=ModelConfig(name="llama3.2"),
        port=9090,
    )
    fc2 = FrameworkConfig(
        framework=Framework.VLLM,
        model=ModelConfig(name="meta-llama/Meta-Llama-3-8B-Instruct"),
        port=9090,
    )
    issues = validate_setup([fc1, fc2], None)
    assert any("Port 9090" in i.message for i in issues)
