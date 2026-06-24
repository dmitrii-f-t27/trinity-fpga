# ALINX AX7203 — Artix-7 XC7A200T-FBG484-2 board truth
# LiteX-accurate pin assignments verified against ALINX manual
# Clock: 200 MHz differential on R4/T4 — bank uses DIFF_SSTL15 (not LVDS)
# Per LiteX / ALINX schematics; confirmed 2026-06-24.

# Set IOSTANDARD on BOTH P and N pads explicitly for nextpnr-xilinx.
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_n]
set_property PACKAGE_PIN R4 [get_ports clk200_p]
set_property PACKAGE_PIN T4 [get_ports clk200_n]

create_clock -period 5.000 -name clk200 [get_ports clk200_p]

# Active-low CPU reset
set_property IOSTANDARD LVCMOS15 [get_ports rst_n]
set_property PACKAGE_PIN T6 [get_ports rst_n]

# User LEDs (active-high, carrier board)
set_property IOSTANDARD LVCMOS18 [get_ports {led[0] led[1] led[2] led[3]}]
set_property PACKAGE_PIN B13 [get_ports led[0]]
set_property PACKAGE_PIN C13 [get_ports led[1]]
set_property PACKAGE_PIN D14 [get_ports led[2]]
set_property PACKAGE_PIN D15 [get_ports led[3]]

# USB-UART bridge (CP2102)
set_property IOSTANDARD LVCMOS33 [get_ports {uart_tx uart_rx}]
set_property PACKAGE_PIN N15 [get_ports uart_tx]
set_property PACKAGE_PIN P20 [get_ports uart_rx]

# Bank voltage setup
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
