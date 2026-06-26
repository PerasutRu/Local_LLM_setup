"""Tests for stop_all_stacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from local_llm_setup.instances.registry import InstanceInfo
from local_llm_setup.runner import DeployResult, stop_all_stacks


def test_stop_all_stacks_no_running():
    with patch("local_llm_setup.runner.list_running_instances", return_value=[]):
        result = stop_all_stacks()
    assert result.success
    assert result.steps == []


def test_stop_all_stacks_stops_each(tmp_path: Path):
    inst_a = InstanceInfo(
        profile_name="a",
        profile_path=tmp_path / "a.yaml",
        output_dir=tmp_path / "out-a",
        status="running",
    )
    inst_b = InstanceInfo(
        profile_name="b",
        profile_path=tmp_path / "b.yaml",
        output_dir=tmp_path / "out-b",
        status="running",
    )
    calls: list[Path] = []

    def fake_stop(output_dir, **kwargs):
        calls.append(output_dir)
        return DeployResult(success=True, steps=[])

    with patch("local_llm_setup.runner.list_running_instances", return_value=[inst_a, inst_b]), patch(
        "local_llm_setup.runner.stop_stack", side_effect=fake_stop
    ), patch("local_llm_setup.profiles.load_profile", side_effect=OSError):
        result = stop_all_stacks()

    assert result.success
    assert calls == [inst_a.output_dir, inst_b.output_dir]
