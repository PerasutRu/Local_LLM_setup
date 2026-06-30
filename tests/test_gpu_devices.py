"""GPU device detection and compose pinning."""

from __future__ import annotations

from unittest.mock import patch

from local_llm_setup.detect.host import detect_gpu_devices
from local_llm_setup.frameworks import get_plugin
from local_llm_setup.models.config import Framework, GpuDevice, SetupConfig
from local_llm_setup.renderers.compose import render_compose
from local_llm_setup.tui.full_config import gpu_device_ids_field, runtime_fields


def test_detect_gpu_devices_parses_nvidia_smi() -> None:
    smi_out = "0, NVIDIA A100-SXM4-40GB, 40960\n1, NVIDIA A100-SXM4-40GB, 40960\n"
    with patch("local_llm_setup.detect.host._run", return_value=(0, smi_out)):
        devices = detect_gpu_devices()

    assert devices == [
        GpuDevice(index="0", name="NVIDIA A100-SXM4-40GB", vram_gb=40.0),
        GpuDevice(index="1", name="NVIDIA A100-SXM4-40GB", vram_gb=40.0),
    ]


def test_runtime_fields_include_gpu_device_ids_for_all_providers() -> None:
    for fw in Framework:
        field_ids = [spec.id for spec in runtime_fields(fw)]
        assert "gpu-device-ids-input" in field_ids


def test_gpu_device_ids_field_shows_detected_gpus() -> None:
    from local_llm_setup.models.config import GPUVendor, HostInfo

    host = HostInfo(
        gpu_vendor=GPUVendor.NVIDIA,
        gpu_devices=[
            GpuDevice(index="0", name="NVIDIA A100-SXM4-40GB", vram_gb=40.0),
            GpuDevice(index="1", name="NVIDIA A100-SXM4-40GB", vram_gb=40.0),
        ],
    )
    spec = gpu_device_ids_field(host)

    assert spec.placeholder == "0"
    assert "GPU 0: NVIDIA A100-SXM4-40GB" in spec.hint
    assert "GPU 1: NVIDIA A100-SXM4-40GB" in spec.hint


def test_ollama_compose_pins_gpu_device_ids() -> None:
    plugin = get_plugin(Framework.OLLAMA)
    fc = plugin.default_config("llama3.2", mode="full")
    fc.gpu_device_ids = ["0", "1"]
    text = render_compose(SetupConfig(frameworks=[fc]))

    assert 'device_ids: ["0", "1"]' in text or 'device_ids:\n' in text
    assert "NVIDIA_VISIBLE_DEVICES" in text
    assert "0,1" in text


def test_sglang_compose_pins_gpu_device_ids() -> None:
    plugin = get_plugin(Framework.SGLANG)
    fc = plugin.default_config("meta-llama/Meta-Llama-3-8B-Instruct", mode="full")
    fc.gpu_device_ids = ["2"]
    text = render_compose(SetupConfig(frameworks=[fc]))

    assert "device_ids" in text
    assert "NVIDIA_VISIBLE_DEVICES" in text
    assert "2" in text


def test_llamacpp_compose_pins_gpu_device_ids() -> None:
    plugin = get_plugin(Framework.LLAMACPP)
    fc = plugin.default_config("/models/model.gguf", mode="full")
    fc.gpu_device_ids = ["0"]
    text = render_compose(SetupConfig(frameworks=[fc]))

    assert "device_ids" in text
    assert "NVIDIA_VISIBLE_DEVICES" in text
