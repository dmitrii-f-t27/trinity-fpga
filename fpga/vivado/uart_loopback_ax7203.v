`default_nettype wire

// =============================================================================
// uart_loopback_ax7203 — minimal UART path diagnostic for ALINX AX7203
// =============================================================================
// Receives any byte on UART RX and immediately echoes it back on TX.
// LED0 toggles on each successfully received byte; LED1 = heartbeat;
// LED2 = line idle (should be high); LED3 = ~rst_n.
// Use this to verify the host ↔ FPGA UART path is physically connected.
// =============================================================================

`timescale 1ns / 1ps

module uart_loopback_ax7203 (
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
    // UART clock divider: 200 MHz / 115200 ~= 1736
    // =========================================================================
    localparam UART_DIV = 11'd1736;
    localparam UART_DIV_HALF = 11'd868;

    reg [10:0] uart_cnt;
    reg        uart_tick;
    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            uart_cnt  <= 11'd0;
            uart_tick <= 1'b0;
        end else if (uart_cnt == UART_DIV - 1) begin
            uart_cnt  <= 11'd0;
            uart_tick <= 1'b1;
        end else begin
            uart_cnt  <= uart_cnt + 1'b1;
            uart_tick <= 1'b0;
        end
    end

    // =========================================================================
    // UART RX: 8N1, oversample at bit-center
    // =========================================================================
    reg [2:0] rx_sync;
    always @(posedge clk200) rx_sync <= {rx_sync[1:0], uart_rx};
    wire rx_bit = rx_sync[2];

    localparam RX_IDLE  = 3'd0;
    localparam RX_START = 3'd1;
    localparam RX_DATA  = 3'd2;
    localparam RX_STOP  = 3'd3;

    reg [2:0]  rx_state;
    reg [10:0] rx_sample_cnt;
    reg [2:0]  rx_bit_idx;
    reg [7:0]  rx_byte;
    reg        rx_done;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            rx_state      <= RX_IDLE;
            rx_sample_cnt <= 11'd0;
            rx_bit_idx    <= 3'd0;
            rx_byte       <= 8'd0;
            rx_done       <= 1'b0;
        end else begin
            rx_done <= 1'b0;
            case (rx_state)
                RX_IDLE: begin
                    if (rx_bit == 1'b0) begin
                        rx_state      <= RX_START;
                        rx_sample_cnt <= 11'd0;
                    end
                end
                RX_START: begin
                    if (uart_tick) begin
                        if (rx_sample_cnt == UART_DIV_HALF) begin
                            rx_state      <= RX_DATA;
                            rx_sample_cnt <= 11'd0;
                            rx_bit_idx    <= 3'd0;
                        end else begin
                            rx_sample_cnt <= rx_sample_cnt + 1'b1;
                        end
                    end
                end
                RX_DATA: begin
                    if (uart_tick) begin
                        if (rx_sample_cnt == UART_DIV - 1) begin
                            rx_sample_cnt <= 11'd0;
                            rx_byte       <= {rx_bit, rx_byte[7:1]};
                            if (rx_bit_idx == 3'd7) begin
                                rx_state <= RX_STOP;
                            end else begin
                                rx_bit_idx <= rx_bit_idx + 1'b1;
                            end
                        end else begin
                            rx_sample_cnt <= rx_sample_cnt + 1'b1;
                        end
                    end
                end
                RX_STOP: begin
                    if (uart_tick) begin
                        if (rx_sample_cnt == UART_DIV - 1) begin
                            rx_state      <= RX_IDLE;
                            rx_sample_cnt <= 11'd0;
                            rx_done       <= 1'b1;
                        end else begin
                            rx_sample_cnt <= rx_sample_cnt + 1'b1;
                        end
                    end
                end
            endcase
        end
    end

    // =========================================================================
    // UART TX: 8N1, single-byte echo FSM
    // =========================================================================
    localparam TX_IDLE  = 2'd0;
    localparam TX_START = 2'd1;
    localparam TX_DATA  = 2'd2;
    localparam TX_STOP  = 2'd3;

    reg [1:0] tx_fsm;
    reg [7:0] tx_sr;
    reg [3:0] tx_bit_cnt;
    reg [9:0] tx_shift;
    reg       tx_active;
    reg       tx_start_req;

    // Capture rx_done into a request flag so it is visible to the TX FSM
    // across clock edges (rx_done is only one clk200 cycle wide).
    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            tx_start_req <= 1'b0;
        end else begin
            if (rx_done && !tx_active) begin
                tx_start_req <= 1'b1;
                tx_sr        <= rx_byte;
            end
            if (tx_start_req && tx_active) begin
                tx_start_req <= 1'b0;
            end
        end
    end

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            tx_fsm     <= TX_IDLE;
            tx_sr      <= 8'hFF;
            tx_bit_cnt <= 4'd0;
            tx_shift   <= 10'h3FF;
            tx_active  <= 1'b0;
        end else begin
            case (tx_fsm)
                TX_IDLE: begin
                    if (tx_start_req) begin
                        tx_active <= 1'b1;
                        tx_fsm    <= TX_START;
                    end
                end
                TX_START: begin
                    if (uart_tick) begin
                        tx_shift   <= {1'b1, tx_sr[7:0], 1'b0};
                        tx_bit_cnt <= 4'd0;
                        tx_fsm     <= TX_DATA;
                    end
                end
                TX_DATA: begin
                    if (uart_tick) begin
                        tx_shift <= {1'b1, tx_shift[9:1]};
                        if (tx_bit_cnt == 4'd9) begin
                            tx_fsm <= TX_STOP;
                        end else begin
                            tx_bit_cnt <= tx_bit_cnt + 1'b1;
                        end
                    end
                end
                TX_STOP: begin
                    if (uart_tick) begin
                        tx_active <= 1'b0;
                        tx_fsm    <= TX_IDLE;
                    end
                end
            endcase
        end
    end

    assign uart_tx = tx_active ? tx_shift[0] : 1'b1;

    // =========================================================================
    // Status LEDs
    // =========================================================================
    reg [25:0] hb_cnt;
    reg [7:0]  last_rx;
    reg        activity;
    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            hb_cnt   <= 26'd0;
            last_rx  <= 8'd0;
            activity <= 1'b0;
        end else begin
            hb_cnt <= hb_cnt + 1'b1;
            if (rx_done) begin
                last_rx  <= rx_byte;
                activity <= ~activity;
            end
        end
    end

    assign led[0] = activity;         // toggles on each received byte
    assign led[1] = hb_cnt[25];       // ~3 Hz heartbeat
    assign led[2] = uart_tx;          // line state (idle = 1)
    assign led[3] = ~rst;             // reset released = 1

endmodule
