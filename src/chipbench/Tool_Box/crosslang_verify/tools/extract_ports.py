import re
import json


# Matches a Verilog sized literal (8'd24, 5'b101, 10'hFF) or a plain integer.
_SIZED_LITERAL_RE = re.compile(r"^\d+'([bdho])([0-9a-fA-F]+)$", re.IGNORECASE)
_BASE = {'b': 2, 'd': 10, 'h': 16, 'o': 8}

_DEFINE_RE = re.compile(r"^\s*`define\s+(\w+)\s+(.+?)\s*$")
_PARAM_RE = re.compile(r'\b(?:parameter|localparam)\s+(\w+)\s*=\s*([^,;\)]+)')
_PORT_RE = re.compile(r'(input|output)\s+(?:reg|wire|logic)?\s*(?:\[([^\]]+)\])?\s*(\w+)')
_SAFE_ARITH_RE = re.compile(r'^[\d\s+\-*/()]+$')


def _parse_int_literal(value):
    """Parse a plain integer or a Verilog sized literal (8'd24). Returns int or None."""
    value = value.strip()
    m = _SIZED_LITERAL_RE.match(value)
    if m:
        base_char, digits = m.groups()
        try:
            return int(digits, _BASE[base_char.lower()])
        except ValueError:
            return None
    if value.isdigit():
        return int(value)
    return None


def _collect_constants(lines):
    """Collect `define macros and parameter/localparam values as a name -> int table.

    Both are needed to resolve non-literal port widths like `[DATA_WIDTH-1:0]`
    (a `parameter`) or `` [`WORD_SIZE-1:0] `` (a macro) -- see README.md's
    Evaluation Report. Only resolves simple literal/sized-literal values, not
    expressions like `$clog2(...)` -- a parameter whose value can't be parsed
    this way is just left out of the table, and any width referencing it
    falls back to the width=1 default below rather than crashing.
    """
    constants = {}
    for line in lines:
        m = _DEFINE_RE.match(line)
        if m:
            name, value = m.groups()
            parsed = _parse_int_literal(value)
            if parsed is not None:
                constants[name] = parsed
            continue
        for name, value in _PARAM_RE.findall(line):
            parsed = _parse_int_literal(value.strip())
            if parsed is not None:
                constants[name] = parsed
    return constants


def _resolve_width_expr(expr, constants):
    """Resolve a width-bracket expression (e.g. "DATA_WIDTH-1:0") to (msb, lsb) ints.

    Returns None if any part can't be resolved to an integer.
    """
    # A macro reference (`WORD_SIZE) is just a name with a leading backtick --
    # strip it before substitution, since the constants table is keyed by the
    # bare name and a stray backtick would otherwise survive substitution and
    # fail the arithmetic-only safety check below.
    expr = expr.replace('`', '')
    parts = expr.split(':')
    if len(parts) != 2:
        return None
    resolved = []
    for part in parts:
        part = part.strip()
        for name, value in constants.items():
            part = re.sub(rf'\b{re.escape(name)}\b', str(value), part)
        if not _SAFE_ARITH_RE.match(part):
            return None
        try:
            # Safe: `part` is pre-validated to contain only digits, whitespace,
            # and + - * / ( ) after substitution -- no names or calls survive.
            resolved.append(int(eval(part, {'__builtins__': {}}, {})))
        except (SyntaxError, ZeroDivisionError, ValueError):
            return None
    return resolved[0], resolved[1]


def extract_ports_from_verilog(verilog_path):
    """Extract ports from Verilog. Returns (inputs, outputs) as [(name, width)].

    Only scans the *first* module in the file -- not the whole file. Some
    refmodel samples stage a required submodule into the same ref.sv
    (see README.md's Evaluation Report); without this scoping, a submodule
    port sharing a name with the top module's would get extracted twice
    (Bug 6a), and a submodule-only port would get bound onto the top-level
    class it doesn't belong to. The paper's own ref.sv files are always
    exactly one module, so this scoping is a no-op for anything not staged
    with an appended submodule.
    """
    with open(verilog_path, 'r') as f:
        code = f.read()

    # Strip single-line and multi-line comments
    code = re.sub(r'//.*?$|/\*.*?\*/', '', code, flags=re.DOTALL | re.MULTILINE)

    all_lines = code.splitlines()
    constants = _collect_constants(all_lines)

    first_module_lines = []
    in_module = False
    for line in all_lines:
        stripped = line.strip()
        if not in_module:
            if re.match(r'\bmodule\b', stripped):
                in_module = True
                first_module_lines.append(line)
            continue
        first_module_lines.append(line)
        if re.match(r'\bendmodule\b', stripped):
            break

    inputs, outputs = [], []

    for line in first_module_lines:
        line = line.strip().rstrip(',')
        m = _PORT_RE.match(line)
        if not m:
            continue
        direction, bracket, name = m.groups()
        width = 1
        if bracket is not None:
            resolved = _resolve_width_expr(bracket, constants) if ':' in bracket else None
            if resolved is not None:
                msb, lsb = resolved
                width = abs(msb - lsb) + 1
            else:
                print(
                    f"extract_ports: could not resolve width [{bracket}] for "
                    f"port {name!r} in {verilog_path}; defaulting to width=1",
                )
        (inputs if direction == 'input' else outputs).append((name, width))

    return inputs, outputs

def extract_ports_from_json(json_path):
    """Extract ports from JSON. Returns (inputs, outputs) as [(name, width)]."""
    with open(json_path, 'r') as f:
        data = json.load(f)

    inputs = [(port['name'], port['width']) for port in data.get('inputs', [])]
    outputs = [(port['name'], port['width']) for port in data.get('outputs', [])]

    return inputs, outputs
