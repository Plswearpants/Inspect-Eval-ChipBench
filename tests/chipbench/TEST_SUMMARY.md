# ChipBench Test Summary

Summary of the test suite in this directory, per `CONTRIBUTING.md`'s
[Testing Standards](../../CONTRIBUTING.md#testing-standards). Covers what
each file tests and the current pass/fail state — not a substitute for
reading the tests themselves, which remain the source of truth.

## Current state

```
54 passed
```

Ran via:

```bash
RUN_SLOW_TESTS=1 PYTHONPATH=src uv run pytest tests/chipbench/ -v
```

- **46 fast tests** (unit tests, no Docker) run in under a second and are
  part of the default `uv run pytest` / `make test` invocation.
- **8 slow tests** (`@pytest.mark.docker`, `@pytest.mark.slow(60)`) are
  end-to-end tests against the real sandboxed toolchain and are skipped by
  default; they require `RUN_SLOW_TESTS=1` (or `pytest --runslow`) and a
  working Docker daemon. All 8 build/reuse the `chipbench-default` image
  (cold build ~5-10 min the first time; cached afterward) and take
  15-25s each once the image exists.

All 54 tests currently pass. No known-failing or `xfail`-marked tests exist
in this suite.

## `test_dataset.py` — 33 tests, unit

Covers `dataset.py`'s sample-construction and staging logic:

- **`verilog_gen_samples`**: a real-example regression test
  (`test_verilog_gen_samples_real_example`), non-emptiness across all three
  categories (`self_contained`, `not_self_contained`, `cpu_ip`), unique
  sample IDs, and the invalid-`category` error message.
- **`debug_samples`**: a real-example regression test, VCD-trace
  inclusion/exclusion by `shot`, non-emptiness across all 8
  `shot`×`bug_type` combinations, and the invalid-`shot`/`bug_type` error
  messages.
- **`refmodel_samples`**: one sample per language per problem, system
  prompt/spec content for the `python` language, that `systemc` is excluded
  (see `prompts.py` for why), and that `Prob000_Four-to-one_multiplexer` is
  excluded (`test_refmodel_samples_excludes_contradictory_prompt`) while
  remaining present in `verilog_gen_samples` (see the `4-B` changelog entry
  in README.md).
- **`_extract_submodule_source`** (Bug 2 fix): extracts a real
  `not_self_contained` submodule, returns `None` when nothing needs
  staging, and confirms `refmodel_samples` actually applies the staged
  source.
- **`_extract_missing_defines`** (Bug 5 fix): extracts real missing
  `` `define `` macros, returns `None` when nothing's missing, ignores
  compiler directives that aren't macro definitions, confirms
  `refmodel_samples` applies staging for both `cpu_ip` and
  `not_self_contained` categories, and confirms `stage_missing_defines=False`
  reproduces the paper's original (unfixed) `ref.sv`/`test.sv` split.

## `test_extract_ports.py` — 6 tests, unit

Covers the vendored, patched `extract_ports.py` (module-boundary scoping
and parametrized-width resolution):

- `test_resolves_parametrized_width_bug_6b` / `test_resolves_arithmetic_width_expression`
  / `test_resolves_macro_based_width`: port widths declared via
  `parameter`, an arithmetic expression, and a `` `define `` macro are all
  resolved to concrete integers rather than mis-parsed.
- `test_ignores_second_module_bug_6a` / `test_real_multi_module_file_no_duplicate_ports`:
  a second module in the same file (the staged submodule case) doesn't
  leak its ports into the top module's.
- `test_unresolvable_width_falls_back_without_crashing`: an unresolvable
  width degrades gracefully instead of raising.

## `test_scorers.py` — 7 tests, unit

Covers `scorers.py`'s code-extraction helper and confirms both scorers are
registered as Inspect `Scorer`s:

- `extract_code`: strips ` ```verilog `, bare, and ` ```python ` fences;
  falls back to the stripped completion when there's no fence; uses the
  first fence when multiple are present.
- `test_iverilog_scorer_is_scorer` / `test_crosslang_verify_scorer_is_scorer`:
  smoke tests confirming the `@scorer`-decorated functions produce valid
  `Scorer` instances.

## `test_chipbench.py` — 8 tests, end-to-end (Docker)

Runs the real sandbox (Icarus Verilog / Yosys-CXXRTL / Verilator via
`crosslang_verify`) against `mockllm/model` with hand-written fixed
completions — one deterministic success/failure path per task, plus a
regression test per infrastructure bug found this project:

| Test | Regression coverage |
|---|---|
| `test_verilog_gen_correct_completion_passes` / `test_verilog_gen_incorrect_completion_fails` | Baseline `chipbench_verilog_gen` scoring, both directions |
| `test_debug_e2e` | Baseline `chipbench_debug` scoring (golden fix scores CORRECT) |
| `test_refmodel_e2e` | Baseline `chipbench_refmodel` scoring (Python) |
| `test_refmodel_cxxrtl_combinational_e2e` | Bug 3 — clock reference no longer emitted for combinational CXXRTL DUTs |
| `test_refmodel_parametrized_width_e2e` | Bug 6b — parametrized port widths (`` [DATA_WIDTH-1:0] ``) extracted correctly, not mis-parsed as a bogus port name |
| `test_refmodel_multi_module_e2e` | Bug 6a — a staged submodule's ports don't collide with the top module's |
| `test_refmodel_blkandnblk_waiver_e2e` | Verilator `BLKANDNBLK` strictness gap on `Prob006_cpu_top` — waived via `-Wno-BLKANDNBLK` |

Each of the six infrastructure bugs found during development (see
README.md's Evaluation Report and `MY_contribution.md`) now has a
deterministic regression test here — a fresh `uv run inspect eval` run
that reintroduced any of them would be caught by this suite before it
reached a real model-scale run.

## Gaps / not covered here

- `chipbench.py`'s `@task` functions themselves (parameter wiring, sandbox
  config, `Epochs`/generation config) are only exercised indirectly, via
  the end-to-end tests calling them with real arguments — there's no unit
  test asserting on `Task` object fields directly. Not flagged as a defect;
  the e2e tests already confirm the wiring works, which is the stronger
  claim.
- `prompts.py`'s prompt-loading constants (`REFMODEL_SYSTEM_PROMPTS`,
  `CXXRTL_PROMPT_FIXED`) aren't tested directly, but their content is
  exercised via `test_refmodel_samples_python_includes_system_prompt_and_spec`
  and the CXXRTL e2e test.
