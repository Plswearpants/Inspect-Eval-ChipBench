import re

def is_clk_signal(inputs):
    '''
    Check if any of the module's inputs is a clock signal.
    Returns is_clk
    '''
    # Checks every input, not just the first: a clock signal can appear at any
    # position in the port list (e.g. Prob006_cpu_top lists `clk` third, after
    # `inputReady`/`reset_n`), and returning early on the first non-matching
    # port would misclassify such a module as combinational. See README.md's
    # Evaluation Report.
    for input in inputs:
        if re.search(r'clk', input[0], re.IGNORECASE):
            return True
    return False
