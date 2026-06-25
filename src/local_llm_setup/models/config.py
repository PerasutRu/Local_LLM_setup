"""Shared configuration schemas."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Framework(str, Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"
    LLAMACPP = "llamacpp"
    SGLANG = "sglang"


FRAMEWORK_DEFAULT_PORTS: dict[Framework, int] = {
    Framework.OLLAMA: 11434,
    Framework.VLLM: 8000,
    Framework.LLAMACPP: 8080,
    Framework.SGLANG: 30000,
}


def framework_default_port(framework: Framework) -> int:
    return FRAMEWORK_DEFAULT_PORTS[framework]


class ConfigMode(str, Enum):
    QUICK = "quick"
    FULL = "full"


class OSType(str, Enum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    WSL = "wsl"
    UNKNOWN = "unknown"


class GPUVendor(str, Enum):
    NVIDIA = "nvidia"
    AMD = "amd"
    APPLE = "apple"
    NONE = "none"
    UNKNOWN = "unknown"


class CheckStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class DoctorCheck(BaseModel):
    name: str
    status: CheckStatus
    message: str
    hint: str | None = None


class HostInfo(BaseModel):
    os_type: OSType = OSType.UNKNOWN
    os_version: str = ""
    arch: str = ""
    is_wsl: bool = False
    gpu_vendor: GPUVendor = GPUVendor.UNKNOWN
    gpu_name: str | None = None
    vram_gb: float | None = None
    ram_gb: float | None = None
    docker_installed: bool = False
    docker_version: str | None = None
    compose_installed: bool = False
    compose_version: str | None = None
    nvidia_driver: str | None = None
    cuda_version: str | None = None
    nvidia_container_toolkit: bool = False
    rocm_version: str | None = None
    nginx_installed: bool = False
    checks: list[DoctorCheck] = Field(default_factory=list)


class Capabilities(BaseModel):
    text: bool = True
    vision: bool = False
    audio: bool = False
    tool_calling: bool = False
    mtp: bool = False
    mtp_drafter_model: str | None = None


class VllmServeOptions(BaseModel):
    """vLLM ``serve`` flags — maps to production setups (e.g. Gemma 4 multimodal)."""

    gpu_memory_utilization: float | None = None
    max_num_seqs: int | None = None
    trust_remote_code: bool = False
    enable_prefix_caching: bool = False
    tool_call_parser: str | None = None
    reasoning_parser: str | None = None
    kv_cache_dtype: str | None = None
    limit_mm_per_prompt: str | None = None
    install_audio_extras: bool = False


class ModelConfig(BaseModel):
    """Model name: Ollama tag, HF repo id, or GGUF path/url."""

    name: str
    quantization: str | None = None
    context_length: int = 8192
    tensor_parallel: int = 1
    hf_token_env: str = "HF_TOKEN"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()


class FrameworkConfig(BaseModel):
    framework: Framework
    mode: ConfigMode = ConfigMode.QUICK
    model: ModelConfig
    capabilities: Capabilities = Field(default_factory=Capabilities)
    port: int = 8000
    publish_port: int | None = None
    bind_host: str = "127.0.0.1"
    image_tag: str | None = None
    extra_env: dict[str, str] = Field(default_factory=dict)
    extra_args: list[str] = Field(default_factory=list)
    gpu_count: int = 1
    gpu_device_ids: list[str] = Field(default_factory=list)
    shm_size: str = "16gb"
    ipc: str | None = None
    extra_volumes: list[str] = Field(default_factory=list)
    command_shell: str | None = None
    vllm: VllmServeOptions | None = None

    @model_validator(mode="after")
    def default_port(self) -> FrameworkConfig:
        if self.port == 8000 and self.framework != Framework.VLLM:
            self.port = FRAMEWORK_DEFAULT_PORTS.get(self.framework, self.port)
        return self


class ApiKeyEntry(BaseModel):
    key: str
    label: str = "default"


class NginxConfig(BaseModel):
    enabled: bool = False
    listen_port: int = 8080
    server_name: str = "_"
    upstream_port: int = 8000
    enable_cors: bool = True
    client_max_body_size: str = "50m"
    proxy_read_timeout: str = "600s"
    api_key_auth: bool = False
    api_keys: list[ApiKeyEntry] = Field(default_factory=list)
    bind_host: str = "0.0.0.0"
    tunnel_enabled: bool = True


class SetupConfig(BaseModel):
    profile_name: str = "default"
    output_dir: Path = Path("./output")
    host: HostInfo | None = None
    frameworks: list[FrameworkConfig] = Field(default_factory=list)
    nginx: NginxConfig = Field(default_factory=NginxConfig)
    hf_token: str | None = None

    def primary_framework(self) -> FrameworkConfig | None:
        return self.frameworks[0] if self.frameworks else None


class ValidationIssue(BaseModel):
    level: str  # error | warn | info
    message: str
    field: str | None = None


class GeneratedOutput(BaseModel):
    compose_yaml: str
    env_file: str
    nginx_conf: str | None = None
    api_keys_map: str | None = None
    run_commands: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    config: SetupConfig | None = None
