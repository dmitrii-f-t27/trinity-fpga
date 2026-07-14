FPGA Vision Self-Test Evidence
==============================
Date:       2026-06-26
Host:       macOS (Brio 100 USB webcam, avfoundation dev [0])
Design:     unknown / last-flashed (gf16_codec_ax7203 suspected)
Board:      ALINX AX7203 (Artix-7 XC7A200T-FBG484-2)
Camera:     Logitech Brio 100 (UVC, VendorID_1133 ProductID_2380)
Photo:      ax7203_vision_selftest_20260626.jpg
Git HEAD:   bc72e8039 (feat(fpga): add uart_rx_probe diagnostic for AX7203)

Method:
  - Capture 8 s @30 fps 1280x720 (auto-exposure settles in ~1 s).
  - Skip first 3 s, crop to LED region (crop=640:340:320:60).
  - Per-frame average luma via ffmpeg signalstats (YAVG).
  - Blink proxy: median crossings across N frames.

Measurement (settled window, LED region):
  - n=25 frames, mean=137.9, min=134.6, max=139.8
  - pk-pk = 5.23 / 255  (sensor noise only)
  - median crossings = 1  (monotonic, no oscillation)

Expected per candidate design (LED0..LED3 active-high, LVCMOS18):
  - blinky_ax7203     -> LED0..3 blink counter  => strong oscillation  (NOT observed)
  - gf16_codec_ax7203 -> led={~rst_n,3'b000}    -> 1 steady LED         (consistent)
  - uart_rx_probe     -> LED1 heartbeat blinks  => oscillation          (NOT observed)

Result: PASS (board alive, steady LEDs, NO blinking)
Conclusion: Board is powered and running a steady-state image; NOT the
blinky. Consistent with the last successfully-flashed gf16_codec bitstream.
UART/JTAG cable (AL321 FT2232H) was NOT connected during this test, so the
closed-loop uart_rx_probe+camera test could not be executed (see plan below).

Closed-loop self-test (pending cable reconnect):
  1. Reconnect AL321 -> verify IDCODE 0x13636093 via OpenOCD.
  2. Flash uart_rx_probe_ax7203.bit (LED0 toggles on uart_rx start-bit).
  3. Host sends N UART bytes (115200 8N1) to FPGA RX pin P20.
  4. Camera captures before/after frames -> LED0 must change state N times.
  5. PASS => host TX reaches FPGA RX (UART path good), regardless of the
     unreliable return path. Then reflash gf16_codec and rerun conformance.
