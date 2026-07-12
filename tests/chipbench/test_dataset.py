"""Tests for ChipBench dataset loaders."""

import pytest

from chipbench.dataset import (
    BUG_TYPES,
    DATA_DIR,
    SHOTS,
    VERILOG_GEN_CATEGORIES,
    _extract_missing_defines,
    _extract_submodule_source,
    debug_samples,
    refmodel_samples,
    verilog_gen_samples,
)


def test_verilog_gen_samples_real_example() -> None:
    """A known sample from the vendored dataset is loaded correctly."""
    dataset = verilog_gen_samples(category="self_contained")
    sample = next(
        s
        for s in dataset
        if s.id == "self_contained/Prob001_continuous_input_sequence_detect"
    )

    assert "TopModule" in str(sample.input)
    assert "shift register" in str(sample.input)
    assert sample.files is not None
    assert "module RefModule" in sample.files["ref.sv"]
    assert "module tb" in sample.files["test.sv"]
    assert sample.metadata == {
        "category": "self_contained",
        "problem_id": "Prob001_continuous_input_sequence_detect",
    }


@pytest.mark.parametrize("category", VERILOG_GEN_CATEGORIES)
def test_verilog_gen_samples_all_categories_nonempty(category: str) -> None:
    dataset = verilog_gen_samples(category=category)  # type: ignore[arg-type]
    assert len(dataset) > 0
    assert all(
        s.metadata is not None and s.metadata["category"] == category for s in dataset
    )


def test_verilog_gen_samples_default_includes_all_categories() -> None:
    all_samples = verilog_gen_samples()
    per_category_total = sum(
        len(verilog_gen_samples(category=c)) for c in VERILOG_GEN_CATEGORIES
    )
    assert len(all_samples) == per_category_total


def test_verilog_gen_samples_unique_ids() -> None:
    dataset = verilog_gen_samples()
    ids = [s.id for s in dataset]
    assert len(ids) == len(set(ids))


def test_debug_samples_real_example() -> None:
    dataset = debug_samples(shot="zero_shot", bug_type="arithmetic")
    sample = next(
        s
        for s in dataset
        if s.id == "zero_shot_arithmetic/Prob001_continuous_input_sequence_detect"
    )

    assert "has bug" in str(sample.input) or "please fix" in str(sample.input)
    assert sample.files is not None
    assert "module RefModule" in sample.files["ref.sv"]
    assert sample.metadata == {
        "shot": "zero_shot",
        "bug_type": "arithmetic",
        "problem_id": "Prob001_continuous_input_sequence_detect",
    }


def test_debug_samples_one_shot_includes_vcd() -> None:
    dataset = debug_samples(shot="one_shot", bug_type="arithmetic")
    sample = next(iter(dataset))
    assert "VCD OUTPUT BEGIN" in str(sample.input)


def test_debug_samples_zero_shot_excludes_vcd() -> None:
    dataset = debug_samples(shot="zero_shot", bug_type="arithmetic")
    sample = next(iter(dataset))
    assert "VCD OUTPUT BEGIN" not in str(sample.input)


@pytest.mark.parametrize("shot", SHOTS)
@pytest.mark.parametrize("bug_type", BUG_TYPES)
def test_debug_samples_all_combinations_nonempty(shot: str, bug_type: str) -> None:
    dataset = debug_samples(shot=shot, bug_type=bug_type)  # type: ignore[arg-type]
    assert len(dataset) > 0


def test_refmodel_samples_constructs_one_per_language_per_problem() -> None:
    all_samples = refmodel_samples()
    python_samples = refmodel_samples(language="python")
    cxxrtl_samples = refmodel_samples(language="cxxrtl")

    assert len(all_samples) == len(python_samples) + len(cxxrtl_samples)
    assert len(python_samples) == len(verilog_gen_samples())


def test_refmodel_samples_python_includes_system_prompt_and_spec() -> None:
    dataset = refmodel_samples(language="python")
    sample = next(
        s
        for s in dataset
        if s.metadata is not None
        and s.metadata["problem_id"] == "Prob001_continuous_input_sequence_detect"
    )

    assert "class TopModule" in str(sample.input)  # from gen_python_prompt.txt
    assert "shift register" in str(sample.input)  # from the problem's own prompt.txt
    assert sample.files is not None
    assert "ref.sv" in sample.files
    assert "test.sv" not in sample.files  # crosslang_verify generates its own testbench


def test_refmodel_samples_excludes_systemc() -> None:
    """SystemC is part of the paper's benchmark but unscoreable with the vendored toolbox."""
    with pytest.raises(ValueError):
        refmodel_samples(language="systemc")  # type: ignore[arg-type]


def test_extract_submodule_source_real_example() -> None:
    """Prob002's not_self_contained prompt embeds the decoder_38 submodule inline."""
    prompt = (
        DATA_DIR
        / "verilog_gen"
        / "not_self_contained"
        / "Prob002_implement_full_subtractor_using_three_to_eight_decoder_prompt.txt"
    ).read_text()

    source = _extract_submodule_source(prompt)

    assert source is not None
    assert "module decoder_38" in source
    assert "endmodule" in source


def test_extract_submodule_source_none_when_absent() -> None:
    """Not every not_self_contained problem needs this: Prob001's ref.sv is self-sufficient."""
    prompt = (
        DATA_DIR
        / "verilog_gen"
        / "not_self_contained"
        / "Prob001_submodules_to_implement_comparison_of_three_input_numbers_prompt.txt"
    ).read_text()

    assert _extract_submodule_source(prompt) is None


def test_refmodel_samples_stages_submodule_source_for_not_self_contained() -> None:
    """Bug 2 fix: chipbench_refmodel's ref.sv must include the submodule Verilator needs."""
    dataset = refmodel_samples(language="python")
    sample = next(
        s
        for s in dataset
        if s.metadata is not None
        and s.metadata["problem_id"]
        == "Prob002_implement_full_subtractor_using_three_to_eight_decoder"
    )

    assert sample.files is not None
    assert "module RefModule" in sample.files["ref.sv"]
    assert "module decoder_38" in sample.files["ref.sv"]


def test_extract_missing_defines_real_example() -> None:
    """Prob006_PC_REG's ref.sv uses macros only defined in its test.sv."""
    directory = DATA_DIR / "verilog_gen" / "cpu_ip"
    ref = (directory / "Prob006_PC_REG_ref.sv").read_text()
    test = (directory / "Prob006_PC_REG_test.sv").read_text()

    defines = _extract_missing_defines(ref, test)

    assert defines is not None
    assert "`define Branch" in defines
    assert "`define RstEnable" in defines


def test_extract_missing_defines_none_when_absent() -> None:
    """Most problems don't use undefined macros at all."""
    directory = DATA_DIR / "verilog_gen" / "cpu_ip"
    ref = (directory / "Prob001_controller_ref.sv").read_text()
    test = (directory / "Prob001_controller_test.sv").read_text()

    assert _extract_missing_defines(ref, test) is None


def test_extract_missing_defines_ignores_compiler_directives() -> None:
    """A bare `timescale (a self-contained directive) isn't a missing macro."""
    ref = "`timescale 1ns/1ps\nmodule RefModule(); endmodule"
    assert _extract_missing_defines(ref, test="") is None


def test_refmodel_samples_stages_missing_defines_for_cpu_ip() -> None:
    """Bug 5 fix: chipbench_refmodel's ref.sv must include macros test.sv defines."""
    dataset = refmodel_samples(language="python")
    sample = next(
        s
        for s in dataset
        if s.metadata is not None and s.metadata["problem_id"] == "Prob006_PC_REG"
    )

    assert sample.files is not None
    assert "`define Branch" in sample.files["ref.sv"]
    assert "module RefModule" in sample.files["ref.sv"]


def test_refmodel_samples_stages_missing_defines_for_not_self_contained() -> None:
    """Bug 5 also affects one not_self_contained problem (Prob006_cpu_top)."""
    dataset = refmodel_samples(language="python")
    sample = next(
        s
        for s in dataset
        if s.metadata is not None and s.metadata["problem_id"] == "Prob006_cpu_top"
    )

    assert sample.files is not None
    assert "`define WORD_SIZE" in sample.files["ref.sv"]


def test_refmodel_samples_stage_missing_defines_false_reproduces_bug_5() -> None:
    """stage_missing_defines=False mimics the paper's original ref.sv/test.sv split.

    Used for the before/after comparison run: our own fixes (Bug 1's prompt,
    Bug 2's submodule staging) stay applied, but this specific paper-side bug
    is left as the paper's original tooling would produce it.
    """
    dataset = refmodel_samples(language="python", stage_missing_defines=False)
    sample = next(
        s
        for s in dataset
        if s.metadata is not None and s.metadata["problem_id"] == "Prob006_PC_REG"
    )

    assert sample.files is not None
    assert "`define Branch" not in sample.files["ref.sv"]
    assert sample.metadata is not None
    assert sample.metadata["stage_missing_defines"] is False
