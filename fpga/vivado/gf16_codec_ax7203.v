`default_nettype wire

// =============================================================================
// gf16_codec_ax7203 — GoldenFloat16 codec + UART conformance engine
// =============================================================================
// Target: ALINX AX7203 (XC7A200T-FBG484-2)
// Clock: 200 MHz differential on R4/T4
// UART:  115200 8N1 on N15 (TX) / P20 (RX)
//
// Protocol (matches conformance/gf16_conformance_ax7203.py):
//   Host -> FPGA: [0xAA][0x55][a_lo][a_hi][b_lo][b_hi][cmd]
//   FPGA -> Host: [0xA5][res_lo][res_hi][status]
//   cmd[0]: 0 = ADD, 1 = MUL
// =============================================================================

`timescale 1ns / 1ps

module gf16_codec_ax7203 (
    input  wire clk200_p,
    input  wire clk200_n,
    input  wire rst_n,
    output wire [3:0] led,
    output wire uart_tx,
    input  wire uart_rx
);

    // =========================================================================
    // Clock input: differential -> IBUFDS -> BUFG
    // =========================================================================
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
    // UART clock divider: 200 MHz / 115200 ≈ 1736
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

    reg [2:0] rx_state;
    reg [10:0] rx_sample_cnt;
    reg [2:0] rx_bit_idx;
    reg [7:0] rx_byte;
    reg       rx_done;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            rx_state     <= RX_IDLE;
            rx_sample_cnt<= 11'd0;
            rx_bit_idx   <= 3'd0;
            rx_byte      <= 8'd0;
            rx_done      <= 1'b0;
        end else begin
            rx_done <= 1'b0;
            case (rx_state)
                RX_IDLE: begin
                    if (rx_bit == 1'b0) begin // start bit falling edge
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
                            rx_done       <= 1'b1; // valid even if stop bit not 1
                        end else begin
                            rx_sample_cnt <= rx_sample_cnt + 1'b1;
                        end
                    end
                end
            endcase
        end
    end

    // =========================================================================
    // Frame assembly: 7 bytes [AA 55 a_lo a_hi b_lo b_hi cmd]
    // =========================================================================
    localparam FRM_SYNC0 = 3'd0;
    localparam FRM_SYNC1 = 3'd1;
    localparam FRM_A_LO  = 3'd2;
    localparam FRM_A_HI  = 3'd3;
    localparam FRM_B_LO  = 3'd4;
    localparam FRM_B_HI  = 3'd5;
    localparam FRM_CMD   = 3'd6;

    reg [2:0] frm_state;
    reg [15:0] op_a;
    reg [15:0] op_b;
    reg        op_is_mul;
    reg        frame_valid;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            frm_state   <= FRM_SYNC0;
            op_a        <= 16'd0;
            op_b        <= 16'd0;
            op_is_mul   <= 1'b0;
            frame_valid <= 1'b0;
        end else begin
            frame_valid <= 1'b0;
            if (rx_done) begin
                case (frm_state)
                    FRM_SYNC0: frm_state <= (rx_byte == 8'hAA) ? FRM_SYNC1 : FRM_SYNC0;
                    FRM_SYNC1: frm_state <= (rx_byte == 8'h55) ? FRM_A_LO  : FRM_SYNC0;
                    FRM_A_LO:  begin op_a[7:0]  <= rx_byte; frm_state <= FRM_A_HI;  end
                    FRM_A_HI:  begin op_a[15:8] <= rx_byte; frm_state <= FRM_B_LO;  end
                    FRM_B_LO:  begin op_b[7:0]  <= rx_byte; frm_state <= FRM_B_HI;  end
                    FRM_B_HI:  begin op_b[15:8] <= rx_byte; frm_state <= FRM_CMD;   end
                    FRM_CMD:   begin
                        op_is_mul   <= rx_byte[0];
                        frame_valid <= 1'b1;
                        frm_state   <= FRM_SYNC0;
                    end
                endcase
            end
        end
    end

    // =========================================================================
    // GF16 adder / multiplier instances
    // =========================================================================
    wire        add_in_ready, mul_in_ready;
    wire        add_out_valid, mul_out_valid;
    wire [15:0] add_out_y,    mul_out_y;

    reg         calc_valid;
    reg  [1:0]  calc_op;
    reg  [15:0] calc_a;
    reg  [15:0] calc_b;
    wire        calc_ready = op_is_mul ? mul_in_ready : add_in_ready;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            calc_valid <= 1'b0;
            calc_op    <= 2'd0;
            calc_a     <= 16'd0;
            calc_b     <= 16'd0;
        end else begin
            calc_valid <= frame_valid;
            calc_op    <= op_is_mul ? 2'b01 : 2'b00;
            calc_a     <= op_a;
            calc_b     <= op_b;
        end
    end

    gf16_add u_add (
        .clk       (clk200),
        .rst_n     (rst_n),
        .in_valid  (calc_valid & ~op_is_mul),
        .in_ready  (add_in_ready),
        .in_op     (2'b00),
        .in_a      (calc_a),
        .in_b      (calc_b),
        .out_valid (add_out_valid),
        .out_ready (1'b1),
        .out_y     (add_out_y)
    );

    gf16_mul u_mul (
        .clk       (clk200),
        .rst_n     (rst_n),
        .in_valid  (calc_valid & op_is_mul),
        .in_ready  (mul_in_ready),
        .in_op     (2'b01),
        .in_a      (calc_a),
        .in_b      (calc_b),
        .out_valid (mul_out_valid),
        .out_ready (1'b1),
        .out_y     (mul_out_y)
    );

    wire        result_valid = op_is_mul ? mul_out_valid : add_out_valid;
    wire [15:0] result_y     = op_is_mul ? mul_out_y     : add_out_y;

    // =========================================================================
    // Output response buffer: [0xA5][res_lo][res_hi][status]
    // =========================================================================
    reg [2:0] tx_state;
    reg [1:0] tx_byte_idx;
    reg [7:0] tx_data;
    reg       tx_start;
    reg       tx_busy;
    reg [3:0] tx_bit_idx;
    reg [9:0] tx_shift;
    reg       tx_active;

    reg [15:0] result_reg;
    reg        result_status;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            tx_state    <= 3'd0;
            tx_byte_idx <= 2'd0;
            tx_start    <= 1'b0;
            result_reg  <= 16'd0;
            result_status<= 1'b0;
        end else begin
            tx_start <= 1'b0;
            if (result_valid && !tx_busy) begin
                result_reg   <= result_y;
                result_status<= 1'b0; // 0 = OK
                tx_state     <= 3'd1;
                tx_byte_idx  <= 2'd0;
                tx_start     <= 1'b1;
            end else if (tx_state == 3'd1 && !tx_busy && tx_byte_idx < 2'd3) begin
                tx_byte_idx <= tx_byte_idx + 1'b1;
                tx_start    <= 1'b1;
            end else if (tx_state == 3'd1 && !tx_busy && tx_byte_idx == 2'd3) begin
                tx_state <= 3'd0;
            end
        end
    end

    always @(*) begin
        case (tx_byte_idx)
            2'd0: tx_data = 8'hA5;
            2'd1: tx_data = result_reg[7:0];
            2'd2: tx_data = result_reg[15:8];
            2'd3: tx_data = {7'd0, result_status};
        endcase
    end

    // =========================================================================
    // UART TX: 8N1
    // =========================================================================
    localparam TX_IDLE  = 2'd0;
    localparam TX_START = 2'd1;
    localparam TX_DATA  = 2'd2;
    localparam TX_STOP  = 2'd3;

    reg [1:0] tx_fsm;
    reg [7:0] tx_sr;
    reg [2:0] tx_idx;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            tx_fsm   <= TX_IDLE;
            tx_sr    <= 8'hFF;
            tx_idx   <= 3'd0;
            tx_shift <= 10'h3FF;
            tx_active<= 1'b0;
            tx_busy  <= 1'b0;
        end else begin
            if (tx_start && !tx_active) begin
                tx_active <= 1'b1;
                tx_busy   <= 1'b1;
                tx_fsm    <= TX_START;
                tx_sr     <= tx_data;
                tx_shift  <= 10'h3FF;
            end

            if (uart_tick && tx_active) begin
                case (tx_fsm)
                    TX_START: begin
                        tx_shift <= {1'b0, tx_sr}; // start bit + data
                        tx_idx   <= 3'd0;
                        tx_fsm   <= TX_DATA;
                    end
                    TX_DATA: begin
                        if (tx_idx == 3'd7) begin
                            tx_fsm <= TX_STOP;
                        end else begin
                            tx_shift <= {1'b1, tx_shift[9:1]};
                            tx_idx   <= tx_idx + 1'b1;
                        end
                    end
                    TX_STOP: begin
                        tx_shift[0] <= 1'b1; // stop bit already loaded
                        tx_active   <= 1'b0;
                        tx_busy     <= 1'b0;
                    end
                endcase
            end
        end
    end

    // TX line: idle high; bit 0 is current transmit bit
    assign uart_tx = tx_active ? tx_shift[0] : 1'b1;

    // =========================================================================
    // Status LEDs
    // =========================================================================
    reg [25:0] hb_cnt;
    always @(posedge clk200 or posedge rst) begin
        if (rst) hb_cnt <= 26'd0;
        else     hb_cnt <= hb_cnt + 1'b1;
    end

    // LED0 = heartbeat, LED1 = RX frame received, LED2 = result valid, LED3 = reset state inverse
    assign led[0] = hb_cnt[25];
    assign led[1] = frame_valid;
    assign led[2] = result_valid;
    assign led[3] = ~rst;

endmodule
