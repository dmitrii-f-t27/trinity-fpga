# 2026-07-07 · MXFP4 BLOCK-LEVEL TIER-E on AX7203

**AGENT**: V (Verdict) + T (Queen, seal) + E (Experience)
**PR**: #249 (merged cc77c58)
**Issue**: #199

## Summary

mxfp4-block — the first **block-level Tier-E cell** in the catalog. All 4 links
of the proof-chain are closed on AX7203 silicon (XC7A200T-FBG484-2).

## Proof-chain

| Link | Value |
|---|---|
| CI-run | `28865563368` SUCCESS (workflow `ax7203-corona-decode-mxfp4-block.yml`) |
| nextpnr routing | clean seed=1 on the first attempt (`--placer heap --router router1`) |
| Bitstream SHA256 | `36acee1b781b92332e3de3ab59ab87d6ac35c19636be026d77bcccf0247b4f13` |
| Bitstream size | 9 730 809 B (XC7A200T-FBG484-2, uncompressed .bit) |
| IDCODE | `0x13636093` (Artix-7 rev 1) — JTAG scan via OpenOCD |
| UART | `HW RESULT: 1056/1056 bit-exact (fails=0)` |
| Test set | 33 blocks × 32 lanes = 1056 representative points |

## What is proven physically

32 × E2M1 element codes + shared E8M0 block-scale → 32 scaled FP32.
The scale is applied as **exponent addition** (a power of two, without a general-purpose
multiplier). This is **real OCP MX mxfp4 semantics**, distinct from
single-element fp4-decode (where block-scale is absent).

### How it differs from fp4 (single-element)

- `fp4` decode: 1 E2M1 code → 1 FP32 (no scaling)
- `mxfp4-block` decode: 32 E2M1 codes + 1 E8M0 scale → 32 FP32 (scaled)

`corona_decode_mxfp4_ax7203.v` (NOT block) — byte-for-byte identical to `corona_decode_fp4_ax7203.v`
(proven by SHA256-diff, SHA mxfp4-single = `1b7773853f983ebdf6d3bcf9e57c29d73bf7d9d0d8dae86b67ac574a3d7de8f5`,
SHA fp4 = `dcee9dec7246c1398ae0525719d067ae70a2953efc4cf905846923075aaad450`),
therefore single-mxfp4 is NOT credited as a separate cell (B-path from the 2026-07-07 fork).
The block-decoder is a separate hardware implementation with genuine novelty.

## Ledger impact

- decode-HW: 53 → **54** (+1, mxfp4-block as a separate cell)
- union: 55 → **56**
- catalog: 83 → **84**
- both axes: 8 / 8 (unchanged)
- SW: 75/0/8 (unchanged)
- compute-HW: 10 (unchanged)

## Engineering lessons of the session

### 1. Routing-cliff = netlist profile, not fan-out width

The 70% forecast for a routing-cliff turned out to be **wrong**. The GF family falls over at N≥24
due to the parametric barrel-shifter in the datapath. The 32-lane mxfp4-block **has no
barrel-shifter** — the scale is implemented as exponent addition (a power of two).
ABC gave ~2094 LUT, router1 found a route at seed=1.

**Routing-friendliness criterion** (confirmed):
- ✅ Fixed-field (binary128, ibm_hfp128, vax_h, mxfp4-block) — they route
- ❌ Barrel-shifter (gf24/32/48/64/96/128, takum32/64) — cliff at N≥24

### 2. macOS AppleUSBFTDI blocks FTDI bulk-write

On Apple Silicon with Full Security, `nvram boot-args="-apple_usb_ftdi"` is **silently
ignored**. Symptom: `libusb_detach_kernel_driver() failed with
LIBUSB_ERROR_ACCESS`. JTAG scan passes (short async-transfers), but `pld
load` hangs on mpsse_flush with a doubling timeout.

**Solution** (what worked):
1. Recovery Mode (hold power during boot on Apple Silicon)
2. Startup Security Utility → **Reduced Security** + "Allow kernel extensions"
3. `sudo nvram boot-args="-apple_usb_ftdi"`
4. `sudo reboot`
5. Physical USB reconnect after every `pld load` (the FPGA does a USB-reset,
   macOS re-matches AppleUSBFTDI without the boot-arg, but with the boot-arg matching
   becomes non-exclusive, and re-opening via libusb works)

Note: even after the boot-arg, `Warn: libusb_detach_kernel_driver() failed`
remains in the OpenOCD log, but **it no longer blocks bulk-write**.

### 3. `/tmp/` on macOS is cleaned on reboot

After every reboot the bitstream disappears. You have to re-download via:
```bash
gh run download 28865563368 -D /tmp/mxfp4_block -n corona-decode-mxfp4-block-bitstream
```

### 4. Two serial nodes after FTDI-unlock

After applying the boot-arg two `/dev/cu.usbserial-*` appear:
- `/dev/cu.usbserial-120` — works for UART (the FPGA responds at 160000 baud)
- `/dev/cu.usbserial-210512180081` — second FTDI interface (CP2102N or channel B)

The host script uses `/dev/cu.usbserial-120` by default — it works.

## Reproduction commands

```bash
# 1. Download the bitstream from the CI artifact
gh run download 28865563368 -D /tmp/mxfp4_block -n corona-decode-mxfp4-block-bitstream

# 2. SHA verify
shasum -a 256 /tmp/mxfp4_block/corona_decode_ax7203.bit
# expected: 36acee1b781b92332e3de3ab59ab87d6ac35c19636be026d77bcccf0247b4f13

# 3. Flash (requires FTDI-unlock via boot-arg + reboot, see lesson 2)
openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" \
  -c "pld load 0 /tmp/mxfp4_block/corona_decode_ax7203.bit" \
  -c "runtest 200000" \
  -c "shutdown"
# expected time: ~78 sec (9.7 MB @ 1 MHz JTAG)

# 4. UART conformance
python3 conformance/mxfp4_block_host_ax7203.py \
  --port /dev/cu.usbserial-120 --baud 160000
# expected output: HW RESULT: 1056/1056 bit-exact (fails=0)
```

## Open issues / Horizon

- [ ] Single-element `mxfp4` (`corona_decode_mxfp4_ax7203.v`) remained in the repo
  as a single-decode example, but is **not credited** as a separate Tier-E cell
  (B-path: physically identical to fp4). Decision: either rename it to
  `corona_decode_fp4_alias_ax7203.v`, or delete it in favor of the block-version.
- [ ] The `-apple_usb_ftdi` boot-arg globally disables FTDI-VCP. If in the future
  FTDI-CDC is needed for other devices — run `sudo nvram -d boot-args`.
- [ ] After a power-cycle of the FPGA the bitstream is lost (volatile). For permanent
  operation an SPI-flash is required (a separate task, not a priority yet).
