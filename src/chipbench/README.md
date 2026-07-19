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
- `cxxrtl_prompt_variant` (Literal['default', 'fixed']): "default" (vendored as-is) or "fixed" (a corrected CXXRTL API for A/B-testing against the default — see README.md's Evaluation Report for why the default fails to compile against the pinned Yosys version). Defaults to "default", unlike stage_missing_defines below, because whether the corrected prompt actually changes model behavior is itself an open question worth measuring against the paper's original — not a harness bug where "fixed" is simply the correct behavior. (default: `'default'`)
- `stage_missing_defines` (bool): whether to apply Bug 5's fix (inject `` `define `` macros ref.sv needs but doesn't itself define). Defaults to True, unlike cxxrtl_prompt_variant above, because this is a straightforward harness gap (the official pipeline never needed this staging since it compiles ref.sv/test.sv together) rather than a substantive A/B question; set False to reproduce the paper's original ref.sv/test.sv split for a before/after comparison. (default: `True`)

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
- **Reference Model Generation** (88 = 44 problems x 2 languages): **not**
  read from the vendored `ref_model_gen/` folder, which is a separate
  training-data-generation tool built on an unrelated corpus, not the
  paper's benchmark. Instead, each Verilog Gen problem's own spec is paired
  with the vendored `gen_{python,cxxrtl}_prompt.txt` system-prompt template
  to construct one sample per language — except `Prob000_Four-to-one_multiplexer`,
  excluded due to a self-contradictory prompt (see Known Limitations below).
  SystemC is part of the original paper's benchmark (44x3=132) but is
  excluded here: the vendored verification toolbox (`Tool_Box/crosslang_verify`)
  has no working SystemC path — `dut_systemc_file` is declared but never
  implemented.

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

*Results produced July 2026. Eval version `2-B` (the Verilator fix in `3-B` postdates these
results — see "Known limitations" below). All runs via OpenRouter
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
- **45 vs. 44 `verilog_gen` problems.** The vendored dataset has gained one problem
  (`Prob000_Four-to-one_multiplexer`) since the paper's own snapshot (its Table 7 appendix lists
  44). `chipbench_refmodel` excludes this same problem for an unrelated reason (a
  self-contradictory prompt, see Known Limitations below), so it happens to match the paper's
  count of 44 problems (88 samples across 2 languages) — coincidentally, not because the exclusion
  was chosen to match. `chipbench_debug`'s 178 problems match the paper's 89×2-shot count exactly.
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

- **No pre-built Docker image is published — the sandbox builds locally on first use.** This
  eval compiles Icarus Verilog, Yosys/CXXRTL, and Verilator from source rather than using
  prebuilt packages, since the versions available via `apt` are too old for
  `crosslang_verify`'s generated testbenches. A cold build takes up to ~10 minutes (observed
  range in practice: 4.5–6 minutes with a warm Docker layer cache cleared, longer on a slower
  connection); every run after that hits Docker's layer cache and starts in a few seconds,
  unless the Dockerfile or `Tool_Box/crosslang_verify/` changes. This is a deliberate tradeoff,
  not an oversight — requesting a pre-built, GHCR-published image (per `CONTRIBUTING.md`'s
  Docker Images section) is possible if the one-time cold-build cost becomes a problem for
  contributors running this eval repeatedly, but requires maintainer-side GHCR/CI setup, so it's
  left as self-built for now.
- **`Prob000_Four-to-one_multiplexer` is excluded from `chipbench_refmodel`.** Its prompt, reused
  verbatim from `verilog_gen`, contradicts the refmodel system prompt prepended to it: the final
  line reads "Write the **Verilog code** for this 4-to-1 multiplexer..." while the CXXRTL/Python
  system prompt says "Do NOT include Verilog." Found via an automated Inspect Scout trajectory
  scan (`/check-trajectories-workflow`, 100-sample subset of a CXXRTL run) — the scan's
  `broken_env` scanner flagged it independently of any compile-time signature, not the
  regex-based failure classifier used elsewhere in this document. Confirmed to be the paper's own
  unmodified data (byte-identical `diff` against the vendored mirror), and — consistent with this
  specific problem already being identified elsewhere in this document as the one addition to the
  vendored dataset absent from the paper's own Table 7 — the only one of all 45 `verilog_gen`
  prompts with this issue (`grep`-confirmed: none of the other 44 end with an explicit "Verilog
  code" instruction). Per `CONTRIBUTING.md`'s Data Quality guidance for a broken dataset record,
  this problem is now filtered out of `chipbench_refmodel` (dropping it from 90 to 88 samples;
  `chipbench_verilog_gen` and `chipbench_debug` are unaffected, since the prompt is entirely
  correct there — "write Verilog code" is exactly what's wanted). Note this is present in the
  official ChipBench repo, not something we added — but excluding it from `chipbench_refmodel`
  has a second benefit beyond fixing the contradiction: it brings the sample count to exactly the
  paper's own 44 problems, making the ours-vs-paper comparison in Table 3 below an apples-to-apples
  44-vs-44 rather than an incidental 45-vs-44. The underlying eval runs still
  cover all 45 problems (a re-run wasn't needed), but the `chipbench_refmodel` pass-rate tables
  below are recomputed to exclude this one problem's samples from the aggregate — see the `4-B`
  changelog entry for how.
- **GPT-3.5 Turbo cannot run `chipbench_debug`'s one-shot variant on every problem.** Its
  16,385-token context window is sometimes exceeded once a full VCD waveform trace is appended to
  the prompt — a model limitation, not a task-design or harness bug. GPT-3.5 results below cover
  zero-shot only for this reason.
- **DeepSeek R1 and GPT-3.5 Turbo were run at a reduced 10 epochs** (rather than the paper's
  default 20) to manage cost and Docker sandbox load at this dataset scale; `pass_at_10` is exact
  at `epochs=10` (its `epochs >= k` requirement is met), but `pass_at_5`'s combinatorial average has
  fewer terms to draw from than the `epochs=20` runs, so its stderr is comparably larger.
- **Seven infrastructure bugs were found and fixed during development of this implementation**
  (an outdated CXXRTL prompt API; missing submodule staging for `not_self_contained` refmodel
  problems; a harness testbench referencing a clock signal for combinational circuits; missing
  macro-definition staging; a vendored port-extraction script that both loses module boundaries
  and mis-parses parametrized bit-widths; a Verilator strictness gap on one problem's golden
  reference; and a clock-detection helper that only checked a module's first input, described
  below). All are confirmed fixed by a regression test, and all but the seventh are additionally
  confirmed at full dataset scale — the fix is confirmed to generalize: a second model (GPT-3.5
  Turbo) run against the fully-fixed pipeline in both refmodel languages shows the identical clean
  signature as the model used to find and fix the bugs (Llama 3.1 8B), not just an artifact of one
  model's specific failure patterns.
- **The Verilator strictness gap (`Prob006_cpu_top`) is fixed and confirmed at full dataset
  scale.** `Prob006_cpu_top`'s golden reference mixes blocking/non-blocking assignments to the same
  packed variable across `always` blocks — a pattern Icarus Verilog (`verilog_gen`/`debug`) accepts
  but Verilator (`refmodel`) used to reject outright (`%Error-BLKANDNBLK`), blocking 100% of
  `not_self_contained` refmodel attempts on this problem in both languages regardless of model
  output. Confirmed to be the paper's own unmodified data (byte-identical `diff`), not a
  dataset-construction issue. Fixed by adding `-Wno-BLKANDNBLK` to `run_verification.py`'s
  `VERILATOR_WARNS` — this only waives Verilator's lint objection to the construct, it doesn't
  change which scheduling Verilator itself elaborates it with, and since `chipbench_refmodel` has no
  other ground truth to compare against, Verilator's own interpretation *is* the golden reference
  regardless. Confirmed via a deterministic e2e regression test
  (`test_refmodel_blkandnblk_waiver_e2e`) and reconfirmed with a fresh full-scale rerun (see
  `5-B` changelog entry) — this fix immediately exposed a **seventh** bug on the exact same
  problem, described next.
- **A seventh bug — `is_clk_signal` only checked a module's first input — is now fixed and
  confirmed.** Once the Verilator fix above let `Prob006_cpu_top` compile far enough to reach the
  testbench-build stage, every attempt on it still failed 100% of the time, now on a different
  error: the generated testbench referenced a local `clk` variable that was never declared.
  `tools/clk.py`'s `is_clk_signal` loops over a module's inputs but `return`s unconditionally on
  the first iteration, so it only ever checked whether the *first* input's name contained "clk" —
  confirmed via `diff` to be the paper's own unmodified code, not something introduced during
  porting. `Prob006_cpu_top` lists `clk` as its third input (after `inputReady`, `reset_n`), so the
  function incorrectly concluded the module wasn't sequential. Fixed by checking every input
  instead of returning early; confirmed via a deterministic e2e regression test
  (`test_refmodel_clk_detection_e2e`) and a fresh full-scale rerun. `Prob006_cpu_top` still scores
  0% after this fix — but now on genuine model-generated-code errors (syntax mistakes, functional
  mismatches), confirmed by inspecting the actual failure text, not a harness block.

### Results

Each task below leads with a compact summary (accuracy = pass@1, the full dataset run in every
case) before the detailed per-category breakdown and paper comparison — the summary is for a
quick read, the breakdown is what actually supports the comparison-to-paper claims.

#### `chipbench_verilog_gen`

| Model | Provider | Accuracy | Stderr | Time |
| ----- | -------- | -------- | ------ | ---- |
| Llama 3.1 8B | Meta | 0.044 | 0.019 | 2h04m |
| DeepSeek R1 (10 epochs) | DeepSeek | 0.271 | 0.056 | 12h22m* |
| GPT-3.5 Turbo (10 epochs) | OpenAI | 0.184 | 0.052 | 13m |

*\*DeepSeek R1's wall-clock includes the local machine idling overnight mid-run; actual active
compute time was closer to 4h22m.*

**Notes:**

- Paper baseline (Table 2, same three models): Llama 3.1 8B 7.0%, DeepSeek R1 23.7%, GPT-3.5
  Turbo 8.15% pass@1.
- All three models completed successfully (900/900, 450/450, 450/450 samples respectively).

vs. paper Table 2, full pass@1/5/10:

| Model | pass@1 (ours / paper) | pass@5 (ours / paper) | pass@10 (ours / paper) |
|---|---|---|---|
| Llama 3.1 8B | 4.44(1.94)% / 7.0% | 11.3(4.15)% / 8.2% | 14.3(4.86)% / 9.3% |
| DeepSeek R1 (10 epochs) | 27.1(5.63)% / 23.7% | 40.6(7.20)% / 33.7% | 42.2(7.45)% / 38.2% |
| GPT-3.5 Turbo (10 epochs) | 18.4(5.18)% / 8.15% | 24.2(6.42)% / 12.59% | 24.4(6.48)% / 12.59% |

Llama 3.1 8B and GPT-3.5 Turbo reproduce the paper's exact 0% on non-self-contained (hierarchical)
designs; DeepSeek R1 does not follow that pattern — it scores substantially above zero on both
sides (paper: 33.3%/50%/50% pass@1/5/10; ours: 18.3%/45.8%/50.0%), close to an exact match on the
paper's own non-zero DeepSeek result there. Self-contained modules track the same order of
magnitude for every model. CPU IP components show a similar split rather than a uniform effect:
DeepSeek R1 and GPT-3.5 Turbo score substantially higher than the paper, while Llama 3.1 8B
actually scores *lower* at pass@1 (7.22% vs. 22.2%) and converges to the paper's exact figure by
pass@10 (22.2% both sides) — not a blanket "we score everyone higher" effect (see below).

#### `chipbench_debug`

| Model | Provider | Accuracy | Stderr | Time |
| ----- | -------- | -------- | ------ | ---- |
| Llama 3.1 8B (zero-shot) | Meta | 0.074 | 0.016 | 1h49m |
| GPT-3.5 Turbo (zero-shot, 10 epochs) | OpenAI | 0.211 | 0.035 | 27m |

**Notes:**

- Paper baseline (Table 4, treated as a zero-shot proxy — the paper doesn't state which shot
  mode Table 4 reports): Llama 3.1 8B 7.77%, GPT-3.5 Turbo 10.0% pass@1.
- Both models completed successfully (3,560/3,560 and 890/890 samples). GPT-3.5's one-shot
  variant was not run at scale — see "Known limitations" above.

vs. paper Table 4, full pass@1/5/10 (zero-shot; see caveat above):

| Model | pass@1 (ours / paper) | pass@5 (ours / paper) | pass@10 (ours / paper) |
|---|---|---|---|
| Llama 3.1 8B (89 problems, 20 epochs) | 7.36(1.58)% / 7.77% | 21.1(3.37)% / 14.7% | 29.6(4.12)% / 22.9% |
| GPT-3.5 Turbo (89 problems, 10 epochs) | 21.1(3.51)% / 10.0% | 34.2(4.84)% / 21.25% | 37.1(5.15)% / 26.25% |

Llama 3.1 8B was also run one-shot (same 89 problems, plus a VCD waveform trace) to check the
paper's own "mixed performance" finding on waveform-aware debugging: one-shot was a modest net
improvement in aggregate (7.36%→7.98% pass@1), but with a genuine per-bug-type split — Arithmetic,
Assignment, and Timing all improved while State machine got worse — echoing the paper's own mixed
result rather than contradicting it.

#### `chipbench_refmodel`

| Model | Provider | Accuracy | Stderr | Time |
| ----- | -------- | -------- | ------ | ---- |
| Llama 3.1 8B, CXXRTL | Meta | 0.045 | 0.021 | 35m |
| Llama 3.1 8B, Python | Meta | 0.122 | 0.038 | 25m |
| GPT-3.5 Turbo, CXXRTL (10 epochs) | OpenAI | 0.068 | 0.029 | 12m |
| GPT-3.5 Turbo, Python (10 epochs) | OpenAI | 0.182 | 0.052 | 11m |

**Notes:**

- Paper baseline (Table 3, Python only — see below): Llama 3.1 8B 2.22%, GPT-3.5 Turbo 5.56%
  pass@1. No published baseline exists for CXXRTL.
- All four runs completed successfully (900/900 and 450/450 samples respectively), against the
  pre-`4-B` 45-problem dataset. Figures in this table and the one below are recomputed to exclude
  `Prob000_Four-to-one_multiplexer` (see the `4-B` changelog entry) from the already-collected
  per-sample results — a re-run wasn't needed since each sample was scored independently; only the
  aggregate pass@1/5/10 and stderr were recomputed over the remaining 44 problems, reimplementing
  Inspect's own `pass_at_k` reducer and `accuracy`/`stderr` metrics
  (`inspect_ai.scorer._reducer.reducer.pass_at`, `inspect_ai.scorer._metrics`) applied to the
  filtered sample set. The 45-problem originals are 0.046/0.128/0.067/0.200 respectively (CXXRTL,
  Python, CXXRTL, Python order above).

vs. paper Table 3 (Python only; no published CXXRTL/SystemC numbers exist), full pass@1/5/10:

| Model | pass@1 (ours / paper) | pass@5 (ours / paper) | pass@10 (ours / paper) |
|---|---|---|---|
| Llama 3.1 8B, Python | 12.2(3.82)% / 2.22% | 23.1(5.74)% / 5.56% | 27.7(6.36)% / 6.67% |
| GPT-3.5 Turbo, Python (10 epochs) | 18.2(5.24)% / 5.56% | 24.4(6.47)% / 6.67% | 25.0(6.60)% / 7.78% |
| Llama 3.1 8B, CXXRTL | 4.5(2.07)% | 11.0(4.11)% | 14.3(4.85)% |
| GPT-3.5 Turbo, CXXRTL (10 epochs) | 6.8(2.87)% | 14.2(4.83)% | 18.2(5.88)% |

CXXRTL has no published comparison to make — the paper reports Table 3 for Python only, despite
CXXRTL being part of its stated three-language methodology (44×3=132 samples).

**`not_self_contained` category, reconfirmed with a fresh targeted rerun after the seventh fix**
(the 6 `not_self_contained` problems only, both fixes live, both languages, matching epoch counts):

| Model | pass@1 (ours / paper) | pass@5 (ours / paper) | pass@10 (ours / paper) |
|---|---|---|---|
| Llama 3.1 8B, Python | 0.83(0.83)% / 0% | 4.17(4.17)% / 0% | 8.33(8.33)% / 0% |
| GPT-3.5 Turbo, Python | 11.67(8.33)% / 0% | 29.56(18.91)% / 0% | 33.33(21.08)% / 0% |
| Llama 3.1 8B, CXXRTL | 0.00(0.00)% | 0.00(0.00)% | 0.00(0.00)% |
| GPT-3.5 Turbo, CXXRTL | 0.00(0.00)% | 0.00(0.00)% | 0.00(0.00)% |

`Prob006_cpu_top` itself still scores 0% in all four reruns (40/40 Python epochs, 30/30 CXXRTL
epochs), but confirmed via the actual failure text to now be genuine model-generated-code errors
(syntax mistakes, functional mismatches) rather than either harness bug — both the `BLKANDNBLK`
and the `clk`-not-declared signatures are absent from every one of these samples. The Llama/GPT-3.5
Python swing in opposite directions from the pre-seventh-fix numbers (Llama down, GPT-3.5 up) is
consistent with sampling noise at this scale (6 problems, each independently re-sampled from the
model) rather than an effect of the fix itself — CXXRTL remains at a flat 0% for both models with
or without `Prob006`, which may be genuine capability difficulty (CXXRTL is the harder language
throughout this document) rather than a further harness issue, but hasn't been specifically
investigated.

The most notable finding here: **the paper reports a flat 0% on both `non_self_contained` and
`cpu_ip`, for every model in Table 3 including both Llama 3.1 8B and GPT-3.5 Turbo** — while our
fixed harness scores above 0% on both categories, for both models (e.g. CPU IP: Llama 17.8→44.4%,
GPT-3.5 34.4→44.4% across pass@1→10). We independently found and fixed a missing-submodule-staging
bug in our own port that would produce exactly this symptom (100% blocked regardless of model
quality) — but that gap is an artifact of our own port's architecture (isolating `ref.sv`
compilation), not something confirmed present in the paper's own code the way the CXXRTL prompt,
port-extraction, and `is_clk_signal` bugs are (each `diff`-confirmed verbatim in the paper's
repository). Our current estimate is that an analogous harness issue in the paper's own tooling is
more likely than these categories being genuinely unsolvable — but since the paper never shipped
its original harness for direct comparison, this remains a specific, falsifiable hypothesis, not a
confirmed finding.

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

The `chipbench_refmodel` totals above (1,800 and 900) predate the `4-B` exclusion of
`Prob000_Four-to-one_multiplexer`; a fresh run against the current dataset would total 1,760 and
880 respectively (44 problems × 2 languages × epochs).

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

### `5-B` (July 2026)

A seventh infrastructure bug, found while reconfirming the sixth: `tools/clk.py`'s
`is_clk_signal` only checked a module's first input for a clock signal (an unconditional early
`return` inside the loop), so `Prob006_cpu_top` — which lists `clk` third, after `inputReady` and
`reset_n` — was misclassified as combinational, leaving its generated testbench referencing a
`clk` variable that was never declared. Confirmed via `diff` to be the paper's own unmodified
code. Fixed by checking every input instead of returning early; confirmed via a deterministic e2e
regression test (`test_refmodel_clk_detection_e2e`) and a fresh full-scale rerun of the affected
`not_self_contained` category (see the Evaluation Report above). The sixth (Verilator strictness)
fix is also reconfirmed at full scale in this same rerun. Bumped `N` (scoring-affecting fix); no
interface change, so `X` is unchanged.

### `4-B` (July 2026)

`Prob000_Four-to-one_multiplexer` excluded from `chipbench_refmodel`'s dataset: its prompt
(reused verbatim from `verilog_gen`) tells the model to write Verilog code, contradicting the
refmodel system prompt's "do NOT include Verilog" instruction — a genuine, if narrow, broken
dataset record (see Known Limitations above), handled per `CONTRIBUTING.md`'s Data Quality
guidance. `chipbench_refmodel` drops from 90 to 88 samples; `chipbench_verilog_gen` and
`chipbench_debug` are unaffected. Bumped `N` (dataset change affecting comparability); no
interface change, so `X` is unchanged.

The four existing `chipbench_refmodel` evaluation runs (Llama 3.1 8B and GPT-3.5 Turbo, Python and
CXXRTL) were not re-run — each sample was already scored independently, so `Prob000`'s per-epoch
scores could simply be dropped from the aggregate. The Results tables above are recomputed directly
from the existing `.eval` logs' per-sample-epoch scores, reimplementing Inspect's own `pass_at_k`
reducer (`inspect_ai.scorer._reducer.reducer.pass_at`: `1 - C(n-c,k)/C(n,k)` per sample) and its
`accuracy`/`stderr` metrics (`inspect_ai.scorer._metrics`: mean and `std(ddof=1)/sqrt(n)` across the
remaining 44 samples) over the filtered sample set. The recomputed "before" values (all 45 problems)
matched the previously-published `3-B` numbers exactly, confirming the recomputation is correct.

### `3-B` (July 2026)

A sixth infrastructure bug, found while working through `EVALUATION_CHECKLIST.md`'s Dataset
Validity check ("is it reasonably possible for a model to succeed at each sample?"): Verilator
rejected `Prob006_cpu_top`'s golden reference outright (`%Error-BLKANDNBLK`), blocking 100% of
`not_self_contained` refmodel attempts on that problem in both languages regardless of model
output. Fixed by adding `-Wno-BLKANDNBLK` to the vendored `run_verification.py`'s
`VERILATOR_WARNS`. Bumped `N` (scoring-affecting fix); no interface change, so `X` is unchanged.

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
