#!/usr/bin/env python3
"""Do the decode hosts' goldens survive their own formats?

Every `*_decode_conformance_ax7203.py` host answers one question: given a code in
format F, what should the board return? The answer is a 32-bit float pattern, so
the golden has to carry an exact value from F into fp32.

Several of them do that through a Python float:

    v = (1 + m / float(1 << M)) * (2.0 ** (e - BIAS))

which is fine when F fits inside a double and silently wrong when it does not.
gf64 is GF(64, E=24, M=39) with BIAS = 8388607. Its exponent field spans
0..16777215, while a double dies outside roughly 2**-1074 .. 2**1023. So:

  * for almost every exponent the term underflows to 0.0 or raises OverflowError
  * the 40-bit significand is squeezed through a 53-bit double and then a 24-bit
    fp32 -- two roundings where the format's own spec asks for one

This runs each host's own golden over its own code set and reports what happens,
then compares it against an exact reference: the value as a Fraction from the
oracle, rounded once to fp32 with round-half-to-even in integer arithmetic.

No board is needed. A host that raises here cannot complete a run at all.

Usage:  python3 research/audit_decode_host_goldens.py
"""
import os
import re
import sys
import types
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
sys.path.insert(0, CONF)

import gf_ref  # noqa: E402


# gf64's exponent field spans 0..16777215 and gf128's is wider still. Building
# the exact value of a code near either end means a Fraction with a 2**16777215
# in it, and normalizing it by halving in a loop is 16 million iterations of
# ever-growing integers. The first version of this did exactly that and the
# process was SIGKILLed by the OOM killer.
#
# This is the third pass to walk into the wide-exponent trap -- pass 186 named it
# and set MAX_SAFE_EXP, pass 229 hit it again. So: no loop, and no exact value is
# ever requested for a code whose exponent is nowhere near fp32's window.
MAX_SAFE_EXP = 1 << 20
FP32_WINDOW = 300          # binades either side of 2**0 that can matter for fp32

# The local exact_to_fp32 that used to live here could not carry the sign of an
# exact zero -- a Fraction has no -0 -- so it called every negative zero a positive
# one, and reported the one host that gets it right as the one that was wrong.
# conformance/gf_decode_golden.fraction_to_fp32 takes the sign explicitly.
from gf_decode_golden import fraction_to_fp32 as exact_to_fp32   # noqa: E402


def load_host(path):
    """Import a host without pyserial and without running its main()."""
    src = open(path, encoding="utf-8", errors="replace").read()
    for name in ("serial",):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    mod = types.ModuleType("host_" + os.path.basename(path)[:-3])
    mod.__dict__["__name__"] = "host_under_audit"
    mod.__dict__["__file__"] = path
    exec(compile(src, path, "exec"), mod.__dict__)   # noqa: S102
    return mod


HEADER = re.compile(r"^\s*N\s*,\s*E\s*,\s*M\s*,\s*BIAS\s*=\s*(\d+)\s*,\s*(\d+)\s*,"
                    r"\s*(\d+)\s*,\s*(\d+)", re.M)


def main():
    hosts = sorted(f for f in os.listdir(CONF)
                   if f.endswith("_decode_conformance_ax7203.py"))
    rows = []
    for fn in hosts:
        path = os.path.join(CONF, fn)
        src = open(path, encoding="utf-8", errors="replace").read()
        m = HEADER.search(src)
        if not m:
            continue                       # not the N,E,M,BIAS shape this checks
        N, E, M, BIAS = (int(x) for x in m.groups())
        key = fn.split("_decode")[0]
        fmt = gf_ref.FORMATS.get(key)
        try:
            host = load_host(path)
        except BaseException as e:         # noqa: BLE001  -- a host may sys.exit() on import
            rows.append((fn, N, E, M, "load failed: %s" % type(e).__name__, 0, 0, 0))
            continue
        golden = getattr(host, "decode", None) or getattr(host, "golden", None)
        if golden is None:
            rows.append((fn, N, E, M, "no decode/golden", 0, 0, 0))
            continue

        EM = (1 << E) - 1
        MMAX = (1 << M) - 1
        # the exponents these hosts pick for themselves, plus the binade edges
        exps = [0, 1, 2, EM - 1, EM, BIAS, BIAS + 1, max(0, BIAS - 1)]
        mants = [0, 1, MMAX, MMAX // 2]
        raised = wrong = checked = 0
        first_bad = None
        for s in (0, 1):
            for e in exps:
                if not 0 <= e <= EM:
                    continue
                for mv in mants:
                    raw = (s << (N - 1)) | (e << M) | mv
                    checked += 1
                    try:
                        got = golden(raw)
                    except BaseException as ex:        # noqa: BLE001
                        raised += 1
                        if first_bad is None:
                            first_bad = ("e=%d m=%d -> %s" % (e, mv, type(ex).__name__))
                        continue
                    # Only ask the oracle for codes whose value could land inside
                    # fp32's window at all. Outside it, gf_ref.decode would build
                    # 2**(e - BIAS) exactly -- millions of bits for the wide GFs.
                    if fmt is None or abs(e - BIAS) > FP32_WINDOW:
                        continue
                    val = gf_ref.decode(fmt, raw)
                    if not isinstance(val, Fraction):
                        continue                       # a Special: sign/NaN policy is the host's
                    want = exact_to_fp32(val, (raw >> (N - 1)) & 1)
                    if got != want:
                        wrong += 1
                        if first_bad is None:
                            first_bad = ("e=%d m=%d host=%#010x exact=%#010x"
                                         % (e, mv, got, want))
        note = "" if fmt is not None else "no oracle for this format"
        rows.append((fn, N, E, M, note, checked, raised, wrong, first_bad))

    print("%-46s %4s %3s %3s  %6s %7s %7s" %
          ("host", "N", "E", "M", "checked", "RAISED", "wrong"))
    tot_r = tot_w = 0
    for r in rows:
        fn, N, E, M, note = r[0], r[1], r[2], r[3], r[4]
        checked, raised, wrong = r[5], r[6], r[7]
        first = r[8] if len(r) > 8 else None
        tot_r += raised
        tot_w += wrong
        flag = "  <<<" if (raised or wrong) else ""
        print("%-46s %4d %3d %3d  %6d %7d %7d%s"
              % (fn[:46], N, E, M, checked, raised, wrong, flag))
        if first:
            print("      first: %s   %s" % (first, note))
        elif note:
            print("      %s" % note)
    print()
    print("hosts examined            : %d" % len(rows))
    print("goldens that RAISE        : %d" % sum(1 for r in rows if r[6]))
    print("goldens that disagree     : %d" % sum(1 for r in rows if r[7]))
    print("raising evaluations       : %d" % tot_r)
    print("disagreeing evaluations   : %d" % tot_w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
