"""End-to-end tests for ChipBench tasks.

These run the real sandboxed toolchain (Icarus Verilog / Verilator /
crosslang_verify), so they are marked `docker` and are not part of the
default fast test run.
"""

import pytest
from inspect_ai import Epochs, eval
from inspect_ai.model import Model, ModelOutput, get_model

from chipbench import chipbench_debug, chipbench_refmodel, chipbench_verilog_gen

# A correct fix/translation of Prob001_continuous_input_sequence_detect: an
# 8-bit shift register (new bit enters the LSB) whose `match` output is
# asserted when the pre-shift register equals 8'b0111_0001.
_CORRECT_TOP_MODULE_SV = """
```verilog
module TopModule(
    input clk,
    input rst_n,
    input a,
    output reg match
    );

    reg [7:0] a_tem;

    always @(posedge clk or negedge rst_n)
        if (!rst_n) match <= 1'b0;
        else if (a_tem == 8'b0111_0001) match <= 1'b1;
        else match <= 1'b0;

    always @(posedge clk or negedge rst_n)
        if (!rst_n) a_tem <= 8'b0;
        else a_tem <= {a_tem[6:0], a};
endmodule
```
"""

_INCORRECT_TOP_MODULE_SV = """
```verilog
module TopModule(
    input clk,
    input rst_n,
    input a,
    output reg match
    );
    always @(*) match = 1'b0;
endmodule
```
"""

_CORRECT_PYTHON_REFMODEL = """
```python
class TopModule:
    def __init__(self):
        self.a_tem = 0

    def eval(self, inputs: dict) -> dict:
        rst_n = inputs.get("rst_n", 1)
        a = inputs.get("a", 0)
        if not rst_n:
            match = 0
        else:
            match = 1 if self.a_tem == 0b01110001 else 0
        if not rst_n:
            self.a_tem = 0
        else:
            self.a_tem = ((self.a_tem << 1) | (a & 1)) & 0xFF
        return {"match": match}
```
"""

# A correct CXXRTL implementation of Prob000_Four-to-one_multiplexer -- purely
# combinational (no clock port at all), correctly omitting any p_clk member
# per the prompt's own rules. Regression test for Bug 3
# (agent_artefacts/chipbench/known-issues/refmodel-scoring-gaps.md): the
# vendored testbench generator used to reference cxxrtl_dut.p_clk
# unconditionally even for combinational DUTs, which this hand-written,
# deliberately-correct submission would fail to compile against regardless of
# its own correctness. A real model's output can't be used for this check --
# it needs to genuinely omit p_clk to expose the bug, which isn't guaranteed
# on any single sampled completion.
_CORRECT_CXXRTL_MULTIPLEXER = """
```cpp
#include <cxxrtl/cxxrtl.h>

namespace cxxrtl_design {

struct p_TopModule : public cxxrtl::module {
    cxxrtl::value<2> p_d0;
    cxxrtl::value<2> p_d1;
    cxxrtl::value<2> p_d2;
    cxxrtl::value<2> p_d3;
    cxxrtl::value<2> p_sel;
    cxxrtl::value<2> p_mux__out;

    void reset() override {
    }

    bool eval(cxxrtl::performer *performer = nullptr) override {
        uint32_t sel = p_sel.data[0] & 0x3;
        uint32_t result;
        if (sel == 0) result = p_d0.data[0];
        else if (sel == 1) result = p_d1.data[0];
        else if (sel == 2) result = p_d2.data[0];
        else result = p_d3.data[0];
        p_mux__out.data[0] = result & 0x3;
        return true;
    }

    bool commit() override {
        return false;
    }
};

} // namespace cxxrtl_design
```
"""


def _mock_model(content: str) -> Model:
    return get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.from_content(model="mockllm/model", content=content)
        ],
    )


@pytest.mark.docker
@pytest.mark.slow(60)
def test_verilog_gen_correct_completion_passes() -> None:
    [log] = eval(
        tasks=chipbench_verilog_gen(category="self_contained"),
        model=_mock_model(_CORRECT_TOP_MODULE_SV),
        epochs=Epochs(1, ["pass_at_1"]),
        sample_id="self_contained/Prob001_continuous_input_sequence_detect",
    )
    assert log.status == "success"
    assert log.results is not None
    assert log.results.scores[0].metrics["accuracy"].value == 1.0


@pytest.mark.docker
@pytest.mark.slow(60)
def test_verilog_gen_incorrect_completion_fails() -> None:
    [log] = eval(
        tasks=chipbench_verilog_gen(category="self_contained"),
        model=_mock_model(_INCORRECT_TOP_MODULE_SV),
        epochs=Epochs(1, ["pass_at_1"]),
        sample_id="self_contained/Prob001_continuous_input_sequence_detect",
    )
    assert log.status == "success"
    assert log.results is not None
    assert log.results.scores[0].metrics["accuracy"].value == 0.0


@pytest.mark.docker
@pytest.mark.slow(60)
def test_debug_e2e() -> None:
    """The golden fix (sample's own ref.sv) should score CORRECT for any debug case."""
    [log] = eval(
        tasks=chipbench_debug(shot="zero_shot", bug_type="arithmetic"),
        model=_mock_model(_CORRECT_TOP_MODULE_SV),
        epochs=Epochs(1, ["pass_at_1"]),
        sample_id="zero_shot_arithmetic/Prob001_continuous_input_sequence_detect",
    )
    assert log.status == "success"


@pytest.mark.docker
@pytest.mark.slow(60)
def test_refmodel_e2e() -> None:
    [log] = eval(
        tasks=chipbench_refmodel(language="python"),
        model=_mock_model(_CORRECT_PYTHON_REFMODEL),
        epochs=Epochs(1, ["pass_at_1"]),
        sample_id="Prob001_continuous_input_sequence_detect/python",
    )
    assert log.status == "success"
    assert log.results is not None
    assert log.results.scores[0].metrics["accuracy"].value == 1.0


@pytest.mark.docker
@pytest.mark.slow(60)
def test_refmodel_cxxrtl_combinational_e2e() -> None:
    """Regression test for Bug 3: a correct combinational CXXRTL DUT must pass.

    Uses a hand-written submission rather than a real model's, since the bug
    only manifests when the DUT correctly omits p_clk -- not guaranteed on
    any single sampled completion, which is exactly why this bug went
    unnoticed (and its fix untested) for so long.
    """
    [log] = eval(
        tasks=chipbench_refmodel(language="cxxrtl", cxxrtl_prompt_variant="fixed"),
        model=_mock_model(_CORRECT_CXXRTL_MULTIPLEXER),
        epochs=Epochs(1, ["pass_at_1"]),
        sample_id="Prob000_Four-to-one_multiplexer/cxxrtl",
    )
    assert log.status == "success"
    assert log.results is not None
    assert log.results.scores[0].metrics["accuracy"].value == 1.0


_CORRECT_PYTHON_ALU = """
```python
class TopModule:
    def eval(self, inputs: dict) -> dict:
        a = inputs.get("SrcA", 0) & 0xFFFFFFFF
        b = inputs.get("SrcB", 0) & 0xFFFFFFFF
        op = inputs.get("Operation", 0) & 0xF
        shamt = b & 0x1F

        def signed(x):
            return x - 0x100000000 if x & 0x80000000 else x

        sa, sb = signed(a), signed(b)
        if op == 0b0000:
            r = a & b
        elif op == 0b0001:
            r = a | b
        elif op == 0b0010:
            r = sa + sb
        elif op == 0b0011:
            r = a ^ b
        elif op == 0b0100:
            r = a << shamt
        elif op == 0b0101:
            r = a >> shamt
        elif op == 0b0110:
            r = sa - sb
        elif op == 0b0111:
            r = sa >> shamt
        elif op == 0b1000:
            r = 1 if a == b else 0
        elif op == 0b1001:
            r = 1 if a != b else 0
        elif op == 0b1100:
            r = 1 if sa < sb else 0
        elif op == 0b1101:
            r = 1 if sa >= sb else 0
        elif op == 0b1110:
            r = 1 if a < b else 0
        elif op == 0b1111:
            r = 1 if a >= b else 0
        elif op == 0b1010:
            r = 1
        else:
            r = 0
        return {"ALUResult": r & 0xFFFFFFFF}
```
"""


@pytest.mark.docker
@pytest.mark.slow(60)
def test_refmodel_parametrized_width_e2e() -> None:
    """Regression test for Bug 6b: parametrized port widths must be extracted correctly.

    Prob002_alu declares `input logic [DATA_WIDTH-1:0] SrcA` with
    `parameter DATA_WIDTH = 32` -- the exact pattern that used to make
    extract_ports.py mis-extract "logic" as a bogus port name (see Bug 6b in
    known-issues/refmodel-scoring-gaps.md). Checks the specific old failure
    signatures are gone rather than requiring perfect ALU correctness, since
    that's what this regression is actually about.
    """
    [log] = eval(
        tasks=chipbench_refmodel(language="python"),
        model=_mock_model(_CORRECT_PYTHON_ALU),
        epochs=Epochs(1, ["pass_at_1"]),
        sample_id="Prob002_alu/python",
    )
    assert log.status == "success"
    assert log.samples is not None
    explanation = log.samples[0].scores["crosslang_verify_scorer"].explanation or ""
    assert "redeclaration of" not in explanation
    assert "has no member named" not in explanation
    assert "RefModule compiled successfully" in explanation
    assert "Build successful" in explanation


@pytest.mark.docker
@pytest.mark.slow(60)
def test_refmodel_multi_module_e2e() -> None:
    """Regression test for Bug 6a: a staged submodule's ports must not leak into the top module.

    Prob003_asynchronous_FIFO's ref.sv already embeds its dual_port_RAM
    submodule inline, sharing port names (wclk, wdata, rdata) with the top
    module -- the exact collision that used to produce duplicate C++
    variable declarations in the generated testbench (see Bug 6a).
    """
    [log] = eval(
        tasks=chipbench_refmodel(language="python"),
        model=_mock_model(
            "```python\nclass TopModule:\n    def eval(self, inputs):\n        return {}\n```"
        ),
        epochs=Epochs(1, ["pass_at_1"]),
        sample_id="Prob003_asynchronous_FIFO/python",
    )
    assert log.status == "success"
    assert log.samples is not None
    explanation = log.samples[0].scores["crosslang_verify_scorer"].explanation or ""
    assert "redeclaration of" not in explanation
    assert "RefModule compiled successfully" in explanation
