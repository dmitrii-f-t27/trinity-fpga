`default_nettype wire

// =============================================================================
// blinky_ax7203 — minimal bring-up for ALINX AX7203 (XC7A200T-FBG484-2)
// =============================================================================
// Phase-0 design: IBUFDS on 200 MHz LVDS clock, active-low reset, 4 LEDs.
// NO PLL/MMCM — eliminates PLL lock as a failure mode during board bring-up.
// Counter runs directly from 200 MHz; LED[0] toggles at ~3 Hz.
// phi^2 + 1/phi^2 = 3 = TRINITY
// =============================================================================

`timescale 1ns / 1ps

module blinky_ax7203 (
    input  wire clk200_p,
    input  wire clk200_n,
    input  wire rst_n,
    output wire [3:0] led,
    output wire uart_tx,
    input  wire uart_rx
);

    wire clk200_raw;
    IBUFDS clk_ibufds (
        .I  (clk200_p),
        .IB (clk200_n),
        .O  (clk200_raw)
    );

    wire clk200;
    BUFG clk_bufg (
        .I (clk200_raw),
        .O (clk200)
    );

    wire rst = ~rst_n;

    // ~3 Hz blink at 200 MHz (counter[25])
    reg [25:0] cnt;
    always @(posedge clk200 or posedge rst) begin
        if (rst) cnt <= 0;
        else     cnt <= cnt + 1'b1;
    end

    assign led     = {cnt[25], cnt[24], cnt[23], cnt[22]};
    assign uart_tx = 1'b1; // idle high

endmodule
