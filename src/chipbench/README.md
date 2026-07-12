# ChipBench: A Next-Step Benchmark for Evaluating LLM Performance in AI-Aided Chip Design

[ChipBench](https://arxiv.org/abs/2601.21448) evaluates LLM capability in AI-aided chip design across three tasks: generating Verilog RTL from a specification, debugging Verilog with an injected bug (arithmetic, assignment, timing, or state-machine), and generating a cross-language reference model (Python or CXXRTL) for a Verilog module. Unlike earlier Verilog benchmarks (VerilogEval, RTLLM), ChipBench's modules are substantially longer and more complex (averaging 61.7 lines / 438.7 cells vs. ~16-46 lines / ~7-33 cells), and its top-performing model in the original paper (Claude 4.5 Opus) solves only 30.74% of Verilog generation problems and 13.33% of Python reference-model problems pass@1 — far from saturated.

Scoring is by functional-equivalence simulation, not string matching: generated Verilog is compiled and simulated against a golden reference with Icarus Verilog (generation, debugging), or a generated Python/CXXRTL reference model is checked against the golden Verilog with a Verilator-based cross-language differential test (reference model generation), reusing the ChipBench authors' own verification tooling rather than reimplementing it.

<!-- Contributors: Automatically Generated -->
Contributed by [@Plswearpants](https://github.com/Plswearpants)
<!-- /Contributors: Automatically Generated -->

<!-- Usage: Automatically Generated -->
## Usage

First, install dependencies:

```bash
uv sync
```

Then run evaluations:

```bash
uv run inspect eval chipbench/chipbench_verilog_gen --model openai/gpt-5-nano
uv run inspect eval chipbench/chipbench_debug --model openai/gpt-5-nano
uv run inspect eval chipbench/chipbench_refmodel --model openai/gpt-5-nano
```

You can also import tasks as Python objects:

```python
from inspect_ai import eval
from chipbench import chipbench_verilog_gen, chipbench_debug, chipbench_refmodel
eval(chipbench_verilog_gen)
```

After running evaluations, view logs with:

```bash
uv run inspect view
```

If you don't want to specify `--model` each time, create a `.env` file:

```bash
INSPECT_EVAL_MODEL=anthropic/claude-opus-4-1-20250805
ANTHROPIC_API_KEY=<anthropic-api-key>
```
<!-- /Usage: Automatically Generated -->

<!-- Options: Automatically Generated -->
## Options

You can control a variety of options from the command line. For example:

```bash
uv run inspect eval chipbench/chipbench_verilog_gen --limit 10
uv run inspect eval chipbench/chipbench_debug --max-connections 10
uv run inspect eval chipbench/chipbench_refmodel --temperature 0.5
```

See `uv run inspect eval --help` for all available options.
<!-- /Options: Automatically Generated -->

<!-- Parameters: Automatically Generated -->
## Parameters

### `chipbench_verilog_gen`

- `category` (Optional[Literal['self_contained', 'not_self_contained', 'cpu_ip']]): Restrict to one problem category ("self_contained", "not_self_contained", or "cpu_ip"). If None, includes all three. (default: `None`)

### `chipbench_debug`

- `shot` (Optional[Literal['zero_shot', 'one_shot']]): Restrict to "zero_shot" (module description + buggy code only) or "one_shot" (also includes a waveform dump). If None, includes both. (default: `None`)
- `bug_type` (Optional[Literal['arithmetic', 'assignment', 'state_machine', 'timing']]): Restrict to one bug type ("arithmetic", "assignment", "state_machine", or "timing"). If None, includes all four. (default: `None`)

### `chipbench_refmodel`

- `language` (Optional[Literal['python', 'cxxrtl']]): Restrict to one target language ("python" or "cxxrtl"). If None, includes both. SystemC is part of the original benchmark but is excluded here — see prompts.py for why. (default: `None`)
- `cxxrtl_prompt_variant` (Literal['default', 'fixed']): "default" (vendored as-is) or "fixed" (a corrected CXXRTL API for A/B-testing against the default — see README.md's Evaluation Report for why the default fails to compile against the pinned Yosys version). (default: `'default'`)
- `stage_missing_defines` (bool): whether to apply Bug 5's fix (inject `` `define `` macros ref.sv needs but doesn't itself define). Defaults to True; set False to reproduce the paper's original ref.sv/test.sv split for a before/after comparison. (default: `True`)

<!-- /Parameters: Automatically Generated -->

## Dataset

The dataset is vendored locally under `data/` from the official
[ChipBench repository](https://github.com/zhongkaiyu/ChipBench) (MIT
licensed), not re-hosted on HuggingFace.

- **Verilog Gen** (45 problems: 30 self-contained + 6 not-self-contained + 9
  CPU-IP design modules): each problem is a `{prompt.txt, ref.sv, test.sv}`
  triplet. `prompt.txt` describes the interface and behavior of a module the
  model must implement as `module TopModule(...)`; `ref.sv` is the golden
  `module RefModule(...)` implementation. This is one more sample than the
  paper's reported 44 — the vendored dataset has gained one additional
  self-contained problem since the paper's Table 7 snapshot.
- **Verilog Debugging** (178 = 89 bug cases x 2 shot modes): `prompt.txt`
  contains the module description plus a buggy `TopModule` with one of four
  injected bug types (arithmetic, assignment, timing, state machine). In
  `one_shot` variants, a waveform (`.vcd`) dump is statically appended to the
  prompt (no simulation is run to produce it — it's baked into the vendored
  data); `zero_shot` omits it.
- **Reference Model Generation** (90 = 45 problems x 2 languages): **not**
  read from the vendored `ref_model_gen/` folder, which is a separate
  training-data-generation tool built on an unrelated corpus, not the
  paper's benchmark. Instead, each Verilog Gen problem's own spec is paired
  with the vendored `gen_{python,cxxrtl}_prompt.txt` system-prompt template
  to construct one sample per language. SystemC is part of the original
  paper's benchmark (44x3=132) but is excluded here: the vendored
  verification toolbox (`Tool_Box/crosslang_verify`) has no working SystemC
  path — `dut_systemc_file` is declared but never implemented.

Example (`chipbench_verilog_gen`, `self_contained/Prob001_continuous_input_sequence_detect`):

```text
Input: "I would like you to implement a module named `TopModule` with the
        following interface... The module should implement an 8-bit shift
        register that shifts in the input `a`... The output `match` should
        be asserted whenever the shift register matches 8'b0111_0001..."
Files: ref.sv (golden `module RefModule`), test.sv (testbench)
```

## Scoring

- **`chipbench_verilog_gen` / `chipbench_debug`**: the model's Verilog is
  written as `generated.sv` inside the sandbox and compiled together with
  the sample's `test.sv` and `ref.sv` using Icarus Verilog
  (`iverilog -g2012 test.sv ref.sv generated.sv`); the resulting simulation
  is run with `vvp` and its `Mismatches: X in Y samples` output line is
  parsed. The sample scores correct iff `X == 0`; a missing line (crash,
  hang, or timeout) scores incorrect rather than being treated as a pass.
- **`chipbench_refmodel`**: the model's Python or C++ (CXXRTL) code is
  written into the sandbox and verified with the vendored
  `Tool_Box/crosslang_verify/main.py`, which compiles the golden `ref.sv`
  with Verilator, drives 1000+ random stimuli, and diffs outputs against the
  submitted reference model.
- Metrics: `pass@1`, `pass@5`, `pass@10`, computed via Inspect's built-in
  `pass_at_k` epoch reducer with 20 completions per sample (matching the
  ChipBench authors' own harness default, `configure.ac`'s `--with-samples`
  default of 20), at `temperature=0.85`, `top_p=0.95` (the VerilogEval
  convention the paper uses for all model evaluations).

## Evaluation Report

*Results produced July 2026. Eval version `1-A`. All runs via OpenRouter
(`openrouter/meta-llama/llama-3.1-8b-instruct`,
`openrouter/deepseek/deepseek-r1`, `openrouter/openai/gpt-3.5-turbo`).*

### Implementation details

**Deviations from the reference implementation:**

- **Single-shot generation only.** The paper's own `ref_model_gen/gen.py` supports iterative
  fixing (`--turns 3`, i.e. the model gets to see its own compile/test errors and retry). This
  implementation uses Inspect's plain `generate()` — one completion per attempt, no retry loop —
  for all three tasks, matching Inspect's standard task-design conventions rather than the paper's
  bespoke script.
- **SystemC excluded.** The paper's reference-model task covers three target languages (Python,
  CXXRTL, SystemC); SystemC is dropped here because the vendored `crosslang_verify` toolbox has no
  working SystemC verification path.
- **45 vs. 44 `verilog_gen`/`refmodel` problems.** The vendored dataset has gained one problem
  (`Prob000_Four-to-one_multiplexer`) since the paper's own snapshot (its Table 7 appendix lists
  44). `chipbench_debug`'s 178 problems match the paper's 89×2-shot count exactly.
- **`chipbench_refmodel`'s dataset is constructed, not read off disk.** The paper never ships a
  runnable refmodel dataset directory; this implementation builds one at runtime from the
  `verilog_gen` problem set (prompt + expected Verilog reference), reusing the paper's own
  `gen_python_prompt.txt`/`gen_cxxrtl_prompt.txt` system prompts.
- **A corrected CXXRTL prompt is available as an opt-in variant.** The vendored
  `gen_cxxrtl_prompt.txt` teaches a CXXRTL C++ API (`override`-based `eval()`, zero-arg `commit()`)
  that doesn't match the pinned Yosys v0.60 toolchain's actual generated header — every CXXRTL
  attempt fails to compile regardless of model quality. `cxxrtl_prompt_variant="fixed"` swaps in a
  corrected prompt verified directly against Yosys v0.60's `cxxrtl.h`; `"default"` (the paper's
  original, unmodified) remains the parameter default for reproduction fidelity. All CXXRTL results
  below use `"fixed"` unless noted, since the default variant cannot meaningfully measure model
  capability (83% of samples fail identically on this signature).

**Known limitations and edge cases:**

- **A Verilator strictness gap remains open.** `Prob006_cpu_top`'s golden reference mixes
  blocking/non-blocking assignments to the same packed variable across `always` blocks — a pattern
  Icarus Verilog (used for `verilog_gen`/`debug`) accepts but Verilator (used for `refmodel`)
  rejects outright (`%Error-BLKANDNBLK`). Confirmed to be the paper's own unmodified data
  (byte-identical `diff`), not a dataset-construction issue. This blocks 100% of
  `not_self_contained` refmodel attempts on this one problem, in both languages, regardless of
  model output.
- **GPT-3.5 Turbo cannot run `chipbench_debug`'s one-shot variant on every problem.** Its
  16,385-token context window is sometimes exceeded once a full VCD waveform trace is appended to
  the prompt — a model limitation, not a task-design or harness bug. GPT-3.5 results below cover
  zero-shot only for this reason.
- **DeepSeek R1 and GPT-3.5 Turbo were run at a reduced 10 epochs** (rather than the paper's
  default 20) to manage cost and Docker sandbox load at this dataset scale; `pass_at_10` is exact
  at `epochs=10` (its `epochs >= k` requirement is met), but `pass_at_5`'s combinatorial average has
  fewer terms to draw from than the `epochs=20` runs, so its stderr is comparably larger.
- **Five infrastructure bugs were found and fixed during development of this implementation**
  (an outdated CXXRTL prompt API; missing submodule staging for `not_self_contained` refmodel
  problems; a harness testbench referencing a clock signal for combinational circuits; missing
  macro-definition staging; and a vendored port-extraction script that both loses module boundaries
  and mis-parses parametrized bit-widths). All five are confirmed fixed and — importantly — the fix
  is confirmed to generalize: a second model (GPT-3.5 Turbo) run against the fully-fixed pipeline in
  both refmodel languages shows the identical clean signature as the model used to find and fix the
  bugs (Llama 3.1 8B), not just an artifact of one model's specific failure patterns.

### Results

#### `chipbench_verilog_gen` — vs. paper Table 2

| Model | pass@1 (ours / paper) | pass@5 (ours / paper) | pass@10 (ours / paper) |
|---|---|---|---|
| Llama 3.1 8B | 4.44(1.94)% / 7.0% | 11.3(4.15)% / 8.2% | 14.3(4.86)% / 9.3% |
| DeepSeek R1 (10 epochs) | 27.1(5.63)% / 23.7% | 40.6(7.20)% / 33.7% | 42.2(7.45)% / 38.2% |
| GPT-3.5 Turbo (10 epochs) | 18.4(5.18)% / 8.15% | 24.2(6.42)% / 12.59% | 24.4(6.48)% / 12.59% |

Non-self-contained (hierarchical) designs reproduce the paper's specific finding of a **flat 0%
pass rate across all three models** exactly. Self-contained modules track the same order of
magnitude for every model. CPU IP components consistently score higher in our runs than the
paper's, for all three models — the one discrepancy here that looks structural rather than
incidental (see below).

#### `chipbench_debug` — vs. paper Table 4 (zero-shot; see caveat below)

The paper's Table 4 doesn't state whether it's zero-shot, one-shot, or a blend of both, so this
comparison assumes it's a reasonable zero-shot proxy, not a confirmed match.

| Model | pass@1 (ours / paper) | pass@5 (ours / paper) | pass@10 (ours / paper) |
|---|---|---|---|
| Llama 3.1 8B (89 problems, 20 epochs) | 7.36(1.58)% / 7.77% | 21.1(3.37)% / 14.7% | 29.6(4.12)% / 22.9% |
| GPT-3.5 Turbo (89 problems, 10 epochs) | 21.1(3.51)% / 10.0% | 34.2(4.84)% / 21.25% | 37.1(5.15)% / 26.25% |

Llama 3.1 8B was also run one-shot (same 89 problems, plus a VCD waveform trace) to check the
paper's own "mixed performance" finding on waveform-aware debugging: one-shot was a modest net
improvement in aggregate (7.36%→7.98% pass@1), but with a genuine per-bug-type split — Arithmetic,
Assignment, and Timing all improved while State machine got worse — echoing the paper's own mixed
result rather than contradicting it.

#### `chipbench_refmodel` — vs. paper Table 3 (Python only; no published CXXRTL/SystemC numbers exist)

| Model | pass@1 (ours / paper) | pass@5 (ours / paper) | pass@10 (ours / paper) |
|---|---|---|---|
| Llama 3.1 8B, Python | 12.8(3.79)% / 2.22% | 24.7(5.83)% / 5.56% | 29.3(6.43)% / 6.67% |
| GPT-3.5 Turbo, Python (10 epochs) | 20.0(5.43)% / 5.56% | 26.1(6.54)% / 6.67% | 26.7(6.67)% / 7.78% |
| Llama 3.1 8B, CXXRTL | 4.56(2.02)% | 11.4(4.03)% | 15.1(4.81)% |
| GPT-3.5 Turbo, CXXRTL (10 epochs) | 6.67(2.81)% | 13.9(4.73)% | 17.8(5.76)% |

CXXRTL has no published comparison to make — the paper reports Table 3 for Python only, despite
CXXRTL being part of its stated three-language methodology (44×3=132 samples).

The most notable finding here: **the paper reports a flat 0% on both `non_self_contained` and
`cpu_ip`, for every model in Table 3 including both Llama 3.1 8B and GPT-3.5 Turbo** — while our
fixed harness scores well above 0% on both categories, for both models (e.g. CPU IP: Llama
17.8→44.4%, GPT-3.5 34.4→44.4% across pass@1→10). Since this implementation independently found
and fixed a missing-submodule-staging bug that would produce exactly this symptom (100% blocked
regardless of model quality) in its own port — and the paper never shipped its original harness for
direct comparison — the most likely explanation is that the paper's own tooling has an equivalent,
unfixed bug, not that these categories are universally unsolvable. This is circumstantial (the
paper's original code isn't available to test directly) but is now backed by two independent models
both hitting exactly 0% on exactly the two categories a missing-submodule-staging bug would block.

### Reproducibility information

| Task | Model | Samples run / total | Epochs |
|---|---|---|---|
| `chipbench_verilog_gen` | Llama 3.1 8B | 900 / 900 | 20 |
| `chipbench_verilog_gen` | DeepSeek R1 | 450 / 450 | 10 |
| `chipbench_verilog_gen` | GPT-3.5 Turbo | 450 / 450 | 10 |
| `chipbench_debug` | Llama 3.1 8B | 3,560 / 3,560 | 20 |
| `chipbench_debug` | GPT-3.5 Turbo (zero-shot only) | 890 / 890 | 10 |
| `chipbench_refmodel` | Llama 3.1 8B (Python + CXXRTL) | 1,800 / 1,800 | 20 |
| `chipbench_refmodel` | GPT-3.5 Turbo (Python + CXXRTL) | 900 / 900 | 10 |

Commands used:

```bash
# verilog_gen
uv run inspect eval src/chipbench/chipbench.py@chipbench_verilog_gen \
  --model openrouter/meta-llama/llama-3.1-8b-instruct
uv run inspect eval src/chipbench/chipbench.py@chipbench_verilog_gen \
  --model openrouter/deepseek/deepseek-r1 --epochs 10
uv run inspect eval src/chipbench/chipbench.py@chipbench_verilog_gen \
  --model openrouter/openai/gpt-3.5-turbo --epochs 10

# debug
uv run inspect eval src/chipbench/chipbench.py@chipbench_debug \
  --model openrouter/meta-llama/llama-3.1-8b-instruct
uv run inspect eval src/chipbench/chipbench.py@chipbench_debug \
  -T shot=zero_shot --model openrouter/openai/gpt-3.5-turbo --epochs 10

# refmodel
uv run inspect eval src/chipbench/chipbench.py@chipbench_refmodel \
  -T language=cxxrtl -T cxxrtl_prompt_variant=fixed \
  --model openrouter/meta-llama/llama-3.1-8b-instruct
uv run inspect eval src/chipbench/chipbench.py@chipbench_refmodel \
  -T language=python --model openrouter/meta-llama/llama-3.1-8b-instruct
uv run inspect eval src/chipbench/chipbench.py@chipbench_refmodel \
  -T language=cxxrtl -T cxxrtl_prompt_variant=fixed \
  --model openrouter/openai/gpt-3.5-turbo --epochs 10
uv run inspect eval src/chipbench/chipbench.py@chipbench_refmodel \
  -T language=python --model openrouter/openai/gpt-3.5-turbo --epochs 10
```

`--epochs 10` for DeepSeek R1 and GPT-3.5 Turbo, and `-T shot=zero_shot` for GPT-3.5's debug run,
are both justified above under "Known limitations." All other parameters use task defaults.

## Changelog

### `2-B` (July 2026)

Five infrastructure bugs affecting `chipbench_refmodel` scoring were found and fixed (see
Evaluation Report above for details): an outdated CXXRTL prompt API, missing submodule staging for
`not_self_contained` problems, an unconditional clock reference in the generated testbench, missing
macro-definition staging, and a vendored port-extraction script that lost module boundaries and
mis-parsed parametrized bit-widths. Bumped `N` since these fixes materially change scoring results
for previously-run samples.

Two new optional parameters added to `chipbench_refmodel` (`X` bump, backward-compatible — both
default to preserving prior behavior):

- `cxxrtl_prompt_variant: Literal["default", "fixed"] = "default"` — `"fixed"` swaps in a corrected
  CXXRTL prompt (see above); `"default"` keeps the original vendored prompt.
- `stage_missing_defines: bool = True` — whether to inject `` `define `` macros a problem's `ref.sv`
  needs but doesn't itself define. Defaults to `True` (the fix applied); `False` reproduces the
  original, unfixed behavior for controlled before/after comparisons.

### `1-A` (initial release)

Initial implementation of all three ChipBench tasks.
