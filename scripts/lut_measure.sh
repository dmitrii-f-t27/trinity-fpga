#!/usr/bin/env bash
# scripts/lut_measure.sh — pinned, reproducible LUT measurement for the GF family.
#
# WHY THIS EXISTS (research/PAPER_INTEGRITY_ISSUES.md §E2, §G2, §G3):
#   The headline LUT numbers (GF16 ADD=485, GF16 MUL=587, GF16+ MUL=505) are
#   fragile w.r.t. yosys flow and parameter defaults:
#     * gf_adder_param defaults to MANT_BITS=8 (=> GF14, NOT GF16);
#       gf_mul_param defaults to MANT_BITS=9 (=> GF16). Inconsistent defaults.
#     * `-flatten` changes the LUT count 2-3x vs no-flatten.
#     * abc9 is mildly nondeterministic run-to-run.
#   This script removes the ambiguity: it generates an EXPLICIT-E/M wrapper per
#   format (no reliance on module defaults), pins ONE flow, and prints a table.
#   It also fills the W=48..128 MUL gap (paper.tex shows '---' there).
#
# WHAT IT MEASURES:
#   Per format, two cores (gf_adder_param, gf_mul_param) x two flows (flatten,
#   no-flatten). Reports LUT = sum(LUT2..LUT6), plus FF, MUXF7, MUXF8.
#
# USAGE:
#   cd <repo>
#   bash scripts/lut_measure.sh            # all formats, all variants
#   bash scripts/lut_measure.sh 16         # only GF16
# Output: a markdown table on stdout + a machine-readable scripts/lut_measure.out.
#
# REQUIREMENTS: yosys >= 0.50 (paper used 0.63). Artix-7 xc7a200t is the target
# family but `stat` LUT counts are part-agnostic for this comparison.
#
# Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RTL="$REPO/fpga/openxc7-synth"
WRAP="$REPO/scripts/_lut_wrappers"
mkdir -p "$WRAP"

# Format list: "NAME W E M HAS_INF"  (HAS_INF: GF16 reserves all-ones exp => 1, else 0)
# E/M sourced from research/COMPLETE_LUT_TABLE.md and scripts/generate_all_formats.py.
FORMATS=(
  "GF4   4  1  2 0"
  "GF6   6  2  3 0"
  "GF8   8  3  4 0"
  "GF10  10 3  6 0"
  "GF12  12 4  7 0"
  "GF14  14 5  8 0"
  "GF16  16 6  9 1"
  "GF20  20 7 12 0"
  "GF24  24 9 14 0"
  "GF32  32 12 19 0"
  "GF48  48 18 29 0"
  "GF64  64 24 39 0"
)

# Optional single-width filter: bash lut_measure.sh 16
FILTER="${1:-}"

# Generate an explicit-param wrapper that instantiates the parametric core.
# Drives clk=0, rst=0, in_valid=1, out_ready=1 so the registered core's LUT is
# the combinational datapath (FF count will include the out_y/out_valid regs).
gen_wrapper() {
  local core="$1" name="$2" W="$3" E="$4" Mb="$5" Hi="$6"
  local mod="wrap_${name}_${core}"
  cat > "$WRAP/${mod}.v" <<EOF
module ${mod} (input  wire [${W}-1:0] a, input  wire [${W}-1:0] b, output wire [${W}-1:0] y);
    ${core} #(.EXP_BITS(${E}), .MANT_BITS(${Mb}), .HAS_INF(${Hi})) u (
        .clk(1'b0), .rst(1'b0), .in_valid(1'b1),
        .in_a(a), .in_b(b), .in_ready(),
        .out_valid(), .out_y(y), .out_ready(1'b1));
endmodule
EOF
  echo "$WRAP/${mod}.v"
}

# Sum LUT2..LUT6 (+ FF, MUXF7, MUXF8) from yosys stat (yosys logs to stderr).
measure() {
  local core="$1" name="$2" W="$3" E="$4" Mb="$5" Hi="$6" flow="$7"
  local wv; wv="$(gen_wrapper "$core" "$name" "$W" "$E" "$Mb" "$Hi")"
  local src="$RTL/${core}.v $wv"
  yosys -p "read_verilog $src; synth_xilinx $flow; stat" 2>&1 \
    | awk '$2 ~ /^(LUT[2-6]|FDCE|FDRE|MUXF7|MUXF8)$/ && $1 ~ /^[0-9]+$/ {c[$2]+=$1}
           END {lut=c["LUT2"]+c["LUT3"]+c["LUT4"]+c["LUT5"]+c["LUT6"];
                printf "%d\t%d\t%d\t%d", lut, c["FDCE"]+c["FDRE"], c["MUXF7"], c["MUXF8"]}'
}

run_variant() {
  local core="$1" name="$2" W="$3" E="$4" Mb="$5" Hi="$6" flow="$7" label="$8" nodsp="$9"
  local fl="-flatten -abc9 -nocarry ${nodsp} -arch xc7"
  fl="${fl//  / }"   # collapse double spaces (when nodsp empty)
  local res; res="$(measure "$core" "$name" "$W" "$E" "$Mb" "$Hi" "$fl")"
  local lut ff m7 m8
  IFS=$'\t' read -r lut ff m7 m8 <<< "$res"
  printf "| %s | %s | %s | %d | %d | %d | %d |\n" "$name" "$core" "$label" "${lut:-NA}" "${ff:-NA}" "${m7:-NA}" "${m8:-NA}"
  echo -e "${name}\t${core}\t${label}\t${lut:-NA}\t${ff:-NA}\t${m7:-NA}\t${m8:-NA}" >> "$REPO/scripts/lut_measure.out"
}

: > "$REPO/scripts/lut_measure.out"

echo "# GF LUT measurement — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo "Toolchain: yosys \$(yosys -V | head -1)"
echo "Flow ADD: synth_xilinx -flatten -abc9 -nocarry -arch xc7"
echo "Flow MUL: + -nodsp"
echo "LUT = sum(LUT2..LUT6). Params pinned per format (no reliance on module defaults)."
echo
echo "| Format | Core | Flow | LUT | FF | MUXF7 | MUXF8 |"
echo "|--------|------|------|----:|---:|------:|------:|"

for line in "${FORMATS[@]}"; do
  read -r name W E Mb Hi <<< "$line"
  if [[ -n "$FILTER" && "$W" != "$FILTER" ]]; then continue; fi
  run_variant gf_adder_param "$name" "$W" "$E" "$Mb" "$Hi" "-flatten -abc9 -nocarry -arch xc7"      "add-flat"  ""
  run_variant gf_adder_param "$name" "$W" "$E" "$Mb" "$Hi" "-abc9 -nocarry -arch xc7"               "add-noflat" ""
  run_variant gf_mul_param   "$name" "$W" "$E" "$Mb" "$Hi" "-flatten -abc9 -nocarry -nodsp -arch xc7" "mul-flat"  "-nodsp"
  run_variant gf_mul_param   "$name" "$W" "$E" "$Mb" "$Hi" "-abc9 -nocarry -nodsp -arch xc7"          "mul-noflat" "-nodsp"
done

echo
echo "Machine-readable: scripts/lut_measure.out"
echo "Cross-check vs paper.tex:863 (GF16 ADD=485, MUL=587) and research/COMPLETE_LUT_TABLE.md."
