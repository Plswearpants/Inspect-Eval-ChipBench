"""Tests for ChipBench dataset loaders."""

import pytest

from chipbench.dataset import (
    BUG_TYPES,
    SHOTS,
    VERILOG_GEN_CATEGORIES,
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
