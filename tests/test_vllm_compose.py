"""vLLM compose generation — production-style configs (e.g. Gemma 4)."""

from __future__ import annotations

from local_llm_setup.frameworks import get_plugin
from local_llm_setup.models.config import (
    Capabilities,
    Framework,
    ModelConfig,
    SetupConfig,
    VllmServeOptions,
)
from local_llm_setup.renderers.compose import render_compose


def _gemma4_setup() -> SetupConfig:
    plugin = get_plugin(Framework.VLLM)
    fc = plugin.default_config("cyankiwi/gemma-4-E4B-it-AWQ-INT4", mode="full")
    fc.model = ModelConfig(
        name="cyankiwi/gemma-4-E4B-it-AWQ-INT4",
        context_length=80000,
        tensor_parallel=1,
    )
    fc.port = 8000
    fc.publish_port = 8002
    fc.bind_host = "0.0.0.0"
    fc.ipc = "host"
    fc.gpu_device_ids = ["0"]
    fc.extra_volumes = ["/nas/nt_hack/huggingface:/root/.cache/huggingface"]
    fc.extra_env = {
        "HF_HOME": "/root/.cache/huggingface",
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    }
    fc.capabilities = Capabilities(text=True, tool_calling=True, vision=True, audio=True)
    fc.vllm = VllmServeOptions(
        gpu_memory_utilization=0.3,
        max_num_seqs=1,
        trust_remote_code=True,
        enable_prefix_caching=True,
        tool_call_parser="gemma4",
        reasoning_parser="gemma4",
        kv_cache_dtype="auto",
        limit_mm_per_prompt='{"image": 4, "audio": 1}',
        install_audio_extras=True,
    )
    return SetupConfig(frameworks=[fc])


def test_vllm_gemma4_style_compose() -> None:
    text = render_compose(_gemma4_setup())

    assert "vllm/vllm-openai:latest" in text
    assert "0.0.0.0:8002:8000" in text
    assert 'ipc: host' in text
    assert "/nas/nt_hack/huggingface:/root/.cache/huggingface" in text
    assert "device_ids" in text
    assert "NVIDIA_VISIBLE_DEVICES" in text
    assert "/bin/bash" in text and "vllm[audio]" in text
    assert "cyankiwi/gemma-4-E4B-it-AWQ-INT4" in text
    assert "--gpu-memory-utilization" in text
    assert "--max-model-len" in text
    assert "80000" in text
    assert "--enable-auto-tool-choice" in text
    assert "--tool-call-parser" in text
    assert "gemma4" in text
    assert "--reasoning-parser" in text
    assert "--enable-prefix-caching" in text
    assert "--trust-remote-code" in text
    assert "--limit-mm-per-prompt" in text
    assert "PYTORCH_CUDA_ALLOC_CONF" in text


def test_vllm_default_model_cache_mount() -> None:
    plugin = get_plugin(Framework.VLLM)
    fc = plugin.default_config("meta-llama/Meta-Llama-3-8B-Instruct")
    text = render_compose(SetupConfig(frameworks=[fc]))

    assert "./model-vllm:/root/.cache/huggingface" in text
    assert "HF_HOME" in text


def test_vllm_serve_entrypoint_without_audio() -> None:
    plugin = get_plugin(Framework.VLLM)
    fc = plugin.default_config("meta-llama/Meta-Llama-3-8B-Instruct")
    fc.capabilities = Capabilities(text=True, tool_calling=True)
    text = render_compose(SetupConfig(frameworks=[fc]))

    assert "entrypoint:" in text and "serve" in text
    assert "meta-llama/Meta-Llama-3-8B-Instruct" in text
    assert "vllm[audio]" not in text
