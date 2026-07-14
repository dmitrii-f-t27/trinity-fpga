#!/usr/bin/env python3
"""
fix_tx_race.py — Fix the TX non-blocking-assignment race in corona_compute_*_ax7203.v wrappers.

Problem
-------
~1496 wrappers drive UART TX from a shift register `tx_shift` that is the target of two
conflicting non-blocking assignments inside one always block:

    if(result_ready) begin
        tx_shift <= tx_load;                          // NBA #1 (load)  -- LOSES
    end
    ...
    if(tcnt==0) begin
        if(tbi==9) begin
            if(responding) begin
                ...
                tx_shift <= {8'h00, tx_shift[W:8]};   // NBA #2 (shift) -- WINS (last)
            end
        end
    end

When result_ready and a byte boundary coincide on the same clock, NBA #2 overwrites the
freshly loaded data -> the first byte (0xA5 header) and beyond get corrupted.

Fix
---
Replace the shift-register TX with the buffer+mux pattern already proven in the GF32/GF64
wrappers:

    * N fixed byte registers  tx_buf0 .. tx_buf{N-1}   (loaded once by result_ready,
      with NO conflicting write anywhere else in the block)
    * A read-only `case(tx_idx)` mux selects the current byte into `tsr`.

This completely removes the second `tx_shift <=` assignment, so there is no longer a race.

The script:
    1. Scans every fpga/openxc7-synth/corona_compute_*_ax7203.v
    2. Detects the broken shift-register pattern (tx_shift + tx_load)
    3. Derives TX_LEN / result width and regenerates the TX section as buffer+mux
    4. Writes a .bak backup alongside each modified file
    5. Reports counts of fixed / skipped (already fixed) / skipped (no pattern)

All other logic (RX, frame FSM, compute, result capture) is left untouched.
"""

import os
import re
import sys
import glob
import argparse

SYNTH_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fpga", "openxc7-synth",
)

# --- regexes ---------------------------------------------------------------

RE_TX_LEN = re.compile(r"localparam\s+\[\d+:\d+\]\s+TX_LEN\s*=\s*(\d+)\s*;")
RE_TX_LOAD = re.compile(
    r"wire\s+\[(\d+):0\]\s+tx_load\s*=\s*\{[^;]*\}\s*;"
)
RE_TX_LOAD_BODY = re.compile(
    r"wire\s+\[(\d+):0\]\s+tx_load\s*=\s*\{\s*result_reg\s*,\s*8'hA5\s*\}\s*;"
)
RE_RESULT_REG = re.compile(r"reg\s+\[(\d+):0\]\s+result_reg\b")


def bit_width_for(value):
    """Smallest Verilog reg width that can hold `value`."""
    return max(1, value.bit_length())


def generate_tx_section(tx_len, load_width_bits, original_localparam_line):
    """Build the replacement TX region (everything from the TX_LEN localparam
    line through the closing `end` of the TX always block, i.e. up to endmodule).

    Mirrors the proven GF32/GF64 buffer+mux TX pattern.

    Key: instead of a shift register that suffers two conflicting NBAs, we keep
    the original `tx_load` wire (verbatim width/expression) and slice it into N
    fixed byte registers via a read-only case() mux. The buffers are written
    ONLY by result_ready, so the race is eliminated. Slicing the original
    tx_load preserves its exact zero-extension / truncation semantics, so this
    is faithful for byte-aligned, non-byte-aligned, and oversized-shift cases.
    """
    n = tx_len
    idx_bits = bit_width_for(n - 1)          # width for tx_idx  (holds 0..n-1)
    last_idx = n - 1
    load_msb = load_width_bits - 1           # original tx_load width (-1 for [:0])

    buf_names = ", ".join("tx_buf{}".format(i) for i in range(n))

    out = []
    out.append(original_localparam_line)
    out.append(
        "    // TX: buffer+mux (no conflicting NBA — fixes tx race). "
        "{} bytes sliced from tx_load[{}:0].".format(n, load_msb)
    )
    # Re-declare tx_load with the ORIGINAL width + expression (verbatim copy).
    out.append(
        "    wire [{}:0] tx_load = {{result_reg, 8'hA5}};".format(load_msb)
    )
    out.append(
        "    reg responding; reg [{}:0] tx_idx; reg [7:0] {};".format(
            idx_bits - 1, buf_names
        )
    )
    out.append("    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;")
    out.append("    always @(posedge mclk or posedge rst) begin")

    # ---- reset ----
    rst_inits = " ".join("tx_buf{}<=8'hFF;".format(i) for i in range(n))
    out.append(
        "        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;"
        "tbi<=0;tsr<=10'h3FF;uart_tx<=1;"
    )
    out.append("            " + rst_inits + " end")
    out.append("        else begin uart_tx<=tsr[0];")

    # ---- load buffers on result_ready (single, non-conflicting write) ----
    # tx_bufk <- tx_load[8k+7 : 8k]; tx_load[7:0] is the 0xA5 header byte.
    loads = []
    for i in range(n):
        hi = 8 * i + 7
        lo = 8 * i
        loads.append("tx_buf{}<=tx_load[{}:{}];".format(i, hi, lo))
    out.append("            if(result_ready) begin")
    out.append("                " + " ".join(loads) + " responding<=1; tx_idx<=0;")
    out.append("            end")

    # ---- baud / shift engine, now read-only on the buffers ----
    out.append("            if(tcnt==0) begin tcnt<=BAUD_DIV-1;")
    out.append("                if(tbi==9) begin tbi<=0;")
    out.append("                    if(responding) begin")
    out.append("                        case(tx_idx)")
    for i in range(n):
        out.append(
                            "                            {idx}'d{i}: tsr<={{1'b1,tx_buf{i},1'b0}};".format(
                                idx=idx_bits, i=i
                            )
        )
    out.append("                        endcase")
    out.append(
        "                        if(tx_idx=={last}) responding<=0; "
        "else tx_idx<=tx_idx+1;".format(last=last_idx)
    )
    out.append("                    end else tsr<=10'h3FF;")
    out.append(
        "                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end"
    )
    out.append("            end else tcnt<=tcnt-1;")
    out.append("        end")
    out.append("    end")
    out.append("    ")  # trailing indent before `endmodule`
    return "\n".join(out)


def fix_file(path, dry_run=False):
    """Return a status string: 'fixed', 'already', 'nopaTtern', or 'error: ...'."""
    with open(path, "r") as fh:
        text = fh.read()

    # Must have the broken shift-register pattern.
    if "tx_shift" not in text or "tx_load" not in text:
        return "already" if "tx_buf0" in text else "nopattern"

    m_lp = RE_TX_LEN.search(text)
    m_load = RE_TX_LOAD.search(text)          # any tx_load wire decl
    m_load_body = RE_TX_LOAD_BODY.search(text)  # specifically {result_reg, 8'hA5}
    m_res = RE_RESULT_REG.search(text)
    if not (m_lp and m_load and m_res):
        return "error: could not parse pattern"
    if not m_load_body:
        return "error: tx_load is not {result_reg, 8'hA5} (skipping, unknown layout)"

    tx_len = int(m_lp.group(1))
    load_width = int(m_load.group(1)) + 1     # original tx_load width in bits

    # Sanity: tx_load must be wide enough to supply all TX_LEN bytes.
    if load_width < tx_len * 8:
        return "error: tx_load width {} < TX_LEN*8 {}".format(
            load_width, tx_len * 8
        )
    if tx_len < 2:
        return "error: TX_LEN too small ({})".format(tx_len)

    # Locate the region: from the TX_LEN localparam line up to `endmodule`.
    lp_start = m_lp.start()
    try:
        endmod = text.index("endmodule")
    except ValueError:
        return "error: no endmodule"
    if endmod < lp_start:
        return "error: endmodule before localparam"

    original_localparam_line = m_lp.group(0)
    new_region = generate_tx_section(
        tx_len, load_width, original_localparam_line
    )
    new_text = text[:lp_start] + new_region + text[endmod:]

    if new_text == text:
        return "error: no change produced"

    if dry_run:
        return "fixed(dry)"

    # Backup (only first time; a fixed file won't match the pattern on rerun).
    bak = path + ".bak"
    if not os.path.exists(bak):
        with open(bak, "w") as fh:
            fh.write(text)

    with open(path, "w") as fh:
        fh.write(new_text)
    return "fixed"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dir", default=SYNTH_DIR,
        help="directory holding corona_compute_*_ax7203.v (default: synth dir)",
    )
    ap.add_argument("--dry-run", action="store_true", help="parse only, write nothing")
    args = ap.parse_args()

    pattern = os.path.join(args.dir, "corona_compute_*_ax7203.v")
    files = sorted(glob.glob(pattern))
    if not files:
        print("no corona_compute_*_ax7203.v files under {}".format(args.dir))
        return 1

    counts = {"fixed": 0, "already": 0, "nopattern": 0}
    errors = []
    for path in files:
        status = fix_file(path, dry_run=args.dry_run)
        if status.startswith("fixed"):
            counts["fixed"] += 1
        elif status == "already":
            counts["already"] += 1
        elif status == "nopattern":
            counts["nopattern"] += 1
        else:
            errors.append((os.path.basename(path), status))

    total = len(files)
    print("=" * 60)
    print("TX-race fix summary  (dry-run)" if args.dry_run else "TX-race fix summary")
    print("=" * 60)
    print("  scanned           : {}".format(total))
    print("  fixed             : {}".format(counts["fixed"]))
    print("  skipped (already) : {}".format(counts["already"]))
    print("  skipped (no pat)  : {}".format(counts["nopattern"]))
    print("  errors            : {}".format(len(errors)))
    if errors:
        print("---- errors ----")
        for name, st in errors:
            print("  {} : {}".format(name, st))
    return 0


if __name__ == "__main__":
    sys.exit(main())
