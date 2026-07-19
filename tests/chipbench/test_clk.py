"""Tests for the vendored (but patched) clk.py -- see the seventh bug writeup.

Loaded by file path rather than package import since Tool_Box/crosslang_verify
has no __init__.py -- it's a vendored, subprocess-invoked toolbox, not part of
the chipbench package, and is excluded from this project's own lint/type-check
tooling (see NOTICE) for that reason. See README.md's Evaluation Report for
the bug writeup.
"""

import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "chipbench"
    / "Tool_Box"
    / "crosslang_verify"
    / "tools"
    / "clk.py"
)
_spec = importlib.util.spec_from_file_location("clk", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
clk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clk)


def test_detects_clk_as_first_input() -> None:
    inputs = [("clk", 1), ("reset_n", 1), ("data_in", 8)]
    assert clk.is_clk_signal(inputs) is True


def test_detects_clk_when_not_first_input() -> None:
    """Regression test: Prob006_cpu_top lists clk third, after inputReady/reset_n."""
    inputs = [("inputReady", 1), ("reset_n", 1), ("clk", 1)]
    assert clk.is_clk_signal(inputs) is True


def test_detects_clk_case_insensitively() -> None:
    inputs = [("data_in", 8), ("CLK", 1)]
    assert clk.is_clk_signal(inputs) is True


def test_no_clk_signal_returns_false() -> None:
    inputs = [("a", 1), ("b", 1), ("sel", 2)]
    assert clk.is_clk_signal(inputs) is False


def test_empty_inputs_returns_false() -> None:
    assert clk.is_clk_signal([]) is False
