"""
Phase 4 verification / V2 - independent re-run of the reproduction gate (DATA-035).

Runs scripts/phase4/10c_repeated_spatial_cv.py exactly as written, changing only
its output folder, so the original Phase 4 output is not overwritten.

Output: data/phase4/verification/gate_rerun/
"""

SRC = "scripts/phase4/10c_repeated_spatial_cv.py"
OLD = 'OUT_P4 = "data/phase4/modeling/results"'
NEW = 'OUT_P4 = "data/phase4/verification/gate_rerun"'

with open(SRC, encoding="utf-8") as f:
    code = f.read()
assert code.count(OLD) == 1, "output line not found exactly once"
exec(compile(code.replace(OLD, NEW), SRC, "exec"), {"__name__": "__main__", "__file__": SRC})
