#!/usr/bin/env python3
"""run_synth.py — yosys synthesis LUT measurement script.
Runs inside Docker (regymm/openxc7) where yosys 0.63 is available.
"""
import subprocess, os, sys

SYNTH_DIR = "fpga/openxc7-synth"
WRAPPERS = "/wrappers"
OUTPUT = "lut_reports/yosys_report.md"

os.makedirs("lut_reports", exist_ok=True)

FORMATS = [
    ("GF4",  1, 2),  ("GF8",  3, 4),  ("GF12", 4, 7),
    ("GF14", 5, 8),  ("GF16", 6, 9),  ("GF20", 7, 12),
]

def run_yosys(verilog_files, flags):
    """Run yosys synthesis, return LUT count."""
    script = f"""
read_verilog {" ".join(verilog_files)}
synth_xilinx {flags}
stat
"""
    result = subprocess.run(
        ["yosys", "-p", script],
        capture_output=True, text=True, timeout=120
    )
    output = result.stdout + result.stderr
    
    lut_count = 0
    in_stat = False
    for line in output.split("\n"):
        if "Printing statistics" in line:
            in_stat = True
            continue
        if in_stat and line.strip() == "":
            if lut_count > 0:
                break
            continue
        if in_stat:
            parts = line.strip().split()
            if len(parts) >= 2:
                cell_type = parts[-1]
                count = int(parts[0])
                if cell_type in ("LUT1", "LUT2", "LUT3", "LUT4", "LUT5", "LUT6",
                                 "MUXF7", "MUXF8"):
                    lut_count += count
    return lut_count

with open(OUTPUT, "w") as f:
    f.write("# Yosys Synthesis LUT Report (pre-P&R)\n")
    f.write(f"Generated: {subprocess.check_output(['date', '-u']).decode().strip()}\n")
    ver = subprocess.check_output(["yosys", "-V"]).decode().strip()
    f.write(f"Tool: {ver}\n")
    f.write("Flags: synth_xilinx -flatten -abc9 -nocarry [-nodsp] -arch xc7\n\n")
    f.write("| Format | W | E | M | ADD LUT | MUL LUT |\n")
    f.write("|--------|---|---|---|---------|---------|\n")

    for name, eb, mb in FORMATS:
        w = 1 + eb + mb
        add_wrapper = f"{WRAPPERS}/{name}_add.v"
        mul_wrapper = f"{WRAPPERS}/{name}_mul.v"

        if not os.path.exists(add_wrapper):
            print(f"  SKIP {name}: wrapper not found at {add_wrapper}")
            continue

        add_lut = run_yosys(
            [add_wrapper, f"{SYNTH_DIR}/gf_adder_param.v"],
            "-flatten -abc9 -nocarry -arch xc7"
        )
        mul_lut = run_yosys(
            [mul_wrapper, f"{SYNTH_DIR}/gf_mul_param.v"],
            "-flatten -abc9 -nocarry -nodsp -arch xc7"
        )

        f.write(f"| {name} | {w} | {eb} | {mb} | {add_lut} | {mul_lut} |\n")
        print(f"  {name} W={w}: ADD={add_lut} MUL={mul_lut}")

print(f"\nReport saved: {OUTPUT}")
