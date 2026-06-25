"""Full-mode wizard config building."""

from pathlib import Path

from local_llm_setup.models.config import ConfigMode, Framework
from local_llm_setup.tui.app import WizardState
from local_llm_setup.tui.full_config import model_fields, runtime_fields


def test_full_mode_vllm_builds_all_fields() -> None:
    state = WizardState(Path("./output"))
    state.framework = Framework.VLLM
    state.mode = ConfigMode.FULL
    state.model_name = "meta-llama/Meta-Llama-3-8B-Instruct"
    state.context_length = 16384
    state.tensor_parallel = 2
    state.quantization = "awq"
    state.hf_token_env = "HF_TOKEN"
    state.hf_token = "hf_secret"
    state.port = 8001
    state.bind_host_override = "127.0.0.1"
    state.image_tag = "vllm/vllm-openai:latest"
    state.shm_size = "32gb"
    state.gpu_count = 2
    state.extra_env_text = "FOO=bar\n# comment\nBAZ=qux"
    state.extra_args_text = "--dtype auto"
    state.profile_name = "myprofile"
    state.nginx_enabled = True
    state.nginx_port = 9090
    state.nginx_server_name = "llm.local"
    state.nginx_client_max_body_size = "100m"
    state.nginx_proxy_read_timeout = "900s"
    state.nginx_enable_cors = False
    state.nginx_tunnel_enabled = False

    config = state.build_config()
    fc = config.frameworks[0]

    assert fc.model.quantization == "awq"
    assert fc.model.context_length == 16384
    assert fc.port == 8001
    assert fc.image_tag == "vllm/vllm-openai:latest"
    assert fc.shm_size == "32gb"
    assert fc.gpu_count == 2
    assert fc.extra_env == {"FOO": "bar", "BAZ": "qux"}
    assert fc.extra_args == ["--dtype", "auto"]
    assert config.profile_name == "myprofile"
    assert config.nginx.listen_port == 9090
    assert config.nginx.server_name == "llm.local"
    assert config.nginx.enable_cors is False
    assert config.nginx.tunnel_enabled is False


def test_full_mode_ollama_env_merged() -> None:
    state = WizardState(Path("./output"))
    state.framework = Framework.OLLAMA
    state.mode = ConfigMode.FULL
    state.model_name = "llama3.2"
    state.ollama_parallel = "4"
    state.ollama_host = "0.0.0.0:11434"
    state.extra_env_text = "CUSTOM=1"

    fc = state.build_config().frameworks[0]
    assert fc.extra_env["OLLAMA_NUM_PARALLEL"] == "4"
    assert fc.extra_env["OLLAMA_HOST"] == "0.0.0.0:11434"
    assert fc.extra_env["CUSTOM"] == "1"


def test_full_mode_llamacpp_ngl_in_extra_args() -> None:
    state = WizardState(Path("./output"))
    state.framework = Framework.LLAMACPP
    state.mode = ConfigMode.FULL
    state.model_name = "/models/model.gguf"
    state.llama_ngl = "35"
    state.extra_args_text = "--threads 8"

    fc = state.build_config().frameworks[0]
    assert fc.extra_args[:2] == ["--n-gpu-layers", "35"]
    assert "--threads" in fc.extra_args


def test_field_specs_cover_each_provider() -> None:
    for fw in Framework:
        assert model_fields(fw)[0].id == "model-input"
        assert runtime_fields(fw)[0].id == "port-input"
