# EXPERIENCE: QMTECH XC7A100T LED Mapping + Synthesis + Flash via ESP32 XVC
Date: 2026-05-07
Board: QMTECH XC7A100T-FGG676 (board revision UNKNOWN — not Wukong V1/V2/V3)
Host: macOS ARM (Apple Silicon) via Docker (regymm/openxc7, amd64 QEMU)
Flash: ESP32 XVC server at 192.168.1.30:2542

## Goal
Map physical LEDs to FPGA pins, build open-source synthesis pipeline, flash bitstreams.

## CONFIRMED Truth

### LED Mapping (VERIFIED by static tests 2026-05-07)
| LED | FPGA Pin | Logic | Notes |
|-----|----------|-------|-------|
| D1  | M22      | active-LOW | pin=0 → ON, pin=1 → OFF |
| D5  | R23      | active-LOW | pin=0 → ON, pin=1 → OFF |
| D6  | T23      | active-LOW | pin=0 → ON, pin=1 → OFF |
| D4  | DONE pin | N/A | DONE indicator, ON when FPGA configured (done=true) |

**LED test results (raw data):**

| Test | M22 | R23 | T23 | J26 | J19 | D1 | D4 | D5 | D6 | done |
|------|-----|-----|-----|-----|-----|----|----|----|----|------|
| led_ident (cnt=0) | 0 | 0 | 1 | 0 | 1 | ON | ON | ON | OFF | true |
| test_A (J26=1) | 0 | 0 | 0 | 1 | 0 | OFF | OFF | ON | OFF | false |
| test_B (R23=1) | 0 | 1 | 0 | 0 | 0 | ON | ON | OFF | ON | true |
| test_C (J26+T23=1) | 0 | 0 | 1 | 1 | 0 | ON | ON | ON | OFF | true |
| led_all_on (all=0) | 0 | 0 | 0 | — | — | ON | ON | ON | ON | true |

Deduction: active-LOW confirmed. D5=R23 (test_B), D6=T23 (test_C), D1=M22 (intersection).
D4=ON when done=true, OFF when done=false → DONE indicator LED.

### Clock Pin (UNRESOLVED)
- F22: TRIED, counter does NOT increment → NO clock
- M21: TRIED, counter does NOT increment → NO clock (official Wukong pin)
- Oscillator may not be populated, or board is different revision

### Synthesis Pipeline (WORKING)
Docker image: `regymm/openxc7` (8.7GB, amd64, requires QEMU on ARM Mac)

```
1. yosys -p 'read_verilog <design>.v; synth_xilinx -family xc7 -top <top> -json <design>.json'
2. nextpnr-xilinx --chipdb /chipdb/xc7a100t.bin --json <design>.json --xdc <design>.xdc --write <design>_routed.json --fasm <design>.fasm
3. /prjxray/env/bin/fasm2frames --db-root /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 --part xc7a100tfgg676-1 <design>.fasm <design>.frames
4. xc7frames2bit -part_file /nextpnr-xilinx/xilinx/external/prjxray-db/artix7/xc7a100tfgg676-1/part.yaml -frm_file <design>.frames -output_file <design>.bit
```

### Key Docker paths inside regymm/openxc7
| Tool | Path |
|------|------|
| Yosys | /usr/local/bin/yosys |
| nextpnr-xilinx | /usr/local/bin/nextpnr-xilinx |
| fasm2frames | /prjxray/env/bin/fasm2frames |
| xc7frames2bit | /usr/local/bin/xc7frames2bit |
| prjxray-db | /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 |
| Part YAML | /nextpnr-xilinx/xilinx/external/prjxray-db/artix7/xc7a100tfgg676-1/part.yaml |
| Part name | xc7a100tfgg676-1 |

### Host-side chipdb
`build/vsa_matmul/xc7a100t.bin` — 159MB, mount into Docker at `/chipdb/`

### Flashing (WORKING)
```
cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- \
  --xvc-host 192.168.1.30 flash --board XC7A100T --bitstream <path>
```
- Bitstream size: ~3,825,788 bytes
- Flash time: ~220-230 seconds
- Bit-reversal: per-byte REVERSE_BYTE[256] lookup table
- JTAG sequence: JPROGRAM → INIT_B poll → 120K RTI clocks → JSTART → DONE check

### QMTECH Official Wukong Pinout (for reference — DIFFERENT from our board)
Source: github.com/ChinaQMTECH/QM_XC7A100T_WUKONG_BOARD
| Version | Clock | LED[0] | LED[1] | Reset |
|---------|-------|--------|--------|-------|
| V1 | M21 | ? | ? | H7 |
| V2 | M21 | V17 | V16 | H7 |
| V3 | M21 | G21 | G20 | H7 |

Our board LEDs (M22, R23, T23) do NOT match any Wukong version.
The board may be a different QMTECH product or unreleased revision.

### Files Created This Session
| File | Purpose |
|------|---------|
| fpga/vsa/led_sweep.v + .xdc | 5-pin sweep (J26,T23,R23,J19,M22) |
| fpga/vsa/led_ident.v + .xdc | Counter-based identification |
| fpga/vsa/led_test_a.v | Static: J26=1 only |
| fpga/vsa/led_test_b.v | Static: R23=1 only |
| fpga/vsa/led_test_c.v | Static: J26=1, T23=1 |
| fpga/vsa/led_all_on.v + .xdc | Static: all LED pins LOW (all ON) |
| fpga/vsa/blinky_final.v + .xdc | Counter blink on F22 clock |
| fpga/vsa/blinky_m21.v + .xdc | Counter blink on M21 clock |
| fpga/vsa/clock_scan.v | Multi-clock scanner (not yet synthesized) |

### Clock Signal (CONFIRMED working)
- **M21**: clock present (proved by direct output = dim LED) — `IO_L12P_T1_MRCC_14`
- **F22**: clock present (proved by direct output = dim LED) — `IO_L15N_T2_DQS_ADV_B_15`
- Frequency: unknown (likely 50MHz, standard QMTECH oscillator)

### nextpnr-xilinx BUFG Routing BUG (CRITICAL BLOCKER)
Clock signal reaches I/O pins but does NOT reach flip-flop clock inputs when BUFG is used.

**Symptoms:**
- `assign led = clk_m21` → LED dim (clock present at pin) ✓
- Single T-FF with BUFG auto-insertion + direct clock output → T-FF dim (WORKS, but only with routing error)
- Counter (4+ bits) with BUFG → counter stuck, LEDs static ✗
- Counter without BUFG → counter stuck, LEDs static ✗
- Any design with >1 FF and BUFG → clock doesn't reach FFs ✗

**Root cause:**
- Yosys auto-inserts BUFG via `clkbufmap.cc` for clock signals
- nextpnr-xilinx routes IBUF → BUFG → FF clock pins
- BUFG output does NOT actually reach the FF clock pins (routing bug in chipdb/placement)
- Only works when nextpnr produces routing error "Invalid global constant node" (which accidentally forces fallback routing)

**Attempted workarounds (ALL FAILED):**
- Explicit BUFG instantiation → same result
- BUFR (regional clock buffer) → "no Bels remaining"
- BUFG removed (Python script reconnects IBUF→FF directly) → clock still doesn't reach FFs
- `-nocarry` flag (LUT-based counter) → same result
- Clock on F22 instead of M21 → same result
- `CLOCK_DEDICATED_ROUTE FALSE` removed → same result

**Only working sequential design:** clock_route_test (1 T-FF + direct clock output + BUFG auto + routing error)

### Synthesis Pipeline with BUFG Removal (for reference)
```bash
# 1. Normal Yosys synthesis
yosys -p 'read_verilog design.v; synth_xilinx -family xc7 -top design -json with_bufg.json'
# 2. Python script to remove BUFG and reconnect IBUF output to FF clock pins
python3 remove_bufg.py with_bufg.json no_bufg.json
# 3. nextpnr + bitstream generation
nextpnr-xilinx --chipdb /chipdb/xc7a100t.bin --json no_bufg.json --xdc design.xdc ...
```

## Open Issues
1. **BUFG routing bug in nextpnr-xilinx** — sequential designs with >1 FF don't work
2. **Board identification** — PCB markings needed to identify exact board revision
3. **Alternative toolchain needed** — F4PGA/VPR, Vivado, or fixed nextpnr

## Next Steps (PRIORITY ORDER)
1. Try F4PGA toolchain (uses VPR instead of nextpnr — may fix BUFG routing)
2. Try newer version of nextpnr-xilinx from source (may have BUFG fix)
3. Try Vivado (paid but would verify design correctness)
4. Once sequential design works: synthesize vsa_matmul
5. UART benchmark for VSA matmul
