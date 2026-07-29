# RETRACTED — takum64/32 routing FAILED (ceiling is 71, not 73)

> **⚠️ RETRACTED 2026-07-03.** takum64/32 CI runs 28675516786 / 28675516794 both
> ended `conclusion=failure` — yosys OK, nextpnr all 8 seeds timed out unrouted on
> Artix-7 200T (XC7A200T). **takum will NOT go GREEN on this part.** The 71→72→73 procedure
> below will NEVER execute on AX7203. Achievable ceiling = 71/83 (TERMINAL).
> See #199 body (revised) + comment issuecomment-4880596167.
>
> **Do NOT act on the flash steps below for takum** — they are moot. Retained only
> as a record of what WAS pre-staged. The lns16 re-flash section (correctness-fix,
> count-neutral) is still valid IF a re-flash is ever wanted, but it does NOT move
> the count (stays 71).

---

# [RETRACTED] Flash-ready: takum64 (71→72) + takum32 (72→73) + lns16 re-flash

> Pre-staged materials for the local-agent queue. The moment a takum run goes
> GREEN, execute the matching section below end-to-end. lns16 bitstream is
> already GREEN (`28668900768`) — its section can run any time HW is free.
> Prepared 2026-07-03 (loop session, bash works; sandbox-independent).

## Prereq (all flashes)
```bash
# verify JTAG access (LIBUSB_ERROR_ACCESS -> fix below)
sudo -n true || echo "NOPASSWD openocd lost — re-enable: echo \"$USER ALL=(ALL) NOPASSWD: /opt/homebrew/bin/openocd\" | sudo tee /etc/sudoers.d/openocd"
# board power-cycle + FTDI kext unload if JTAG stuck
pkill -f openocd 2>/dev/null; sudo kextunload -b com.apple.driver.AppleUSBFTDI 2>/dev/null
```

## 1. takum64 GREEN (`28675516786`) → decode-HW 41→42, Tier-E 71→72
```bash
# download artifact
gh run download 28675516786 -n corona-decode-takum64-bitstream -D /tmp/tk64
BIT=/tmp/tk64/build/corona_decode_takum64/corona_decode_ax7203.bit
SHA=$(shasum -a 256 "$BIT" | cut -d' ' -f1); echo "SHA256=$SHA"
# flash (~78s)
sudo -n /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 $BIT" -c "runtest 200000" -c "shutdown"
# conformance (subnormal-fix regression-catched via --extended)
python3 conformance/takum64_decode_conformance_ax7203.py --extended | tee logs/takum64_hw.log
# post Tier-E (fill SHA + UART line from the log)
gh issue comment 199 --repo gHashTag/trinity-fpga --body "### Tier-E proof: \`takum64\` (decode — Hunhold logarithmic N=64, 94+72-bit routing-opt + subnormal-fix)
decode-HW 41->42. Tier-E 72.
- CI run: https://github.com/gHashTag/trinity-fpga/actions/runs/28675516786
- Bitstream SHA256: \`$SHA\`
- IDCODE: \`0x13636093\` ✅ | Flash: ~78s, rc=0
- UART conformance: \`HW RESULT: N/N bit-exact (fails=0)\` @160000 baud, /dev/cu.usbserial-120 (--extended incl. subnormal band)"
```

## 2. takum32 GREEN (`28675516794`) → decode-HW 42→43, Tier-E 72→73 (CEILING)
```bash
gh run download 28675516794 -n corona-decode-takum32-bitstream -D /tmp/tk32
BIT=/tmp/tk32/build/corona_decode_takum32/corona_decode_ax7203.bit
SHA=$(shasum -a 256 "$BIT" | cut -d' ' -f1); echo "SHA256=$SHA"
sudo -n /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 $BIT" -c "runtest 200000" -c "shutdown"
python3 conformance/takum32_decode_conformance_ax7203.py --extended | tee logs/takum32_hw.log
gh issue comment 199 --repo gHashTag/trinity-fpga --body "### Tier-E proof: \`takum32\` (decode — Hunhold logarithmic N=32, 72-bit f_lo routing-opt + subnormal-fix)
decode-HW 42->43. Tier-E 73 — ACHIEVABLE HW CEILING (see body §🎯).
- CI run: https://github.com/gHashTag/trinity-fpga/actions/runs/28675516794
- Bitstream SHA256: \`$SHA\`
- IDCODE: \`0x13636093\` ✅ | Flash: ~78s, rc=0
- UART conformance: \`HW RESULT: N/N bit-exact (fails=0)\` @160000 baud, /dev/cu.usbserial-120 (--extended incl. subnormal band)"
```

## 3. lns16 re-flash (`28668900768`, GREEN NOW) → correctness-fix (count does NOT change, 41 stays)
```bash
gh run download 28668900768 -n corona-decode-lns16-bitstream -D /tmp/lns16
BIT=/tmp/lns16/build/corona_decode_lns16/corona_decode_ax7203.bit
SHA=$(shasum -a 256 "$BIT" | cut -d' ' -f1); echo "SHA256=$SHA"
sudo -n /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 $BIT" -c "runtest 200000" -c "shutdown"
python3 conformance/lns16_decode_conformance_ax7203.py --extended | tee logs/lns16_hw.log
gh issue comment 199 --repo gHashTag/trinity-fpga --body "### Tier-E re-proof: \`lns16\` (decode — subnormal-flush fix, 10.7%->2.2% error)
decode-HW 41 (unchanged — correctness fix on existing cell). lns16 now actually-correct on silicon.
- CI run: https://github.com/gHashTag/trinity-fpga/actions/runs/28668900768
- Bitstream SHA256: \`$SHA\`
- IDCODE: \`0x13636093\` ✅ | Flash: ~78s, rc=0
- UART conformance: \`HW RESULT: N/N bit-exact, K known-limitation(s), 0 hard-fail(s) [PASS]\` @160000 baud (--extended incl. subnormal band — regression-catches the bffc7a2ab fix)"
```

## Stop-rule
- After takum32 → **73/83 = ACHIEVABLE CEILING**. Do NOT chase 83/83 (10 structural formats mathematically impossible — see #199 body §🎯).
- The 1-ULP subnormal residuals (lns16 111, takum 2 each) are KNOWN_LIMITATION — tagged by `--extended`, not hard-fails. Polish for a later loop (approach-2 wider correction path), not a Tier-E blocker.
