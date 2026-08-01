# 2026-08-01 — TRI-NET: first ternary compute on AX7203 silicon

Board: ALINX AX7203, XC7A200T-2FBG484, IDCODE `0x13636093`.
Programmer: AL321 FT232H on `/dev/cu.usbserial-210512180081`.
UART: on-board CP2102N on `/dev/cu.usbserial-1110`, 160000 baud.

## What was measured

| Cell | Result | Evidence |
|---|---|---|
| `corona_compute_gfternary_mul_ax7203` | **16/16 bit-exact** | CI run `30702513394`, flashed 2026-08-01, `gfternary_compute_conformance_ax7203.py --op mul` |
| `trinet_mac32_ax7203` | simulation 128/128; hardware run pending | CI run `30702638896`, bitstream sha `e476fc03c98c8b4c7f67e310e4d22df392f88d578af3e1326b2762df6a2f86a0` |

Before this session the ternary column of the 83-format matrix had no hardware
entry at all: `corona_compute_gfternary_mul_ax7203.v` had been written but had
never been synthesised, and there was no CI workflow for any ternary cell.

## The bug only silicon could find

`gfternary_compute_conformance_ax7203.py` sent a **seven**-byte request where
the wrapper parses **six**:

```
wrapper : AA 55 fmt a b trig
host    : AA 55 fmt fmt a b trig        <- one byte too many
```

Every operand shifted by one, so the FPGA read `a = 0` for every job and
returned zero. That is the *correct* answer for the seven of sixteen input
pairs whose product is zero, so the first hardware run scored 7/16 with a
perfectly consistent-looking failure pattern. After removing the duplicated
`fmt` byte: 16/16.

The golden oracle's own self-test passed throughout — it never exercised the
wire encoding. This is the fourth RTL/host bug in this program that simulation
could not see, and it lands in the same place as the others: the frame path.

**Rule reinforced:** a conformance host is not verified by its self-test. The
encode/decode path has to be exercised against something that did not come from
the same source file — either the RTL in simulation, or the board.

## A second instance of the same class, caught in simulation

`formal/trinet_mac32_tb.v` read its vector fields with `$fscanf %h`, which packs
the first hex pair into the *high* byte, then transmitted them low byte first —
reversing every multi-byte field. The dot product did not notice, because
reversing the byte order of both operands applies the same permutation to `w`
and `x` and leaves the sum unchanged. Only the CRC-32 over the job bytes caught
it, failing 23 of 24 vectors while vector 0 (all zeros) passed.

**Worth keeping:** adding a checksum over the inputs turned an invisible
permutation bug into an immediate, localised failure. The arithmetic alone was
not a sufficient witness.

## Toolchain notes

- Docker was **not** running locally, so all synthesis went through CI. The
  local path (`regymm/openxc7`) needs the daemon up; CI is the reliable route.
- `sudo -n /opt/homebrew/bin/openocd` was still passwordless this session — the
  `/etc/sudoers.d/openocd` rule survived. Verify it every session; it has been
  lost to a reboot before.
- Flashing 9,730,795 bytes at the AL321's stable 100 kHz takes **778 seconds**.
  Earlier notes claiming ~78 s are wrong by an order of magnitude; budget 13
  minutes per flash and pipeline other work against it.
- openocd's stdout is block-buffered when redirected, so a running flash shows
  an empty log file for its whole duration. An empty file is not a hang.

## Synthesis recipe that worked

`trinet_mac32_ax7203` — 429 LCs, 296 FDCE + 125 FDPE, **zero DSP48**:

```
synth_xilinx -flatten -abc9 -nocarry -nodsp -arch xc7 -top trinet_mac32_ax7203
nextpnr-xilinx --placer heap|sa, seeds 1..8, router1, --freq 50.0
```

A DSP guard that greps the whole yosys log for `DSP48` is a false positive — the
string appears in pass banners. Match the cell-count column instead:
`grep -E '^ *[0-9]+ +DSP48'`.
