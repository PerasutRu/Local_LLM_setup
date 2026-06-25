"""Tests for host detection."""

from __future__ import annotations

from unittest.mock import patch

from local_llm_setup.detect.host import (
    detect_os,
    detect_wsl,
    install_hint,
    is_port_free,
)
from local_llm_setup.models.config import OSType


def test_detect_os_linux():
    with patch("platform.system", return_value="Linux"), patch(
        "local_llm_setup.detect.host.detect_wsl", return_value=False
    ), patch("platform.platform", return_value="Linux-6.1"):
        os_type, version, is_wsl = detect_os()
        assert os_type == OSType.LINUX
        assert is_wsl is False


def test_detect_os_wsl():
    with patch("platform.system", return_value="Linux"), patch(
        "local_llm_setup.detect.host.detect_wsl", return_value=True
    ), patch("platform.platform", return_value="Linux-WSL"):
        os_type, _, is_wsl = detect_os()
        assert os_type == OSType.WSL
        assert is_wsl is True


def test_detect_os_macos():
    with patch("platform.system", return_value="Darwin"), patch(
        "platform.platform", return_value="macOS-14"
    ):
        os_type, _, _ = detect_os()
        assert os_type == OSType.MACOS


def test_install_hint_docker_linux():
    hint = install_hint("docker", OSType.LINUX)
    assert hint is not None
    assert "docker" in hint.lower()


def test_is_port_free():
    assert is_port_free(59999) is True
