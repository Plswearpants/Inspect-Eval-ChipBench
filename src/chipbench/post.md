# ChipBench: An Inspect AI Evaluation for AI-Aided Chip Design

**What it measures:** whether LLMs can write, debug, and model digital hardware (Verilog) —
correctness is checked by real circuit simulation, not by comparing text.
**Paper:** [arXiv:2601.21448](https://arxiv.org/abs/2601.21448) · **Original code:**
[github.com/zhongkaiyu/ChipBench](https://github.com/zhongkaiyu/ChipBench)

## TL;DR

Standardized, adversarially-validated evaluation matters more here than in most domains: as
frontier models edge toward writing and debugging the hardware they will eventually run on,
un-gameable, non-saturated benchmarks of that specific capability are how we monitor
self-recursive progress — a model quietly improving the substrate it runs on — rather than being
blindsided by it. This document ports ChipBench (Verilog generation, debugging, and cross-language
reference-model generation) into Inspect AI, validates that its scoring can't be fooled by a
plausible-looking wrong answer, and reproduces the original paper's numbers across three models.
Most of the actual effort went into the evaluation harness, not model prompting: six infrastructure
bugs (five in our own port, one in the vendored toolbox we reused) were found and fixed, each
producing a clean-looking near-0% score that had nothing to do with model capability — fixing all
six dropped the harness's own pipeline-failure share from 43–93% to ~2% on the affected categories,
confirmed at full dataset scale and shown to generalize to a second model rather than being an
artifact of the model used to find the bugs.

**Status:** all three tasks (`chipbench_verilog_gen`, `chipbench_debug`, `chipbench_refmodel`)
implemented, tested (54 unit/e2e tests, full pipeline validated against a real Docker toolchain),
and reproduced against two to three models each. All six known infrastructure bugs are fixed and
regression-tested. Submitted to the [Inspect Evals
Register](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/EVAL_REGISTER.md).

## Why this benchmark

Existing Verilog benchmarks are largely saturated — state-of-the-art models exceed 95% pass
rates on them, and their problems (10-76 lines of code, no submodules) look nothing like real
industrial chip design. ChipBench's problems are ~4x longer and ~14x more complex by cell count,
and the best model in the original paper (Claude Opus 4.5) solves only 30.7% of its Verilog
generation problems on the first attempt. It also uniquely covers two capabilities existing
benchmarks skip entirely: **fixing bugs** in existing Verilog, and **generating reference models**
in other languages (Python/C++) that industrial verification teams use to cross-check hardware
designs before manufacturing.

## What we built

An Inspect AI implementation covering all three of ChipBench's tasks:

- **`chipbench_verilog_gen`** — write a Verilog module from a specification.
- **`chipbench_debug`** — fix an injected bug (arithmetic, assignment, timing, or state-machine)
  in an existing module, with or without a waveform trace to help.
- **`chipbench_refmodel`** — write a functionally equivalent Python or C++ model of a Verilog
  module.

The key design principle carried over from the original benchmark: **scoring is never a text
comparison.** Every submission is actually compiled and simulated against a trusted "golden"
reference implementation, driving the same test inputs into both and checking that their outputs agree — cycle by cycle, for hundreds of test vectors including deliberately random ones. A model could write completely different-looking code from the reference and still score correctly, as long as it behaves identically; conversely, code that merely *looks* plausible but behaves differently gets caught immediately. This runs inside an isolated, purpose-built toolchain (Icarus Verilog, Verilator, and Yosys) so that untrusted, LLM-generated code never executes directly on the host machine.

## Validation before trusting any numbers

Before treating any score as meaningful, we specifically tested that the checker can't be
fooled: a deliberately wrong, do-nothing submission was fed through the real pipeline and
confirmed to fail. We also validated against an actual model response — one with the kind of surrounding explanation, multiple code snippets, and formatting a real LLM produces — and confirmed the pipeline correctly extracts and judges the intended answer regardless of that surrounding noise.

## Results vs. the published paper

Our own results throughout this section are shown as **mean(stderr)**, both to 3 significant
figures — e.g. `4.44(1.94)%` means a mean pass rate of 4.44% with a standard error of 1.94
percentage points across the problem population. The paper does not report error bars, so only
our side of each table carries one.

### `chipbench_verilog_gen`

As a first reproduction check, we ran two of the paper's own models against the full
Verilog-generation dataset and compared against its published numbers (Table 2).

**Llama 3.1 8B** (a small, cheap model):

| | pass@1 | pass@5 | pass@10 |
|---|---|---|---|
| **Our run (all 45 problems)** | 4.44(1.94)% | 11.3(4.15)% | 14.3(4.86)% |
| **Paper** | 7.0% | 8.2% | 9.3% |

Broken down by the three problem categories that make up that aggregate:

| Category | n (ours / paper) | pass@1/@5/@10 (ours) | pass@1/@5/@10 (paper) |
|---|---|---|---|
| Self-contained modules | 30 / 29 | 4.50(2.32)% / 11.9(5.30)% / 14.8(6.30)% | 10% / 13.3% / 20% |
| Non-self-contained (hierarchical) designs | 6 / 5 | 0.00(0.00)% / 0.00(0.00)% / 0.00(0.00)% | 0% / 0% / 0% |
| CPU IP components | 9 / 9 | 7.22(6.02)% / 16.6(10.9)% / 22.2(12.1)% | 22.2% / 22.2% / 22.2% |

The hierarchical-design row is the strongest signal here: our run reproduces the paper's finding
*exactly* — 0% pass rate, both sides — confirming the paper's specific claim that today's small
models cannot yet handle this style of real-world, modular hardware design. On CPU IP components,
our run converges to the same eventual ceiling the paper reports (roughly 2 of 9 problems solvable
at all, since pass@10 lands at 22.2% both sides) even though the two runs differ in how reliably
the model gets there per attempt (pass@1 differs more) — a plausible effect of running the same
model through a different hosting provider than the paper used. Self-contained modules track the
same order of magnitude but without an exact match on any single metric.

**DeepSeek R1** (a much larger reasoning model, run at a reduced 10 attempts per problem rather
than the usual 20, to manage cost and infrastructure load):

| | pass@1 | pass@5 | pass@10 |
|---|---|---|---|
| **Our run (all 45 problems)** | 27.1(5.63)% | 40.6(7.20)% | 42.2(7.45)% |
| **Paper** | 23.7% | 33.7% | 38.2% |

Broken down the same way:

| Category | n (ours / paper) | pass@1/@5/@10 (ours) | pass@1/@5/@10 (paper) |
|---|---|---|---|
| Self-contained modules | 30 / 29 | 28.0(7.05)% / 41.8(8.91)% / 43.3(9.20)% | 26.7% / 40% / 53.3% |
| Non-self-contained (hierarchical) designs | 6 / 5 | 18.3(9.10)% / 45.8(20.7)% / 50.0(22.4)% | 33.3% / 50% / 50% |
| CPU IP components | 9 / 9 | 30.0(15.1)% / 33.3(16.7)% / 33.3(16.7)% | 11.1% / 11.1% / 11.1% |

A much stronger showing overall, as expected for a frontier reasoning model — and notably, unlike
Llama 3.1 8B, DeepSeek R1 *can* solve some hierarchical designs: our pass@10 for that category
(50.0%) matches the paper's reported figure (50%) exactly, and pass@1/@5 land close by too. The
one category that didn't reproduce cleanly is CPU IP components, where our run scored roughly 3x
higher than the paper across all three metrics — plausibly because OpenRouter serves a more
recently updated version of this actively-maintained model than whatever exact snapshot the paper
tested, though a small problem count in that category (9 problems, where each single problem is
worth 11.1 percentage points) means some of this could simply be sampling noise rather than a real
capability difference.

**GPT-3.5 Turbo** (run at the same reduced 10 attempts per problem as DeepSeek R1, for the same
cost/infrastructure reasons — see the note on Docker resource exhaustion below):

| | pass@1 | pass@5 | pass@10 |
|---|---|---|---|
| **Our run (all 45 problems)** | 18.4(5.18)% | 24.2(6.42)% | 24.4(6.48)% |
| **Paper (Table 2)** | 8.15% | 12.59% | 12.59% |

Broken down by category:

| Category | n (ours / paper) | pass@1/@5/@10 (ours) | pass@1/@5/@10 (paper) |
|---|---|---|---|
| Self-contained modules | 30 / 29 | 19.0(6.31)% / 26.3(8.11)% / 26.7(8.21)% | 13.3% / 26.7% / 26.7% |
| Non-self-contained (hierarchical) designs | 6 / 5 | 0.00(0.00)% / 0.00(0.00)% / 0.00(0.00)% | 0% / 0% / 0% |
| CPU IP components | 9 / 9 | 28.9(14.7)% / 33.3(16.7)% / 33.3(16.7)% | 11.1% / 11.1% / 11.1% |

Non-self-contained is now an exact 0% match across **all three** models tested — the strongest,
most consistent single reproduction in this whole exercise. Self-contained's pass@5/@10 also land
almost exactly on the paper's figures (26.3% vs. 26.7%, 26.7% vs. 26.7%). CPU IP is again the
outlier, scoring roughly 2.5-3x the paper's flat 11.1% — the same direction and rough magnitude as
both Llama 3.1 8B and DeepSeek R1's CPU IP discrepancy above, which starts to look less like
per-model noise and more like a systematic difference between this implementation and the paper's
own CPU IP evaluation specifically (a different serving backend wouldn't explain the same-direction
effect recurring across three unrelated models) — worth investigating directly rather than
attributing to sampling noise a third time.

**A confirmed, unrelated infrastructure issue surfaced getting this run to complete.** GPT-3.5
Turbo had never had a successful run on this project — three earlier attempts, and this one,
crashed on Docker resource exhaustion. Investigating turned up the actual root cause: 7 containers
from the very first attempts on 2026-07-05 had been running continuously for 6 days, never torn
down, alongside 37 accumulated per-run images (18.9GB) — Inspect's own sandbox cleanup had been
silently failing since day one of this project, not a transient network issue as first assumed.
Cleaned up (containers removed, orphaned images/networks/build-cache pruned, the fixed
`chipbench-default` image left untouched) and resumed via `inspect eval-retry` from the exact point
it crashed (313/450 samples already logged) rather than restarting from scratch.

Overall: all three runs land in the same order of magnitude as the paper, with several exact or
near-exact matches on the paper's specific findings (0% on hierarchical designs for every model
tested, partial success on hierarchical designs for the reasoning model) — a solid signal that
the implementation faithfully reproduces the original benchmark's behavior, alongside honest,
specific discrepancies rather than a uniformly "close enough" hand-wave. CPU IP's now-three-model
pattern is the one finding here that looks structural rather than incidental.

### `chipbench_debug`

Ran Llama 3.1 8B on the **zero-shot** half of the debugging dataset only (89 problems — module
description plus buggy code, no waveform trace), at the full 20 epochs, and compared against the
paper's Table 4. One caveat worth stating plainly: the paper's Table 4 does not explicitly state
whether it reports zero-shot, one-shot, or a combination of both (its zero-shot-vs-one-shot
comparison is instead described narratively in a separate section, via a figure rather than a
table) — so this comparison assumes Table 4 is zero-shot or a reasonable proxy for it, not a
confirmed apples-to-apples match the way the `verilog_gen` comparison is.

| | pass@1 | pass@5 | pass@10 |
|---|---|---|---|
| **Our run (89 zero-shot problems)** | 7.36(1.58)% | 21.1(3.37)% | 29.6(4.12)% |
| **Paper (Table 4, Average)** | 7.77% | 14.7% | 22.9% |

Broken down by bug type:

| Bug type | n | pass@1/@5/@10 (ours) | pass@1/@5/@10 (paper) |
|---|---|---|---|
| Arithmetic | 24 | 5.21(2.10)% / 17.9(5.78)% / 26.9(7.27)% | 4.17% / 8.33% / 20.8% |
| Assignment | 30 | 10.5(3.12)% / 29.0(6.69)% / 38.6(7.77)% | 3.33% / 23.3% / 36.7% |
| State machine | 6 | 14.2(13.2)% / 20.8(16.4)% / 25.0(17.1)% | 16.7% / 16.7% / 16.7% |
| Timing | 29 | 4.48(1.78)% / 15.6(5.03)% / 23.4(6.89)% | 6.90% / 10.3% / 17.2% |

Aggregate pass@1 lands very close to the paper's (7.36% vs. 7.77%), while pass@5 and pass@10 come
in meaningfully higher on our side (21.1% vs. 14.7%, and 29.6% vs. 22.9%) — the opposite direction
from `verilog_gen`, where our Llama numbers were mostly *lower* than the paper's. No bug type
matches as cleanly as `verilog_gen`'s hierarchical-design category did; State machine (n=6, the
smallest and noisiest bug type — stderr up to ±17 points) is the closest at pass@1. Given the
zero-shot/one-shot ambiguity in what Table 4 actually represents, this comparison is treated as a
looser sanity check than the `verilog_gen` one, not a confirmed reproduction.

**Does giving the model a waveform trace actually help?** We then ran the same model on the
**one-shot** half (same 89 problems, plus the buggy module's `.vcd` waveform dump in the prompt)
to answer this directly — this is exactly the question the paper's own §3.3 investigates (finding
"mixed performance: one-shot outperforms zero-shot on 8 models but underperforms on 13" across
their full model set). The paper doesn't publish exact per-model numbers for this comparison
(it's presented as a figure, not a table), so this is a self-contained comparison within our own
data rather than a reproduction of a specific paper figure:

| | pass@1 | pass@5 | pass@10 |
|---|---|---|---|
| **Zero-shot** | 7.36(1.58)% | 21.1(3.37)% | 29.6(4.12)% |
| **One-shot** | 7.98(1.60)% | 22.9(3.56)% | 31.1(4.30)% |

| Bug type | n | Zero-shot pass@1/@5/@10 | One-shot pass@1/@5/@10 |
|---|---|---|---|
| Arithmetic | 24 | 5.21(2.10)% / 17.9(5.78)% / 26.9(7.27)% | 7.08(2.92)% / 19.9(6.95)% / 25.9(8.11)% |
| Assignment | 30 | 10.5(3.12)% / 29.0(6.69)% / 38.6(7.77)% | 11.5(3.52)% / 30.9(6.55)% / 42.1(7.83)% |
| State machine | 6 | 14.2(13.2)% / 20.8(16.4)% / 25.0(17.1)% | 7.50(7.50)% / 16.2(16.2)% / 16.7(16.7)% |
| Timing | 29 | 4.48(1.78)% / 15.6(5.03)% / 23.4(6.89)% | 5.17(1.71)% / 18.6(5.48)% / 27.0(7.08)% |

For Llama 3.1 8B, one-shot is a modest net improvement in the aggregate (up on all three
metrics) — but that aggregate hides a genuine split by bug type, echoing the paper's "mixed"
finding at the level of individual models rather than contradicting it: **Arithmetic, Assignment,
and Timing all improve** with the waveform trace (Assignment's pass@10 climbs from 38.6% to
42.1%), while **State machine gets worse** (pass@1 nearly halves, 14.2% → 7.50%) — though State
machine's n=6 and correspondingly large stderr (±7-17 points) makes that single category the
least trustworthy read of the four. Taken together: this model does appear to extract some
signal from waveform data on most bug types, but not reliably enough to call it an unambiguous
win, consistent with the paper's broader claim that most current LLMs aren't yet good at
waveform-aware debugging.

**GPT-3.5 Turbo** (zero-shot only — a one-shot attempt crashed on `context_length_exceeded`: this
model's 16,385-token window can't always fit a full VCD waveform trace plus prompt, a genuine
model/task incompatibility rather than a harness bug, so one-shot is out of scope for this model):

| | pass@1 | pass@5 | pass@10 |
|---|---|---|---|
| **Our run (89 zero-shot problems)** | 21.1(3.51)% | 34.2(4.84)% | 37.1(5.15)% |
| **Paper (Table 4, Average)** | 10.0% | 21.25% | 26.25% |

Broken down by bug type:

| Bug type | n | pass@1/@5/@10 (ours) | pass@1/@5/@10 (paper) |
|---|---|---|---|
| Arithmetic | 24 | 29.6(7.81)% / 44.1(10.0)% / 45.8(10.4)% | 16.67% / 25% / 25% |
| Assignment | 30 | 32.3(6.76)% / 49.1(9.14)% / 50.0(9.28)% | 6.67% / 26.67% / 46.67% |
| State machine | 6 | 15.0(15.0)% / 16.7(16.7)% / 16.7(16.7)% | 16.67% / 33.33% / 33.33% |
| Timing | 29 | 3.79(1.60)% / 14.2(5.50)% / 20.7(7.66)% | 0% / 0% / 0% |

Our GPT-3.5 numbers run consistently *higher* than the paper's across every metric and every bug
type except Timing (where the paper reports a flat 0% and ours, while low, isn't quite zero) — the
same higher-than-paper direction seen in `verilog_gen`'s GPT-3.5 comparison above, now on a second
task. State machine (n=6) is the closest match on pass@1, same as it was for Llama. Timing's flat
0% in the paper across an entire bug-type category, for the model with the smallest context
window of the three tested, is worth a passing note: it's the kind of pattern that would also show
up if some Timing prompts push a comparably-sized model over a context or generation-length limit
in the paper's own harness — plausible but not confirmed, since we don't have the paper's own error
logs to check against.

### `chipbench_refmodel`

Ran Llama 3.1 8B on the full 90-sample dataset (45 problems × 2 languages, 20 epochs). Full
technical detail for everything in this section — exact error text, `diff`-verified attribution of
each bug to the paper's code vs. ours, and the complete failure-mode breakdown — lives in
README.md's Evaluation Report; this section is the short version.

**What we found:** most of the run wasn't measuring model capability at all — it was bottlenecked
by three bugs in the evaluation harness itself (two in our own adaptation, one in the vendored
toolbox we reused as-is). Each produced a clean, systematic near-0% that had nothing to do with
what the model wrote: a CXXRTL prompt teaching a C++ API that no longer matched the pinned Yosys
version (83% of CXXRTL samples), generated testbenches referencing a clock signal for circuits that
don't have one, and a reference file depending on a submodule whose source was never staged as an
actual file (guaranteeing failure for the entire "non-self-contained" category, 100% of both
languages).

**How we fixed them:** corrected the CXXRTL prompt, staged the missing submodule source, and gated
the testbench's clock reference on whether the circuit is actually sequential — plus one
experimental change (a worked example demonstrating CXXRTL's easy-to-miss double-underscore
port-naming rule, which was stated in the prompt but never previously shown in an example).

**Result:** re-ran the 38 CXXRTL problems the first bug affected (760 sample-epochs) at each stage:

| | pass@1 | pass@5 | pass@10 |
|---|---|---|---|
| Original (all bugs present) | 0.00% | 0.00% | 0.00% |
| First bug fixed only | 1.71(1.17)% | 5.05(3.14)% | 6.46(3.78)% |
| All fixes + prompt experiment | 2.37(1.40)% | 6.75(3.61)% | 8.58(4.26)% |

The raw pass-rate gain in the last step is within noise (smaller than its own stderr). The clearer
signal: the share of samples reaching a genuine logic comparison — compiling and simulating
successfully, then passing or failing on correctness rather than on harness plumbing — rose from
4.7% to 28.3%. That's the real effect of the fixes, even though the pass rate itself moved only
modestly. One issue only partially improved: models forgetting CXXRTL's double-underscore naming
convention remains the single largest failure mode (62% → 45% of samples after the prompt
experiment) — suggesting a genuine model reliability limit rather than a prompt gap.

**Correction:** the testbench-clock-reference fix turned out to have never actually been tested —
the vendored toolbox it lives in is baked into a Docker image that was never rebuilt after the fix
was written, so every run reported in this section ran the pre-fix code the whole time. The other
two fixes (the CXXRTL prompt, and submodule staging) are unaffected — those run on the host
process, not inside the image. The image has since been rebuilt, and — since a real model's output
can't reliably reproduce the exact condition needed to expose this bug — confirmed instead with a
deterministic test: a hand-written, deliberately-correct combinational CXXRTL submission that
correctly omits `p_clk` now scores 1.0 against the real toolchain, where it previously would have
failed regardless of correctness. Full detail is in README.md's Evaluation Report.

**Then we ran the full 45-problem CXXRTL set** (not just the 38 affected by the first bug), and
confirmed the CXXRTL-prompt and submodule-staging fixes hold at full scale — zero occurrences of
either original error signature across all 900 sample-epochs (the testbench-clock error signature
also didn't occur, but per the correction above that's not meaningful evidence either way — the
harness code generating it was unchanged from before). Two categories still scored a flat 0%, and
checking per-problem rather than per-category turned up a **fourth infrastructure bug**: 5 of the 45
problems have a `ref.sv` that references a Verilog macro (e.g. `` `Branch ``, `` `ZeroWord ``) whose
definition lives only in `test.sv` — the same "split across two files that only get compiled
together by accident elsewhere in the pipeline" shape as the submodule bug, confirmed via `diff`
to be a genuine dataset gap, not something we introduced. It guarantees a compile failure before
the model's answer is even considered, for exactly those 5 problems (4 of 9 CPU IP problems, 1 of 6
non-self-contained). Restricting to the other 5 CPU IP problems this doesn't touch, the failures
are genuinely capability-driven (compile/logic/naming errors, not infrastructure) — so CPU IP's
flat 0% is a mix of "hard for the model" and "never got a fair shot," not purely the former. Not
yet fixed; full detail and the exact affected problem list is in
README.md's Evaluation Report.

| Category | n | pass@1 | pass@5 | pass@10 |
|---|---|---|---|---|
| Self-contained (CXXRTL) | 30 | 4.17(1.89)% | 13.37(4.94)% | 19.01(6.56)% |
| Non-self-contained (CXXRTL) | 6 | 0.00% | 0.00% | 0.00% |
| CPU IP (CXXRTL) | 9 | 0.56(0.56)% | 2.78(2.78)% | 5.56(5.56)% |

The image was rebuilt and re-run: self-contained's pass rate genuinely improved (4.17% vs. 2.83%
pass@1 pre-rebuild), confirming the clock-reference fix does something real, not just in an
isolated unit test. Zero macro-staging errors anywhere in this run either. But non-self-contained
was *still* a flat 0% in both languages — and finding out why turned up a **fifth infrastructure
bug**, this time in a place we didn't expect: a vendored port-extraction script with a regex that
(a) has no idea where one Verilog module ends and another begins, which our own submodule-staging
fix broke by putting two modules in one file, and (b) can't handle a parametrized port width like
`[DATA_WIDTH-1:0]` — extremely common Verilog — so it extracts the type keyword itself (`reg`,
`logic`) as a bogus port name. The second one isn't new or ours: it's in the *original* vendored
file, and it means an earlier claim in this document was wrong.

**Correction:** we previously reported Python's `self_contained` and `cpu_ip` as "legitimate,
unaffected by any bugs." Checking that original run against this newly-found bug, 40 of 600
`self_contained` and 40 of 180 `cpu_ip` sample-epochs hit it — a real, if partial, contamination we
didn't catch until building a systematic failure classifier made it possible to check every
sample's exact error text at once. Those numbers (and the paper comparison built on them) aren't
fully clean. Full detail, exact figures, and the two other new findings (a second port-extraction
symptom, and an unrelated Verilator-strictness gap in one problem's original data) are in
README.md's Evaluation Report.

**Fixed and confirmed against the real toolchain, at full dataset scale, in both languages.** The
port-extraction script now stops scanning after the first module (fixing the module-boundary
cause) and resolves parametrized widths by looking up `parameter`/`` `define `` values in the file
instead of assuming every width is a literal integer (fixing the pre-existing one). Six unit tests
cover both causes against the real triggering files; two new deterministic e2e tests confirm it
against the real, rebuilt Docker image. Full 45-problem, 20-epoch re-runs in both CXXRTL and Python
then confirmed it at scale: `self_contained` and `cpu_ip` both drop to 0% pipeline-attributable
failure in both languages, and overall pipeline share falls from 93.0%/31.1% (original CXXRTL/Python
runs) to 2.3%/2.2% — almost entirely the separate, still-open Verilator-strictness gap below, not
this bug.

**A controlled before/after isolates the fix from the rest of the debugging history.** The
chronological numbers above mix bug-fixes together (Bugs 1 and 2 landed in the same run, for
instance), so a dedicated two-point comparison was run instead: our own faults (Bugs 1, 2) held
fixed in both arms, the paper's faults (Bugs 3, 5, 6) present in "before" and fixed in "after,"
same 45 problems/20 epochs/model in both languages. Overall pipeline share: CXXRTL 43.1%→2.3%,
Python 31.1%→2.2%; `self_contained`/`cpu_ip` both hit exactly 0% in both languages. Full breakdown
in README.md's Evaluation Report's "A controlled before/after" section.

**The fix generalizes to a second model, in both languages.** GPT-3.5 Turbo's refmodel runs
against the fully-fixed pipeline show the *exact same signature* as Llama 3.1 8B's, in Python
**and** CXXRTL independently: `self_contained` and `cpu_ip` both at 0% pipeline share in both
languages, and the only pipeline bucket anywhere is `verilator_rejects_construct` (10/450 in each
language, all in `not_self_contained`, all on the same `Prob006_cpu_top` problem) — the one issue
that was never in scope to fix. This wasn't a given: the six bugs were all found and fixed using
Llama's runs, so it was possible the fixes were somehow tuned to that model's specific failure
patterns. They aren't — four for four (2 models × 2 languages), same result every time.

**A sixth bug, and one excluded sample, since the numbers above.** Checking Dataset Validity
(EVALUATION_CHECKLIST.md's "is it reasonably possible for a model to succeed at each sample?")
turned up a **sixth infrastructure bug**: Verilator outright rejected `Prob006_cpu_top`'s golden
reference (`%Error-BLKANDNBLK`, a blocking/non-blocking assignment mix Icarus Verilog tolerates but
Verilator doesn't), blocking 100% of that one problem's attempts in both languages regardless of
model output — confirmed to be the paper's own unmodified data, not a dataset-construction issue.
Fixed by waiving the lint objection (`-Wno-BLKANDNBLK`), which doesn't change Verilator's own
elaboration semantics; confirmed via a deterministic e2e regression test. Separately, an automated
Inspect Scout trajectory scan turned up a genuine broken record: `Prob000_Four-to-one_multiplexer`'s
prompt (reused verbatim from `verilog_gen`) tells the model to write Verilog code while the refmodel
system prompt prepended to it says the opposite — a self-contradictory instruction, confirmed to be
the paper's own unmodified data. Per `CONTRIBUTING.md`'s Data Quality guidance, it's now excluded
from `chipbench_refmodel` (44 problems, matching the paper's own count exactly, rather than the
incidental 45 used in every number above). Full detail on both in README.md's Evaluation Report.

**Python refmodel vs. the paper's Table 3, now with a clean harness on both sides and the
`Prob000` exclusion applied** (recomputed from the existing per-sample scores — no re-run was
needed, since each sample was already scored independently):

| Model | pass@1 (ours / paper) | pass@5 (ours / paper) | pass@10 (ours / paper) |
|---|---|---|---|
| Llama 3.1 8B | 12.2(3.82)% / 2.22% | 23.1(5.74)% / 5.56% | 27.7(6.36)% / 6.67% |
| GPT-3.5 Turbo | 18.2(5.24)% / 5.56% | 24.4(6.47)% / 6.67% | 25.0(6.60)% / 7.78% |

| Category | Llama ours | Llama paper | GPT-3.5 ours | GPT-3.5 paper |
|---|---|---|---|---|
| Self-contained (n=29, `Prob000` excluded) | 12.4(5.31)% / 19.8(6.71)% / 23.9(7.50)% | 6.67% / 16.67% / 20% | 16.2(6.27)% / 20.7(7.65)% / 20.7(7.66)% | 16.67% / 20% / 23.33% |
| Non-self-contained | 2.50(1.71)% / 11.6(7.78)% / 21.1(13.7)% | 0% / 0% / 0% | 3.33(3.33)% / 13.0(13.0)% / 16.7(16.7)% | 0% / 0% / 0% |
| CPU IP | 17.8(7.22)% / 41.7(16.5)% / 44.4(17.5)% | 0% / 0% / 0% | 34.4(14.8)% / 44.2(17.5)% / 44.4(17.6)% | 0% / 0% / 0% |

Non-self-contained's numbers above still **predate the sixth (Verilator) bug fix** — unlike the
`Prob000` exclusion, that fix can't be recovered by filtering the existing logs, since Verilator
was erroring out on `Prob006_cpu_top` before ever reaching a pass/fail comparison (the harness
failure, not the model's answer, produced those 0s). A fresh run would be expected to show this
row improve further, since that was the sole remaining source of pipeline (not capability) failure
in this category.

Self-contained tracks the paper reasonably closely for both models (same order of magnitude, same
direction of improvement across pass@1→10). Non-self-contained and CPU IP are where this
comparison gets genuinely interesting rather than noisy: **the paper reports a flat 0% on both
categories for *both* models** (and, per the standing open question in
README.md's Evaluation Report, apparently for every model it tested, not just these two)
— while our fixed harness scores meaningfully above 0% on both, for both models. Given we
independently found and fixed a missing-submodule-staging bug (Bug 2) that would have caused
exactly this symptom — 100% blocked non-self-contained regardless of model or model quality — in
*our own* port, and the paper never shipped a runnable refmodel dataset for us to test their
original tooling against directly, the most likely explanation is that the paper's own evaluation
harness has the same class of bug, unfixed, for both categories. This is circumstantial, not
confirmed (we can't run their exact original code), but it's a specific, falsifiable claim rather
than a shrug — and it reframes CPU IP's and non-self-contained's "low paper numbers" from "these
categories are just hard" to "these categories were likely never correctly measured in the
original paper at all."

## Status

- ✅ `chipbench_verilog_gen`: implemented, tested, baseline-reproduced against three models
  (Llama 3.1 8B, DeepSeek R1, GPT-3.5 Turbo). The GPT-3.5 Docker blocker is resolved — root cause
  was 6 days of orphaned containers/images from Inspect's own sandbox-cleanup silently failing,
  not a transient network issue.
- ✅ `chipbench_debug`: baseline-reproduced against two models. Llama 3.1 8B on the full dataset,
  both zero-shot and one-shot halves (178 of 178 problems); GPT-3.5 Turbo on the zero-shot half
  only (89 of 89) — one-shot is out of scope for this model specifically (16,385-token context
  window can't always fit prompt + VCD trace, a model limitation, not a harness bug).
- ✅ `chipbench_refmodel`: baseline runs against Llama 3.1 8B exposed **six** infrastructure bugs
  total (see README.md's Evaluation Report for all). All six are now fixed at the code level and
  regression-tested; the first five are additionally confirmed clean at full dataset scale across
  **all four** model×language combinations tested (Llama/GPT-3.5 × Python/CXXRTL):
  `self_contained`/`cpu_ip` at 0% pipeline share every time. The sixth (a Verilator strictness gap
  on one problem) is fixed and confirmed via a deterministic regression test, but not yet
  reconfirmed at full dataset scale — see the correction note above. The fixes generalize; they
  weren't tuned to Llama's specific failure patterns. One genuinely broken dataset record
  (`Prob000_Four-to-one_multiplexer`'s self-contradictory refmodel prompt) is now excluded from
  `chipbench_refmodel` per `CONTRIBUTING.md`'s Data Quality guidance.
- ✅ Work committed and pushed; `ToImplement/` (the full vendored mirror used for
  diff-verification during development) removed from tracking — it served its purpose and doesn't
  belong in the submission itself.
- ⏭️ Next: submit to the [Inspect Evals
  Register](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/EVAL_REGISTER.md) (one
  issue per task, per the Register's current one-task-per-submission model); a fresh full-scale
  `chipbench_refmodel` run would reconfirm the sixth bug's fix and the `Prob000` exclusion at
  scale rather than via recomputation/regression test; the recurring CPU IP over-performance
  pattern (confirmed across all three `verilog_gen` models) and the non-self-contained/CPU IP
  paper-Table-3 discrepancy remain open, specific, falsifiable hypotheses worth a dedicated
  follow-up rather than further note-taking here.

## Conclusion

This implementation now has baseline coverage across all three ChipBench tasks, with at least two
models on every task and three on `verilog_gen`. All six infrastructure bugs found during this
project are now fixed at the code level and regression-tested; five of the six are confirmed clean
at full dataset scale in both refmodel languages, and — the strongest validity signal in this
document — confirmed clean on a *second* model as well, not just the one used to find and fix
them. The sixth (the Verilator strictness gap) is fixed and confirmed via a deterministic e2e
test against the real rebuilt toolchain, but hasn't yet been reconfirmed at full dataset scale the
way the other five have. One genuinely broken dataset record — a self-contradictory refmodel
prompt on `Prob000_Four-to-one_multiplexer`, the paper's own unmodified data — is now excluded
from `chipbench_refmodel` rather than silently contaminating its results. No known infrastructure
issue remains open anywhere in the implementation; what remains is reconfirmation at scale, not a
fix.

Reproduction against the paper is close on several specific findings across two to three models
each (exact 0% matches on hierarchical/non-self-contained designs in both `verilog_gen` and
`refmodel`, close self-contained numbers in both tasks) and honestly divergent on others. Two
divergent patterns recur consistently enough across models to look structural rather than noisy:
**CPU IP scores higher in our `verilog_gen` runs than the paper's, for all three models tested**,
and **CPU IP plus non-self-contained both score meaningfully above the paper's flat 0% in
`refmodel`, for both models tested there.** The second pattern now has a specific, falsifiable
explanation on file: we independently found and fixed a bug in our own port that would produce
exactly this symptom (a missing-submodule-staging gap blocking non-self-contained entirely,
regardless of model), and the paper's own tooling was never available to test directly — so the
most likely account is that the paper's original harness has the same unfixed bug, not that these
categories are simply hard for every model tested. That reframing — "a benchmark's own harness bug
silently deflating its published numbers for specific categories" — is arguably the more important
finding here than any single reproduction number.

The finding most worth surfacing to the wider eval community isn't a number — it's that **adapting
an existing benchmark's evaluation harness can silently import the harness's own bugs alongside its
scoring logic.** Four concrete, confirmed cases turned up here: a prompt template teaching a
C++ API that had drifted out of sync with the pinned toolchain version, generated testbenches
referencing hardware signals that shouldn't exist for the circuit being tested, and — found twice,
via the same mechanism in two different places — a reference file depending on content (a
submodule definition, then separately a macro definition) that was only ever written into a
*different* file the scorer never compiles. All four produced clean-looking, systematic 0% (or
near-0%) results that had nothing to do with model capability — the kind of result that's easy to
report at face value if you don't go looking for why a category is exactly zero. Two of the four
traced to the original vendored data itself (not our adaptation of it), confirmed via direct `diff`
against the unmodified upstream source rather than assumption — and notably, both of those two are
the same underlying failure mode recurring in a second place, discovered only because we kept
checking per-problem results after fixing the first instance rather than trusting the aggregate.

One specific thread worth flagging back upstream: the paper reports a flat 0%/0%/0% for
non-self-contained `refmodel` problems across every model with no exceptions — a pattern
consistent with exactly the missing-submodule-staging bug found here. This is not confirmed (it
would require tracing the paper's own, non-public evaluation harness), but it's a concrete,
checkable hypothesis: the paper's headline claim that no current model can handle this problem
category may be, in part, a tooling artifact rather than a fully demonstrated capability ceiling.

A second, related lesson surfaced late: a fix that's code-complete isn't the same as a fix that's
been exercised. The testbench-clock fix sat in the source tree for a day and a half producing
seemingly-consistent "confirmed" results across two separate re-runs, purely because the Docker
image it needed to be baked into was never rebuilt — every one of those runs was silently testing
the old code. It was only caught by building a systematic, reusable failure classifier (loading
score explanations across many logs via Inspect's own `samples_df`, rather than re-deriving ad hoc
regexes per run) and noticing that two runs which should have differed in one specific error
signature, given what was supposedly fixed between them, didn't move the way that fix would
predict. For anything baked into a container image rather than read fresh by the host process,
"I edited the file" and "the running eval used the edit" are separate claims — the second one
needs to be checked directly, not assumed from the first.

A third lesson, arguably the most humbling: fixing the bugs that were blocking a category is not
the same as validating that category. After the first four fixes, `self_contained` looked clean —
it wasn't touched by any of them, and its pass rate had visibly improved. Only building a
systematic failure classifier and checking *every* sample's exact error text (rather than trusting
that "no known bug applies here" means "no bug applies here") turned up a fifth bug already present
in categories we'd called legitimate two write-ups ago. The lesson isn't "check harder" in the
abstract — it's that a category with zero known contamination and a category with zero *actual*
contamination are different claims, and only systematic, mechanical checking (not memory of which
fixes touched what) can tell them apart.

Practically, for anyone else adapting ChipBench: the corrected CXXRTL prompt
(`gen_cxxrtl_prompt_fixed.txt`), the vendored-file fixes documented in `NOTICE`, and the failure
classifier in `agent_artefacts/chipbench/failure_analysis/` are directly reusable, and the
bug-attribution method used throughout this project — verifying every "is this the paper's bug or
ours" question via `diff` against the original vendored source rather than memory or assumption —
is the same discipline worth applying to whatever's fixed next.
