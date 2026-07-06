"""ChipBench: A Next-Step Benchmark for Evaluating LLM Performance in AI-Aided Chip Design

Zhongkai Yu, Chenyang Zhou, Yichen Lin, Hejia Zhang, Haotian Ye, Junxia Cui,
Zaifeng Pan, Jishen Zhao, Yufei Ding
https://arxiv.org/abs/2601.21448

Based on: https://github.com/zhongkaiyu/ChipBench
(MIT License, Copyright (c) 2023-2024 NVIDIA Research Projects)

# Verilog generation
inspect eval chipbench/chipbench_verilog_gen

# restrict to one category
inspect eval chipbench/chipbench_verilog_gen -T category=self_contained

# Verilog debugging
inspect eval chipbench/chipbench_debug -T shot=one_shot -T bug_type=timing

# Reference model generation (Python or CXXRTL; SystemC is not scoreable, see prompts.py)
inspect eval chipbench/chipbench_refmodel -T language=python
"""

from pathlib import Path

from inspect_ai import Epochs, Task, task
from inspect_ai.model import GenerateConfig
from inspect_ai.solver import generate

from chipbench.dataset import (
    BugType,
    Shot,
    VerilogGenCategory,
    debug_samples,
    refmodel_samples,
    verilog_gen_samples,
)
from chipbench.prompts import RefModelLanguage
from chipbench.scorers import crosslang_verify_scorer, iverilog_scorer
from utils.metadata import load_version_from_yaml

COMPOSE_FILE = str(Path(__file__).parent / "compose.yaml")

# paper's own harness default (ChipBench configure.ac: samples="20"),
# used to support pass@1/pass@5/pass@10
NUM_EPOCHS = 20

# VerilogEval convention, used by the paper for all model evaluations
TEMPERATURE = 0.85
TOP_P = 0.95

EVAL_VERSION = load_version_from_yaml("chipbench")


@task
def chipbench_verilog_gen(category: VerilogGenCategory | None = None) -> Task:
    """Verilog generation from specification.

    Args:
        category: Restrict to one problem category ("self_contained",
            "not_self_contained", or "cpu_ip"). If None, includes all three.
    """
    return Task(
        dataset=verilog_gen_samples(category=category),
        epochs=Epochs(NUM_EPOCHS, ["pass_at_1", "pass_at_5", "pass_at_10"]),
        solver=generate(),
        scorer=iverilog_scorer(),
        config=GenerateConfig(temperature=TEMPERATURE, top_p=TOP_P),
        sandbox=("docker", COMPOSE_FILE),
        version=EVAL_VERSION,
    )


@task
def chipbench_debug(
    shot: Shot | None = None,
    bug_type: BugType | None = None,
) -> Task:
    """Verilog debugging: fix an injected bug in a golden module.

    Args:
        shot: Restrict to "zero_shot" (module description + buggy code only)
            or "one_shot" (also includes a waveform dump). If None, includes
            both.
        bug_type: Restrict to one bug type ("arithmetic", "assignment",
            "state_machine", or "timing"). If None, includes all four.
    """
    return Task(
        dataset=debug_samples(shot=shot, bug_type=bug_type),
        epochs=Epochs(NUM_EPOCHS, ["pass_at_1", "pass_at_5", "pass_at_10"]),
        solver=generate(),
        scorer=iverilog_scorer(),
        config=GenerateConfig(temperature=TEMPERATURE, top_p=TOP_P),
        sandbox=("docker", COMPOSE_FILE),
        version=EVAL_VERSION,
    )


@task
def chipbench_refmodel(language: RefModelLanguage | None = None) -> Task:
    """Cross-language reference model generation.

    Args:
        language: Restrict to one target language ("python" or "cxxrtl").
            If None, includes both. SystemC is part of the original
            benchmark but is excluded here — see prompts.py for why.
    """
    return Task(
        dataset=refmodel_samples(language=language),
        epochs=Epochs(NUM_EPOCHS, ["pass_at_1", "pass_at_5", "pass_at_10"]),
        solver=generate(),
        scorer=crosslang_verify_scorer(),
        config=GenerateConfig(temperature=TEMPERATURE, top_p=TOP_P),
        sandbox=("docker", COMPOSE_FILE),
        version=EVAL_VERSION,
    )
