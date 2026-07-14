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
    CXXRTL_PROMPT_FIXED,
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

# Excluded from chipbench_refmodel only (not chipbench_verilog_gen/debug):
# this problem's prompt, reused verbatim from verilog_gen, ends with "Write
# the Verilog code for this..." while the refmodel system prompt prepended
# to it says "Do NOT include Verilog" -- a self-contradictory instruction
# found via Inspect Scout trajectory analysis (see README.md's Evaluation
# Report). Confirmed to be the paper's own unmodified data, and the only
# one of all 45 verilog_gen prompts with this issue. The prompt is entirely
# correct for chipbench_verilog_gen, where "write Verilog code" is exactly
# what's wanted, so it stays included there.
_EXCLUDED_REFMODEL_PROBLEM_IDS = frozenset({"Prob000_Four-to-one_multiplexer"})

_PROBLEM_ID_PATTERN = re.compile(r"^(Prob\d+_.+)_prompt\.txt$")
_SUBMODULE_SOURCE_PATTERN = re.compile(r"```(?:verilog)?\n(.*?)```", re.DOTALL)
_MACRO_USE_PATTERN = re.compile(r"`([A-Za-z_]\w*)")
_MACRO_DEFINE_PATTERN = re.compile(r"^\s*`define\s+([A-Za-z_]\w*)\b", re.MULTILINE)
# Verilog/SystemVerilog compiler directives -- a backtick-identifier that
# isn't one of these is a macro reference that needs a `define somewhere.
_COMPILER_DIRECTIVES = frozenset(
    {
        "timescale",
        "celldefine",
        "endcelldefine",
        "default_nettype",
        "include",
        "define",
        "undef",
        "ifdef",
        "ifndef",
        "else",
        "elsif",
        "endif",
        "resetall",
        "unconnected_drive",
        "nounconnected_drive",
        "line",
        "pragma",
        "protect",
        "endprotect",
    }
)


def _extract_submodule_source(prompt: str) -> str | None:
    """Extract embedded submodule Verilog source from a not_self_contained prompt.

    not_self_contained problems give the model a required submodule's source
    inline in the prompt (a fenced code block) rather than in ref.sv itself —
    ref.sv only defines RefModule and instantiates the submodule. verilog_gen/
    debug get the submodule "for free" since the model's own generated.sv is
    compiled alongside ref.sv in the same iverilog invocation; chipbench_refmodel
    compiles ref.sv alone via Verilator and needs the submodule supplied
    explicitly, or every not_self_contained sample fails with a Verilator
    MODMISSING error regardless of what the model writes (see README.md's
    Evaluation Report).
    """
    match = _SUBMODULE_SOURCE_PATTERN.search(prompt)
    return match.group(1) if match else None


def _extract_missing_defines(ref: str, test: str) -> str | None:
    """Extract `` `define `` macros ref.sv uses but doesn't itself define, from test.sv.

    Some problems' ref.sv references Verilog preprocessor macros (e.g.
    `` `Branch ``, `` `ZeroWord ``) whose `` `define `` only appears in
    test.sv. Preprocessor directives are global across all files compiled
    together, so this works by accident for verilog_gen/debug (which
    compile ref.sv + test.sv + generated.sv in one iverilog invocation) but
    not chipbench_refmodel, which compiles ref.sv alone via Verilator and
    needs the macros supplied explicitly, or every such problem fails with
    "Define or directive not defined" regardless of what the model writes
    (see README.md's Evaluation Report).
    """
    used = {
        name
        for name in _MACRO_USE_PATTERN.findall(ref)
        if name not in _COMPILER_DIRECTIVES
    }
    if not used:
        return None
    already_defined = set(_MACRO_DEFINE_PATTERN.findall(ref))
    missing = used - already_defined
    if not missing:
        return None
    define_lines = [
        line
        for line in test.splitlines()
        if (match := _MACRO_DEFINE_PATTERN.match(line)) and match.group(1) in missing
    ]
    return "\n".join(define_lines) if define_lines else None


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
    if category is not None and category not in VERILOG_GEN_CATEGORIES:
        raise ValueError(
            f"Unsupported category={category!r}. Supported: {VERILOG_GEN_CATEGORIES}"
        )
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
    if shot is not None and shot not in SHOTS:
        raise ValueError(f"Unsupported shot={shot!r}. Supported: {SHOTS}")
    if bug_type is not None and bug_type not in BUG_TYPES:
        raise ValueError(f"Unsupported bug_type={bug_type!r}. Supported: {BUG_TYPES}")
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


def refmodel_samples(
    language: RefModelLanguage | None = None,
    cxxrtl_prompt_variant: Literal["default", "fixed"] = "default",
    stage_missing_defines: bool = True,
) -> Dataset:
    """Build the (constructed) Reference Model Generation dataset.

    Args:
        language: Restrict to one target language ("python" or "cxxrtl").
            If None, includes both (one sample per language per Verilog Gen
            problem).
        cxxrtl_prompt_variant: "default" uses the vendored gen_cxxrtl_prompt.txt
            as-is; "fixed" swaps in prompts.CXXRTL_PROMPT_FIXED, a corrected
            variant for A/B-testing whether the original's outdated CXXRTL API
            is actually why CXXRTL scores so low (see README.md's Evaluation
            Report). Has no effect on the "python" language.
        stage_missing_defines: whether to inject `` `define `` macros ref.sv
            uses but doesn't itself define (Bug 5's fix). Defaults to True;
            set False to reproduce the paper's original ref.sv/test.sv split
            as-is, e.g. for a before/after comparison against a pipeline that
            mimics the paper's own methodology rather than our fixes.
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
            if problem_id in _EXCLUDED_REFMODEL_PROBLEM_IDS:
                continue
            prompt, ref, test = _load_triplet(directory, problem_id)
            # Unconditional, unlike stage_missing_defines below: without the
            # submodule's source, ref.sv references an undefined module and
            # cannot compile at all, in any configuration, so there is no
            # meaningful "before" state to reproduce by toggling this off.
            if cat == "not_self_contained":
                submodule_source = _extract_submodule_source(prompt)
                if submodule_source:
                    ref = f"{ref}\n\n{submodule_source}"
            if stage_missing_defines:
                missing_defines = _extract_missing_defines(ref, test)
                if missing_defines:
                    ref = f"{missing_defines}\n\n{ref}"
            for lang in languages:
                if lang == "cxxrtl" and cxxrtl_prompt_variant == "fixed":
                    system_prompt = CXXRTL_PROMPT_FIXED
                else:
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
                            "cxxrtl_prompt_variant": cxxrtl_prompt_variant,
                            "stage_missing_defines": stage_missing_defines,
                        },
                    )
                )
    if not samples:
        raise ValueError(f"No samples found for language={language!r}")
    return MemoryDataset(samples=samples, name="chipbench_refmodel")
