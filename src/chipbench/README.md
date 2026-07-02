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
  read from the vendored `Ref Model Gen/` folder, which is a separate
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

TODO: A brief summary of results for your evaluation implementation compared against a standard set of existing results.

## Changelog
