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
