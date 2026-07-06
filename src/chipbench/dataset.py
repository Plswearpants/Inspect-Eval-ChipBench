"""Dataset loaders for ChipBench.

Adapted from https://github.com/zhongkaiyu/ChipBench (MIT License,
Copyright (c) 2023-2024 NVIDIA Research Projects). The dataset under
``data/`` is vendored locally from that repository's ``Verilog Gen/`` and
``Verilog Debugging/`` directories (not HuggingFace). Each Verilog Gen /
Debug problem is a ``{prompt.txt, ref.sv, test.sv}`` triplet on disk;
``ref.sv`` declares ``module RefModule(...)`` and the model is asked to
produce a matching ``module TopModule(...)``.

The Ref Model Gen task's dataset is *not* read from the upstream repo's
``Ref Model Gen/`` directory (not vendored here at all, beyond its three
``gen_*_prompt.txt`` templates) — that directory is a separate
training-data-generation tool built on an unrelated corpus, not the paper's
44x3 benchmark. Instead we construct the samples ourselves by pairing each
Verilog Gen problem's own spec with the vendored
``gen_{python,cxxrtl}_prompt.txt`` templates (see prompts.py for why
SystemC is excluded).

Note on sample counts: the vendored repo's ``verilog_gen`` data contains 45
problems (30 self-contained + 6 not-self-contained + 9 cpu-design), one more
than the paper's reported 44 (an extra ``Four-to-one_multiplexer`` sample not
listed in the paper's Table 7 appendix) — the dataset has evolved since the
paper snapshot. All samples present on disk are included.
"""

import re
from pathlib import Path
from typing import Literal

from inspect_ai.dataset import Dataset, MemoryDataset, Sample

from chipbench.prompts import (
    REFMODEL_LANGUAGES,
    REFMODEL_SYSTEM_PROMPTS,
    RefModelLanguage,
)

DATA_DIR = Path(__file__).parent / "data"

VerilogGenCategory = Literal["self_contained", "not_self_contained", "cpu_ip"]
BugType = Literal["arithmetic", "assignment", "state_machine", "timing"]
Shot = Literal["zero_shot", "one_shot"]

VERILOG_GEN_CATEGORIES: tuple[VerilogGenCategory, ...] = (
    "self_contained",
    "not_self_contained",
    "cpu_ip",
)
BUG_TYPES: tuple[BugType, ...] = ("arithmetic", "assignment", "state_machine", "timing")
SHOTS: tuple[Shot, ...] = ("zero_shot", "one_shot")

_PROBLEM_ID_PATTERN = re.compile(r"^(Prob\d+_.+)_prompt\.txt$")


def _find_problem_ids(directory: Path) -> list[str]:
    ids = []
    for path in sorted(directory.glob("Prob*_prompt.txt")):
        match = _PROBLEM_ID_PATTERN.match(path.name)
        if match:
            ids.append(match.group(1))
    return ids


def _load_triplet(directory: Path, problem_id: str) -> tuple[str, str, str]:
    prompt = (directory / f"{problem_id}_prompt.txt").read_text()
    ref = (directory / f"{problem_id}_ref.sv").read_text()
    test = (directory / f"{problem_id}_test.sv").read_text()
    return prompt, ref, test


def verilog_gen_samples(category: VerilogGenCategory | None = None) -> Dataset:
    """Build the Verilog Gen dataset.

    Args:
        category: Restrict to one category ("self_contained",
            "not_self_contained", or "cpu_ip"). If None, includes all three.
    """
    categories = (category,) if category is not None else VERILOG_GEN_CATEGORIES
    samples = []
    for cat in categories:
        directory = DATA_DIR / "verilog_gen" / cat
        for problem_id in _find_problem_ids(directory):
            prompt, ref, test = _load_triplet(directory, problem_id)
            samples.append(
                Sample(
                    id=f"{cat}/{problem_id}",
                    input=prompt,
                    files={"ref.sv": ref, "test.sv": test},
                    metadata={"category": cat, "problem_id": problem_id},
                )
            )
    if not samples:
        raise ValueError(f"No samples found for category={category!r}")
    return MemoryDataset(samples=samples, name="chipbench_verilog_gen")


def debug_samples(
    shot: Shot | None = None,
    bug_type: BugType | None = None,
) -> Dataset:
    """Build the Verilog Debugging dataset.

    Args:
        shot: Restrict to "zero_shot" or "one_shot". If None, includes both.
        bug_type: Restrict to one bug type ("arithmetic", "assignment",
            "state_machine", or "timing"). If None, includes all four.
    """
    shots = (shot,) if shot is not None else SHOTS
    bug_types = (bug_type,) if bug_type is not None else BUG_TYPES
    samples = []
    for s in shots:
        for bt in bug_types:
            directory = DATA_DIR / "debug" / f"{s}_{bt}"
            for problem_id in _find_problem_ids(directory):
                prompt, ref, test = _load_triplet(directory, problem_id)
                samples.append(
                    Sample(
                        id=f"{s}_{bt}/{problem_id}",
                        input=prompt,
                        files={"ref.sv": ref, "test.sv": test},
                        metadata={"shot": s, "bug_type": bt, "problem_id": problem_id},
                    )
                )
    if not samples:
        raise ValueError(f"No samples found for shot={shot!r}, bug_type={bug_type!r}")
    return MemoryDataset(samples=samples, name="chipbench_debug")


def refmodel_samples(language: RefModelLanguage | None = None) -> Dataset:
    """Build the (constructed) Reference Model Generation dataset.

    Args:
        language: Restrict to one target language ("python" or "cxxrtl").
            If None, includes both (one sample per language per Verilog Gen
            problem).
    """
    if language is not None and language not in REFMODEL_LANGUAGES:
        raise ValueError(
            f"Unsupported language={language!r}. Supported: {REFMODEL_LANGUAGES} "
            "(SystemC is part of the paper's benchmark but is not scoreable "
            "with the vendored crosslang_verify toolbox, see prompts.py)."
        )
    languages = (language,) if language is not None else REFMODEL_LANGUAGES
    samples = []
    for cat in VERILOG_GEN_CATEGORIES:
        directory = DATA_DIR / "verilog_gen" / cat
        for problem_id in _find_problem_ids(directory):
            prompt, ref, _test = _load_triplet(directory, problem_id)
            for lang in languages:
                system_prompt = REFMODEL_SYSTEM_PROMPTS[lang]
                samples.append(
                    Sample(
                        id=f"{problem_id}/{lang}",
                        input=f"{system_prompt}\n\n{prompt}",
                        files={"ref.sv": ref},
                        metadata={
                            "problem_id": problem_id,
                            "category": cat,
                            "language": lang,
                        },
                    )
                )
    if not samples:
        raise ValueError(f"No samples found for language={language!r}")
    return MemoryDataset(samples=samples, name="chipbench_refmodel")
