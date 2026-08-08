#!/usr/bin/env python3
"""Is a register narrower than what is compared against it really silent in yosys?

.github/workflows/narrow-register-gate.yml opens by saying so, and cites its
evidence:

    pass 146 confirmed that by running yosys over trinity_v1_morse.v, which
    compared a 25-bit register against 1,500,000,000 and produced zero warnings

yosys cannot read trinity_v1_morse.v. Line 113 is a SystemVerilog assignment
pattern -- `reg [2:0] morse_sequence [0:37] = '{ ... }` -- which the frontend
rejects as OP_CAST, in plain mode and under -sv alike. The version that existed
BEFORE pass 146's own edit fails at the same construct. So the file has never been
readable by yosys, and "produced zero warnings" is what a refused read produces:
zero warnings, because nothing was analysed.

A claim of silence that was really a claim of failure. The premise may still be
true -- it is a fact about the language, not about that file -- but it had no
evidence, so this establishes it directly.

Each case below is a minimal module yosys CAN read, isolating one narrowing:

    compare     25-bit reg compared against 1_500_000_000  (needs 31 bits)
    assign      8-bit reg assigned a 16-bit expression
    slice       4-bit reg assigned bits [7:0] of a wider bus
    port        a 4-bit port driven by an 8-bit wire
    control     the shape the gate actually hunts: a counter compared against a
                constant it can never reach, so the branch is dead

Silence is the ANSWER, not a failure: it is precisely why research/audit_narrow_
register.py has to look for these with its own analysis rather than reading a
tool's warnings. A case that does warn is worth knowing about too, because that
one yosys would have caught for free.

Usage:  python3 research/witness_narrow_register_silence.py [--verbose]
"""
import os
import re
import subprocess
import sys
import tempfile

CASES = [
    ("compare", """
module m(input clk, output reg hit);
    reg [24:0] ctr;
    always @(posedge clk) begin
        ctr <= ctr + 1'b1;
        hit <= (ctr == 32'd1500000000);   // 25 bits vs a value needing 31
    end
endmodule
"""),
    ("assign", """
module m(input clk, input [15:0] wide, output reg [7:0] narrow);
    always @(posedge clk) narrow <= wide;             // 16 into 8
endmodule
"""),
    ("slice", """
module m(input clk, input [31:0] bus, output reg [3:0] q);
    always @(posedge clk) q <= bus[7:0];              // 8 into 4
endmodule
"""),
    ("port", """
module inner(input [3:0] a, output [3:0] y); assign y = a; endmodule
module m(input [7:0] wide, output [3:0] y);
    inner u(.a(wide), .y(y));                          // 8-bit wire, 4-bit port
endmodule
"""),
    ("control", """
module m(input clk, output reg done);
    reg [7:0] frames;
    always @(posedge clk) begin
        frames <= frames + 1'b1;
        done <= (frames == 9'd300);        // 8 bits can never hold 300
    end
endmodule
"""),
]

WARN = re.compile(r"^Warning:", re.M)


def main():
    verbose = "--verbose" in sys.argv
    silent, noisy, broken = [], [], []
    with tempfile.TemporaryDirectory() as d:
        for name, src in CASES:
            p = os.path.join(d, "%s.v" % name)
            open(p, "w").write(src)
            r = subprocess.run(
                ["yosys", "-p", "read_verilog %s; hierarchy -top m; proc; opt" % p],
                capture_output=True, text=True, timeout=300)
            out = r.stdout + r.stderr
            if r.returncode != 0:
                broken.append((name, out.strip().splitlines()[-1][:90]))
                continue
            warns = [w for w in out.splitlines() if w.startswith("Warning:")]
            # yosys emits a housekeeping warning about a wire it optimised away in
            # some of these; only a width-related one counts as "yosys told you".
            width = [w for w in warns
                     if re.search(r"width|truncat|extend|size", w, re.I)]
            (noisy if width else silent).append((name, width[0][:90] if width else ""))
            if verbose:
                print("  %-9s rc=0  warnings=%d  width-related=%d"
                      % (name, len(warns), len(width)))

    print("narrowings that yosys reports nothing about : %d" % len(silent))
    for n, _ in silent:
        print("      %s" % n)
    if noisy:
        print("narrowings yosys DOES warn about            : %d" % len(noisy))
        for n, w in noisy:
            print("      %-9s %s" % (n, w))
    if broken:
        print("cases yosys could not read (fix the case)   : %d" % len(broken))
        for n, e in broken:
            print("      %-9s %s" % (n, e))

    print()
    if silent and not broken:
        print("Silence confirmed on %d of %d narrowings, on modules yosys can actually"
              % (len(silent), len(CASES)))
        print("read -- which trinity_v1_morse.v never was. This is why")
        print("research/audit_narrow_register.py must find these itself.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
