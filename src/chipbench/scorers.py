"""Scorers for ChipBench.

Both scorers run inside the sandboxed toolchain (Icarus Verilog, Yosys/CXXRTL,
Verilator) and defer to the vendored ChipBench verification code rather than
reimplementing simulation or comparison logic:

- ``iverilog_scorer`` (verilog_gen, debug): compiles the model's generated
  Verilog together with the sample's ``ref.sv``/``test.sv`` (already staged
  in the sandbox via ``Sample.files``) using Icarus Verilog, exactly as the
  vendored ``test.sv`` testbenches expect, and parses the
  ``Mismatches: X in Y samples`` line the testbench itself prints.
- ``crosslang_verify_scorer`` (refmodel): shells out to the vendored
  ``Tool_Box/crosslang_verify/main.py`` (baked into the sandbox image) to
  verify a Python or CXXRTL reference model against ``ref.sv``.
"""

import re
from typing import Literal

from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Scorer,
    Target,
    accuracy,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState
from inspect_ai.util import ExecResult, sandbox

VERIFY_TIMEOUT = 60

_MISMATCH_PATTERN = re.compile(r"Mismatches:\s*(\d+)\s*in\s*(\d+)\s*samples")

_VERILOG_CODE_PATTERN = re.compile(
    r"```(?:verilog|systemverilog)?\n(.*?)```", re.DOTALL
)
_GENERIC_CODE_PATTERN = re.compile(r"```\w*\n(.*?)```", re.DOTALL)

CrosslangDutFlag = Literal["--dut-py", "--dut-cc"]

_DUT_FILENAME_AND_FLAG: dict[str, tuple[str, CrosslangDutFlag]] = {
    "python": ("generated.py", "--dut-py"),
    "cxxrtl": ("generated.cc", "--dut-cc"),
}


def extract_code(completion: str) -> str:
    """Extract code from a model completion, stripping markdown fences if present."""
    matches = _VERILOG_CODE_PATTERN.findall(
        completion
    ) or _GENERIC_CODE_PATTERN.findall(completion)
    return matches[0].strip() if matches else completion.strip()


@scorer(metrics=[accuracy(), stderr()])
def iverilog_scorer() -> Scorer:
    """Score by compiling and simulating the generated Verilog against the golden reference."""

    async def score(state: TaskState, target: Target) -> Score:
        code = extract_code(state.output.completion)
        await sandbox().write_file("generated.sv", code)

        compile_result = await sandbox().exec(
            cmd=[
                "iverilog",
                "-g2012",
                "-o",
                "sim.vvp",
                "test.sv",
                "ref.sv",
                "generated.sv",
            ],
            timeout=VERIFY_TIMEOUT,
        )
        if not compile_result.success:
            return Score(
                value=INCORRECT,
                answer=code,
                explanation=f"iverilog compile failed:\n{compile_result.stderr}",
            )

        try:
            run_result = await sandbox().exec(
                cmd=["vvp", "sim.vvp"], timeout=VERIFY_TIMEOUT
            )
        except TimeoutError:
            run_result = ExecResult(False, 1, "", "Simulation timed out.")

        match = _MISMATCH_PATTERN.search(run_result.stdout)
        if match is None:
            return Score(
                value=INCORRECT,
                answer=code,
                explanation=(
                    "Simulation did not report a Mismatches line (crashed, hung, or "
                    f"timed out before completion):\n{run_result.stdout}\n{run_result.stderr}"
                ),
            )

        mismatches = int(match.group(1))
        return Score(
            value=CORRECT if mismatches == 0 else INCORRECT,
            answer=code,
            explanation=match.group(0),
        )

    return score


@scorer(metrics=[accuracy(), stderr()])
def crosslang_verify_scorer() -> Scorer:
    """Score by running the vendored crosslang_verify tool against the golden Verilog."""

    async def score(state: TaskState, target: Target) -> Score:
        assert state.metadata is not None
        language = state.metadata["language"]
        dut_filename, dut_flag = _DUT_FILENAME_AND_FLAG[language]

        code = extract_code(state.output.completion)
        await sandbox().write_file(dut_filename, code)

        try:
            result = await sandbox().exec(
                cmd=[
                    "python3",
                    "/opt/crosslang_verify/main.py",
                    "ref.sv",
                    dut_flag,
                    dut_filename,
                    "-w",
                    "work",
                ],
                timeout=VERIFY_TIMEOUT,
            )
        except TimeoutError:
            result = ExecResult(False, 1, "", "Verification timed out.")

        return Score(
            value=CORRECT if result.success else INCORRECT,
            answer=code,
            explanation=f"{result.stdout}\n{result.stderr}",
        )

    return score
