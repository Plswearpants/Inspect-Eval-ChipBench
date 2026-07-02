"""Unit tests for ChipBench scorers."""

from inspect_ai.scorer import Scorer

from chipbench.scorers import crosslang_verify_scorer, extract_code, iverilog_scorer


def test_extract_code_from_verilog_fence() -> None:
    completion = (
        "Here is the module:\n```verilog\nmodule TopModule(); endmodule\n```\nDone."
    )
    assert extract_code(completion) == "module TopModule(); endmodule"


def test_extract_code_from_bare_fence() -> None:
    completion = "```\nmodule TopModule(); endmodule\n```"
    assert extract_code(completion) == "module TopModule(); endmodule"


def test_extract_code_from_python_fence() -> None:
    completion = "```python\nclass TopModule:\n    pass\n```"
    assert extract_code(completion) == "class TopModule:\n    pass"


def test_extract_code_no_fence_returns_stripped_completion() -> None:
    completion = "  module TopModule(); endmodule  "
    assert extract_code(completion) == "module TopModule(); endmodule"


def test_extract_code_uses_first_fence_when_multiple_present() -> None:
    completion = "```verilog\nfirst\n```\nsome text\n```verilog\nsecond\n```"
    assert extract_code(completion) == "first"


def test_iverilog_scorer_is_scorer() -> None:
    assert isinstance(iverilog_scorer(), Scorer)


def test_crosslang_verify_scorer_is_scorer() -> None:
    assert isinstance(crosslang_verify_scorer(), Scorer)
