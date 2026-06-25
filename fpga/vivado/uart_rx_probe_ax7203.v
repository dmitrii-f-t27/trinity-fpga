`default_nettype wire

// =============================================================================
// uart_rx_probe_ax7203 — diagnostic: LED0 toggles on every start-bit falling edge
// =============================================================================
// Use this to verify that host UART TX actually reaches the FPGA RX pin.
// LED0 toggles each time a start bit (high->low transition) is detected.
// LED1 = heartbeat. LED2 = uart_tx (idle high). LED3 = ~rst_n.
// =============================================================================

`timescale 1ns / 1ps

module uart_rx_probe_ax7203 (
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

    // =========================================================================
    // Synchronize and detect falling edge on uart_rx
    // =========================================================================
    reg [2:0] rx_sync;
    reg       rx_dly;
    reg       start_pulse;
    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            rx_sync     <= 3'b111;
            rx_dly      <= 1'b1;
            start_pulse <= 1'b0;
        end else begin
            rx_sync     <= {rx_sync[1:0], uart_rx};
            rx_dly      <= rx_sync[2];
            start_pulse <= rx_dly && !rx_sync[2];
        end
    end

    // =========================================================================
    // Heartbeat + activity LED
    // =========================================================================
    reg [25:0] hb_cnt;
    reg        activity;
    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            hb_cnt   <= 26'd0;
            activity <= 1'b0;
        end else begin
            hb_cnt <= hb_cnt + 1'b1;
            if (start_pulse) activity <= ~activity;
        end
    end

    assign led[0] = activity;
    assign led[1] = hb_cnt[25];
    assign led[2] = uart_tx; // idle high
    assign led[3] = ~rst;

    assign uart_tx = 1'b1; // keep idle high

endmodule
