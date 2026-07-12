"""Prompt templates for the ChipBench reference-model-generation task.

Adapted from https://github.com/zhongkaiyu/ChipBench/tree/main/Ref%20Model%20Gen
(MIT License, Copyright (c) 2023-2024 NVIDIA Research Projects). These are
the vendored system prompts the ChipBench authors use to instruct a model
to produce a reference model.

Only Python and CXXRTL are supported: the vendored ``Tool_Box/crosslang_verify``
verification toolbox has no working SystemC path (``dut_systemc_file`` is an
unused, unimplemented parameter in ``generate_testbench.py``), so a SystemC
submission can't actually be scored. ``gen_systemc_prompt.txt`` remains
vendored under ``data/refmodel_prompts/`` for future use if that gap is
closed upstream, but is not wired into any task.
"""

from pathlib import Path
from typing import Literal

REFMODEL_PROMPTS_DIR = Path(__file__).parent / "data" / "refmodel_prompts"

RefModelLanguage = Literal["python", "cxxrtl"]

REFMODEL_LANGUAGES: tuple[RefModelLanguage, ...] = ("python", "cxxrtl")

REFMODEL_SYSTEM_PROMPTS: dict[RefModelLanguage, str] = {
    language: (REFMODEL_PROMPTS_DIR / f"gen_{language}_prompt.txt").read_text()
    for language in REFMODEL_LANGUAGES
}

# A/B-test variant: the original gen_cxxrtl_prompt.txt (vendored verbatim from
# upstream) teaches a CXXRTL virtual-method API that predates the one Yosys
# v0.60's actual cxxrtl.h ships (confirmed by reading the header directly:
# `reset()`/`eval(performer*)`/`commit()` signatures, and that `wire::commit()`
# needs an observer argument the original example didn't supply). This fixed
# variant corrects those signatures. Not wired into REFMODEL_SYSTEM_PROMPTS by
# default — see chipbench.py's `cxxrtl_prompt_variant` task parameter — since
# whether it actually improves pass rate is exactly what's being tested; see
# README.md's Evaluation Report.
CXXRTL_PROMPT_FIXED = (REFMODEL_PROMPTS_DIR / "gen_cxxrtl_prompt_fixed.txt").read_text()
