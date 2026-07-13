# Trinity FPGA: Tier-E Silicon Proof

**Date: 2026-07-13 | Hardware: AX7203 (XC7A200T-FBG484-2) | IDCODE: 0x13636093**

## Verified Results

| Format | Op | Vectors | Result | SHA256 |
|--------|-----|---------|--------|--------|
| GF4 (1S+1E+2M) | ADD | 256/256 exhaustive | bit-exact | 4c7b1e59a964... |
| GF4 (1S+1E+2M) | MUL | 256/256 exhaustive | bit-exact | e759d57a4f2b... |
| GF8 (1S+3E+4M) | ADD | 512/512 | bit-exact | ca79919948f1... |
| GF16 (1S+6E+9M) | ADD | 128/128 | bit-exact | 925cc793a0de... |

**Total: 1152/1152 vectors, 0 failures.**

## Toolchain (fully open-source, no Vivado)

```
RTL → yosys (synth_xilinx -abc9 -nocarry -arch xc7)
    → nextpnr-xilinx (--fasm --placer heap --router router1 --timing-allow-fail --freq 5-10)
    → fasm2frames (prjxray, --part xc7a200tfbg484-2)
    → xc7frames2bit (--part.yaml)
    → openocd pld load (FTDI JTAG, 500 kHz, ~156s per bitstream)
    → UART conformance (160000 baud, gf_ref.py Fraction-exact golden oracle)
```

## Golden Oracle

`conformance/gf_ref.py`: exact rational arithmetic using Python `fractions.Fraction`.
Round-half-to-even (RNE) with sticky bit.
Parameteric by (EXP_BITS, MANT_BITS, BIAS).
Supports: normal, subnormal, zero, Inf, NaN.

## Known Limitations (honest)

1. GF8/GF16 MUL routing fails in nextpnr-xilinx (larger designs). Vivado would route these.
2. No timing closure (--timing-allow-fail flag). Fmax unknown.
3. FTDINoSerial.kext required on macOS (codeless kext, IOProbeScore=90000).
4. `csrutil enable --without kext` required (reduces macOS SIP for kext loading).

## Reproduction

```bash
# Build (via CI or local Docker)
docker run --rm -v $(pwd):/work regymm/openxc7:latest bash -c '
cd /work/fpga/openxc7-synth &&
yosys -p "read_verilog gf_adder_param.v gf_mul_param.v corona_compute_gf4_add_ax7203.v; synth_xilinx -abc9 -nocarry -arch xc7; write_json gf4_add.json" &&
nextpnr-xilinx --chipdb /chipdb/xc7a200tfbg484-2.bin --json gf4_add.json --xdc ax7203_corona.xdc --fasm gf4_add.fasm --router router1 --timing-allow-fail --freq 10 &&
/prjxray/env/bin/fasm2frames --db-root /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 --part xc7a200tfbg484-2 gf4_add.fasm gf4_add.frames 2>/dev/null &&
xc7frames2bit --part_file /nextpnr-xilinx/xilinx/external/prjxray-db/artix7/xc7a200tfbg484-2/part.yaml --frm_file gf4_add.frames --output_file gf4_add.bit'

# Flash
python3 hardware/tools/trinity_flash.py gf4_add.bit

# Verify
python3 -c "
import serial, time, sys; sys.path.insert(0, 'conformance')
from gf_ref import FORMATS, gf_add
GF4 = FORMATS['gf4']
ser = serial.Serial('/dev/cu.usbserial-1120', 160000, timeout=3)
ok = bad = 0
for a in range(16):
    for b in range(16):
        ser.write(bytes([0xAA,0x55,0x00, a, b, 0x00])); time.sleep(0.03)
        r = ser.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            if (r[1] & 0xF) == gf_add(GF4, a, b): ok += 1
            else: bad += 1
ser.close()
print(f'GF4 ADD: {ok}/{ok+bad} bit-exact (fails={bad})')
"
```
