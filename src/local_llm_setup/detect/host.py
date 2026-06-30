"""Host detection and doctor checks."""

from __future__ import annotations

import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path

from local_llm_setup.models.config import (
    CheckStatus,
    DoctorCheck,
    GpuDevice,
    GPUVendor,
    HostInfo,
    OSType,
)


def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode, out.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 1, ""


def detect_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def detect_os() -> tuple[OSType, str, bool]:
    system = platform.system().lower()
    version = platform.platform()
    is_wsl = detect_wsl()

    if is_wsl:
        return OSType.WSL, version, True
    if system == "linux":
        return OSType.LINUX, version, False
    if system == "darwin":
        return OSType.MACOS, version, False
    if system == "windows":
        return OSType.WINDOWS, version, False
    return OSType.UNKNOWN, version, False


def detect_docker() -> tuple[bool, str | None]:
    code, out = _run(["docker", "version", "--format", "{{.Server.Version}}"])
    if code == 0 and out:
        return True, out.splitlines()[0]
    code, out = _run(["docker", "--version"])
    if code == 0:
        m = re.search(r"Docker version ([\d.]+)", out)
        return True, m.group(1) if m else out
    return False, None


def detect_compose() -> tuple[bool, str | None]:
    for cmd in (["docker", "compose", "version", "--short"], ["docker-compose", "--version"]):
        code, out = _run(cmd)
        if code == 0 and out:
            return True, out.splitlines()[0]
    return False, None


def detect_nvidia() -> tuple[str | None, str | None, bool]:
    driver = None
    cuda = None
    toolkit = False

    code, out = _run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    if code == 0 and out:
        driver = out.splitlines()[0].strip()

    code, out = _run(["nvcc", "--version"])
    if code == 0:
        m = re.search(r"release ([\d.]+)", out)
        if m:
            cuda = m.group(1)

    if not cuda and driver:
        code, out = _run(["nvidia-smi"])
        if code == 0:
            m = re.search(r"CUDA Version:\s*([\d.]+)", out)
            if m:
                cuda = m.group(1)

    code, out = _run(["docker", "info", "--format", "{{json .Runtimes}}"])
    if code == 0 and "nvidia" in out.lower():
        toolkit = True
    else:
        code, out = _run(["which", "nvidia-ctk"])
        toolkit = code == 0

    return driver, cuda, toolkit


def detect_rocm() -> str | None:
    code, out = _run(["rocm-smi", "--showdriverversion"])
    if code == 0:
        m = re.search(r"([\d.]+)", out)
        if m:
            return m.group(1)
    code, out = _run(["rocminfo"])
    if code == 0 and "gfx" in out.lower():
        return "detected"
    return None


def detect_gpu_devices() -> list[GpuDevice]:
    code, out = _run(
        ["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"]
    )
    if code != 0 or not out:
        return []

    devices: list[GpuDevice] = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",", 2)]
        if len(parts) < 2:
            continue
        idx, name = parts[0], parts[1]
        vram: float | None = None
        if len(parts) > 2:
            try:
                vram = round(float(parts[2]) / 1024, 1)
            except ValueError:
                pass
        devices.append(GpuDevice(index=idx, name=name, vram_gb=vram))
    return devices


def detect_gpu() -> tuple[GPUVendor, str | None, float | None]:
    os_type, _, _ = detect_os()

    if os_type == OSType.MACOS and platform.machine() in ("arm64", "aarch64"):
        return GPUVendor.APPLE, "Apple Silicon", None

    devices = detect_gpu_devices()
    if devices:
        first = devices[0]
        return GPUVendor.NVIDIA, first.name, first.vram_gb

    if detect_rocm():
        return GPUVendor.AMD, "AMD GPU (ROCm)", None

    return GPUVendor.NONE, None, None


def detect_ram_gb() -> float | None:
    os_type, _, _ = detect_os()
    try:
        if os_type == OSType.LINUX or os_type == OSType.WSL:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / 1024 / 1024, 1)
        if os_type == OSType.MACOS:
            code, out = _run(["sysctl", "-n", "hw.memsize"])
            if code == 0:
                return round(int(out.strip()) / 1024**3, 1)
    except (OSError, ValueError):
        pass
    return None


def detect_nginx() -> bool:
    return shutil.which("nginx") is not None


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def install_hint(check_name: str, os_type: OSType) -> str | None:
    hints: dict[str, dict[OSType, str]] = {
        "docker": {
            OSType.LINUX: "curl -fsSL https://get.docker.com | sh",
            OSType.WSL: "curl -fsSL https://get.docker.com | sh",
            OSType.MACOS: "brew install --cask docker",
            OSType.WINDOWS: "winget install Docker.DockerDesktop",
        },
        "compose": {
            OSType.LINUX: "Docker Compose v2 is included with Docker Desktop / docker-ce",
            OSType.MACOS: "Included with Docker Desktop",
            OSType.WINDOWS: "Included with Docker Desktop",
        },
        "nvidia_driver": {
            OSType.LINUX: "https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/",
            OSType.WSL: "Install NVIDIA driver on Windows + WSL2 CUDA support",
        },
        "nvidia_container_toolkit": {
            OSType.LINUX: "https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html",
            OSType.WSL: "Same as Linux: install nvidia-container-toolkit",
        },
        "nginx": {
            OSType.LINUX: "sudo apt install nginx  # or: sudo dnf install nginx",
            OSType.MACOS: "brew install nginx",
        },
    }
    return hints.get(check_name, {}).get(os_type)


def run_doctor() -> HostInfo:
    os_type, os_version, is_wsl = detect_os()
    arch = platform.machine()
    gpu_vendor, gpu_name, vram_gb = detect_gpu()
    gpu_devices = detect_gpu_devices() if gpu_vendor == GPUVendor.NVIDIA else []
    ram_gb = detect_ram_gb()
    docker_ok, docker_ver = detect_docker()
    compose_ok, compose_ver = detect_compose()
    nvidia_driver, cuda_version, nvidia_ctk = detect_nvidia()
    rocm_version = detect_rocm()
    nginx_ok = detect_nginx()

    checks: list[DoctorCheck] = []

    def add(name: str, ok: bool, msg_ok: str, msg_fail: str, warn_only: bool = False):
        hint = None if ok else install_hint(name, os_type)
        checks.append(
            DoctorCheck(
                name=name,
                status=CheckStatus.OK if ok else (CheckStatus.WARN if warn_only else CheckStatus.FAIL),
                message=msg_ok if ok else msg_fail,
                hint=hint,
            )
        )

    add("docker", docker_ok, f"Docker {docker_ver}", "Docker not found")
    add("compose", compose_ok, f"Compose {compose_ver}", "Docker Compose not found")
    add(
        "gpu",
        gpu_vendor != GPUVendor.NONE,
        _gpu_check_message(gpu_vendor, gpu_name, vram_gb, gpu_devices),
        "No GPU detected — CPU-only inference",
        warn_only=True,
    )

    if gpu_vendor == GPUVendor.NVIDIA:
        add(
            "nvidia_driver",
            nvidia_driver is not None,
            f"NVIDIA driver {nvidia_driver}",
            "NVIDIA driver not found",
        )
        add(
            "cuda",
            cuda_version is not None,
            f"CUDA {cuda_version}",
            "CUDA not detected",
            warn_only=True,
        )
        add(
            "nvidia_container_toolkit",
            nvidia_ctk,
            "NVIDIA Container Toolkit available",
            "NVIDIA Container Toolkit not detected — GPU in Docker may not work",
            warn_only=True,
        )
    elif gpu_vendor == GPUVendor.AMD:
        add(
            "rocm",
            rocm_version is not None,
            f"ROCm {rocm_version}",
            "ROCm not detected",
            warn_only=True,
        )
    elif gpu_vendor == GPUVendor.APPLE:
        checks.append(
            DoctorCheck(
                name="metal",
                status=CheckStatus.OK,
                message="Apple Silicon Metal available (use Ollama or llama.cpp for best support)",
            )
        )

    add("nginx", nginx_ok, "nginx installed", "nginx not installed (optional)", warn_only=True)

    return HostInfo(
        os_type=os_type,
        os_version=os_version,
        arch=arch,
        is_wsl=is_wsl,
        gpu_vendor=gpu_vendor,
        gpu_name=gpu_name,
        vram_gb=vram_gb,
        gpu_devices=gpu_devices,
        ram_gb=ram_gb,
        docker_installed=docker_ok,
        docker_version=docker_ver,
        compose_installed=compose_ok,
        compose_version=compose_ver,
        nvidia_driver=nvidia_driver,
        cuda_version=cuda_version,
        nvidia_container_toolkit=nvidia_ctk,
        rocm_version=rocm_version,
        nginx_installed=nginx_ok,
        checks=checks,
    )


def _gpu_check_message(
    gpu_vendor: GPUVendor,
    gpu_name: str | None,
    vram_gb: float | None,
    gpu_devices: list[GpuDevice],
) -> str:
    if not gpu_name:
        return "No GPU"
    if len(gpu_devices) <= 1:
        return f"GPU: {gpu_name} ({vram_gb or '?'} GB VRAM)"
    parts = [
        f"GPU {d.index}: {d.name} ({d.vram_gb or '?'} GB)"
        for d in gpu_devices
    ]
    return f"{len(gpu_devices)} GPUs — " + "; ".join(parts)


def detect_host() -> HostInfo:
    return run_doctor()
