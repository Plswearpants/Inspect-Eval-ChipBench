# My Contribution

This documents what was changed relative to the official ChipBench implementation
([github.com/zhongkaiyu/ChipBench](https://github.com/zhongkaiyu/ChipBench)) and what was
written from scratch to port it into Inspect AI, with the reasoning behind each piece. See
`NOTICE` for the formal attribution ledger (copyright, license, exact file list) — this doc is
the narrative version, organized by *why* each change exists.

## Modified vendored files

Five files were copied from the official implementation and then patched. Everything else
vendored (`data/**`, and the rest of `Tool_Box/crosslang_verify/**`) is copied verbatim,
unmodified.

### `Tool_Box/crosslang_verify/src/run_verification.py`

- **Links `verilated_threads.o`.** The pinned Verilator version (5.x) requires this at link
  time; the original script was written against an older Verilator that didn't. Without it,
  every `chipbench_refmodel` sample fails to build regardless of the model's answer.
- **Adds `-Wno-BLKANDNBLK` to `VERILATOR_WARNS`.** One problem's golden reference
  (`Prob006_cpu_top`) mixes blocking/non-blocking assignments to the same packed variable across
  `always` blocks — a pattern Icarus Verilog (used for `verilog_gen`/`debug`) accepts but
  Verilator rejects outright. This waives the objection without changing what Verilator itself
  elaborates; without it, this one problem was 100% unsolvable in both refmodel languages, no
  matter what the model produced.

### `Tool_Box/crosslang_verify/src/generate_testbench.py`

- **Gates clock-reference generation behind `is_sequential`.** The original always emitted a
  reference to the DUT's clock member in the generated testbench's warmup code, even for purely
  combinational circuits that correctly have no clock at all. That's a guaranteed compile failure
  for every combinational-circuit submission, independent of whether the model's own code was
  correct.

### `Tool_Box/crosslang_verify/tools/extract_ports.py`

- **Stops scanning after the first module.** Needed once our own submodule-staging logic (see
  `dataset.py` below) started producing `ref.sv` files containing two modules instead of one —
  the original regex had no concept of module boundaries and would merge a submodule's ports
  into the top module's, causing duplicate/incorrect port declarations in the generated
  testbench.
- **Resolves parametrized bit-widths** (`[DATA_WIDTH-1:0]`, `` [`WORD_SIZE-1:0] ``) by looking up
  `parameter`/`localparam`/`` `define `` values in the file. The original assumed every port
  width was a literal integer and would silently mis-extract the type keyword itself
  (`reg`/`wire`/`logic`) as a bogus port name whenever it hit a non-literal width — a bug present
  in the *original* vendored file, predating anything in this port, affecting `self_contained`
  and `cpu_ip` problems too, not just the ones our own submodule-staging change touches.

### `Tool_Box/crosslang_verify/tools/clk.py`

- **Checks every input for a clock signal, not just the first.** The original `is_clk_signal`
  loops over a module's inputs but `return`s unconditionally on the first iteration, so it only
  ever checked whether the *first* port's name contained "clk" — a bug present in the *original*
  vendored file. `Prob006_cpu_top` lists `clk` as its third input (after `inputReady`, `reset_n`),
  so the function concluded the module wasn't sequential, and the generated testbench referenced a
  `clk` local variable that its own (incorrectly-gated) declaration never created — another
  100%-of-attempts block on the same problem the `BLKANDNBLK` fix above addresses, discovered only
  once that first fix let compilation get far enough to reach this one.

## Adapters written from scratch

The official implementation has no notion of Inspect's `Task`/`Dataset`/`Sample`/`Scorer`
abstractions — it's a set of standalone scripts (`sv-generate`, `gen.py`,
`run_verification.py`) invoked from the command line with bespoke arguments, operating on files
on disk. These four files exist to bridge that gap; none of their code is copied from upstream,
though each one calls into or loads vendored content.

### `chipbench.py`

**Why needed**: Inspect requires each evaluable unit to be an `@task`-decorated function
returning a `Task` (dataset + solver + scorer + sandbox + generation config). The official repo
has no equivalent — no single place that says "here is one runnable evaluation." This file
defines the three tasks (`chipbench_verilog_gen`, `chipbench_debug`, `chipbench_refmodel`),
wiring together the dataset loaders, the Docker sandbox, the scorers, and the
`temperature=0.85`/`top_p=0.95` generation config the paper uses — none of which exists as
reusable code upstream.

### `dataset.py`

**Why needed**: Inspect expects a `Dataset` of `Sample` objects (input, target, metadata,
per-sample files). The official implementation just reads raw `{prompt.txt, ref.sv, test.sv}`
triplets off disk ad hoc, tightly coupled to its own scripts' directory conventions — there's no
"give me a structured dataset" API to call. This file:

- Discovers and loads `verilog_gen`/`debug` problems into properly-IDed `Sample`s.
- **Constructs** the `refmodel` dataset at runtime, since the official repo never ships one — its
  `ref_model_gen/` directory is a separate training-data-generation tool on an unrelated corpus,
  not a benchmark dataset. Each sample is built by pairing a `verilog_gen` problem's spec with
  the vendored `gen_{python,cxxrtl}_prompt.txt` system prompt.
- Stages a `not_self_contained` problem's submodule source into its `ref.sv` (`_extract_submodule_source`)
  and stages missing `` `define `` macros a problem's `ref.sv` needs but doesn't itself define
  (`_extract_missing_defines`). Both of these "work for free" in the official pipeline, since it
  compiles the model's answer, `ref.sv`, and `test.sv` together in one invocation, so a missing
  definition in one file is satisfied by another. Inspect's `chipbench_refmodel` scorer compiles
  `ref.sv` in isolation via Verilator, so nothing else supplies these automatically — without
  this staging, every affected sample fails to compile regardless of the model's output.

### `scorers.py`

**Why needed**: Inspect's scoring contract is an `@scorer`-decorated async function taking a
`TaskState`/`Target` and returning a `Score`. The official implementation's scoring logic is
embedded inside its own monolithic scripts rather than exposed as a callable, per-sample scoring
function. This file extracts the model's code from its completion (stripping markdown fences),
invokes the same underlying tools the official implementation relies on (`iverilog`, or the
vendored `crosslang_verify` tool) inside the sandbox, and translates their raw output — a
`Mismatches: X in Y` line, or a process exit code — into Inspect's `CORRECT`/`INCORRECT`
contract.

### `prompts.py`

**Why needed**: loads the vendored prompt text files (`gen_python_prompt.txt`,
`gen_cxxrtl_prompt.txt`) as clean, testable module-level constants, per this project's own
`BEST_PRACTICES.md` guidance (prompt templates should be constants, not inline strings scattered
through the code) — the official repo just references these as flat file paths inside `gen.py`,
with no importable API. Also hosts `CXXRTL_PROMPT_FIXED`, a corrected CXXRTL prompt variant
(see below) offered as an opt-in alternative, not a modification to the vendored default.

## New file, not a modification

### `data/refmodel_prompts/gen_cxxrtl_prompt_fixed.txt`

**Why needed**: the vendored `gen_cxxrtl_prompt.txt` teaches a CXXRTL C++ API
(`override`-based `eval()`, zero-argument `commit()`) that no longer matches the pinned Yosys
v0.60 toolchain's actual generated header — every CXXRTL attempt fails to compile on this
signature regardless of model quality (confirmed: 83% of samples in the original, unfixed run).
This file is a corrected rewrite of the same prompt's virtual-method instructions and examples,
verified directly against Yosys v0.60's `cxxrtl.h`. It's wired in as an *opt-in* variant
(`cxxrtl_prompt_variant="fixed"`) rather than replacing the default, since whether it actually
changes model behavior was itself something worth measuring, not assuming.
