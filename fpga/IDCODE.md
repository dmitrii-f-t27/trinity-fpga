# IDCODE — QMTech XC7A100T (FGG676)

## Raw IDCODE

```
0x13631093
```

## Decoded Fields (IEEE 1149.1)

| Field          | Bits   | Value    | Meaning               |
|----------------|--------|----------|-----------------------|
| Version        | 31:28  | 0x1      | Silicon revision 1    |
| Part Number    | 27:12  | 0x3631   | XC7A100T              |
| Manufacturer   | 11:1   | 0x049    | Xilinx                |
| Required LSB   | 0      | 1        | Valid IDCODE          |

## Part Number Cross-Reference

| Part Number | Device     | Expected IDCODE (ver 1 / ver 0) |
|-------------|------------|---------------------------------|
| 0x362D      | XC7A35T    | 0x0362D093                      |
| 0x3631      | XC7A100T   | 0x13631093 / 0x03631093         |
| 0x3636      | XC7A200T   | 0x13636093 / 0x03636093         |

This board is a QMTech Wukong (package FGG676) carrying an **XC7A100T** die.
Part number 0x3631 decodes to XC7A100T, and IDCODE 0x13631093 matches the
tested value asserted in `t27 cli/dlc10/tests/idcode.rs`. This agrees with the
FPGA SSOT (`t27/fpga/HARDWARE_SSOT.md`). The physically distinct ALINX AX7203
board (package FBG484) carries an XC7A200T die (part 0x3636, IDCODE
0x13636093, see `fpga/openxc7-synth/ax7203_al321.cfg`) — do not confuse the two.

## IR Length

6 bits (standard Xilinx 7-series).

## Detection Command

```bash
openFPGALoader --cable xvc-client --ip 192.168.1.30 --port 2542 --detect
```

Output:
```
found 1 devices
index 0:
	idcode 0x3631093
	manufacturer xilinx
	family artix a7 100t
	model  xc7a100
	irlength 6
```
