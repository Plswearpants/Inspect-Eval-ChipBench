"""Tests for the vendored (but patched) extract_ports.py -- see Bug 6.

Loaded by file path rather than package import since Tool_Box/crosslang_verify
has no __init__.py -- it's a vendored, subprocess-invoked toolbox, not part of
the chipbench package, and is excluded from this project's own lint/type-check
tooling (see NOTICE) for that reason. See README.md's Evaluation Report for
the bug writeup.
"""

import importlib.util
import tempfile
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "chipbench"
    / "Tool_Box"
    / "crosslang_verify"
    / "tools"
    / "extract_ports.py"
)
_spec = importlib.util.spec_from_file_location("extract_ports", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
extract_ports = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract_ports)

DATA_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "chipbench" / "data" / "verilog_gen"
)


def test_resolves_parametrized_width_bug_6b() -> None:
    """Prob002_alu: `input logic [DATA_WIDTH-1:0] SrcA` must not lose its name to 'logic'."""
    inputs, outputs = extract_ports.extract_ports_from_verilog(
        str(DATA_DIR / "cpu_ip" / "Prob002_alu_ref.sv")
    )
    names = {name for name, _width in inputs + outputs}
    assert "logic" not in names
    assert dict(inputs)["SrcA"] == 32
    assert dict(inputs)["SrcB"] == 32
    assert dict(inputs)["Operation"] == 4
    assert dict(outputs)["ALUResult"] == 32


def test_resolves_arithmetic_width_expression() -> None:
    """Prob032: `output reg [size*2-1:0] mul_out` with parameter size = 4 -> width 8."""
    inputs, outputs = extract_ports.extract_ports_from_verilog(
        str(DATA_DIR / "self_contained" / "Prob032_pipeline_multiplier_ref.sv")
    )
    assert dict(inputs)["mul_a"] == 4
    assert dict(inputs)["mul_b"] == 4
    assert dict(outputs)["mul_out"] == 8


def test_ignores_second_module_bug_6a(tmp_path: Path) -> None:
    """A submodule sharing a port name with the top module must not be extracted too."""
    verilog = tmp_path / "staged_ref.sv"
    verilog.write_text(
        """
        module RefModule(
            input wclk,
            input [7:0] data,
            output [7:0] result
        );
        endmodule

        module submodule(
            input wclk,
            input [15:0] internal_only
        );
        endmodule
        """
    )
    inputs, outputs = extract_ports.extract_ports_from_verilog(str(verilog))
    names = {name for name, _width in inputs + outputs}
    assert names == {"wclk", "data", "result"}
    assert dict(inputs)["wclk"] == 1
    assert "internal_only" not in names


def test_real_multi_module_file_no_duplicate_ports() -> None:
    """Prob003_asynchronous_FIFO already embeds dual_port_RAM, sharing wclk/wdata/rdata."""
    inputs, outputs = extract_ports.extract_ports_from_verilog(
        str(DATA_DIR / "not_self_contained" / "Prob003_asynchronous_FIFO_ref.sv")
    )
    names = [name for name, _width in inputs + outputs]
    assert len(names) == len(set(names)), f"duplicate ports extracted: {names}"
    assert "wenc" not in names  # dual_port_RAM-only port must not leak through


def test_resolves_macro_based_width() -> None:
    """Bug 5's staged `define lines must also resolve as widths, e.g. `WORD_SIZE."""
    with_defines = "`define WORD_SIZE 16\n\nmodule RefModule(\n    output [`WORD_SIZE-1:0] data\n);\nendmodule\n"
    with tempfile.NamedTemporaryFile("w", suffix=".sv", delete=False) as f:
        f.write(with_defines)
        path = f.name
    inputs, outputs = extract_ports.extract_ports_from_verilog(path)
    assert dict(outputs)["data"] == 16


def test_unresolvable_width_falls_back_without_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A width depending on $clog2(...) can't be resolved -- must default to 1, not crash."""
    verilog = tmp_path / "unresolvable.sv"
    verilog.write_text(
        """
        module RefModule#(parameter DEPTH = 16)(
            input [$clog2(DEPTH)-1:0] addr
        );
        endmodule
        """
    )
    inputs, _outputs = extract_ports.extract_ports_from_verilog(str(verilog))
    assert dict(inputs)["addr"] == 1
    assert "could not resolve width" in capsys.readouterr().out
