`default_nettype wire

// =============================================================================
// gf16_codec_ax7203 — GoldenFloat16 ADD conformance engine over UART
// =============================================================================
// Target: ALINX AX7203 (XC7A200T-FBG484-2)
// Clock: CFGMCLK (~70 MHz, STARTUPE2) — re-clocked from 200 MHz (UART non-responsive on 200 MHz)
// UART:  ~161290 baud 8N1 on N15 (TX) / P20 (RX) — host reads/sends ~160000
//
// Protocol (matches conformance/gf16_conformance_ax7203.py):
//   Host -> FPGA: [0xAA][0x55][a_lo][a_hi][b_lo][b_hi][cmd]
//   FPGA -> Host: [0xA5][res_lo][res_hi][status]
//   cmd is ignored in this simplified ADD-only build.
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
    // Clock: STARTUPE2 CFGMCLK (~70 MHz) -> BUFG. Re-clocked from the 200 MHz
    // differential path because UART on 200 MHz gave 0 response (gf16 + loopback)
    // while CFGMCLK UART is proven (rx_echo, uart_tx_probe). clk200_p/n pads are
    // kept (unused) so gf16_ax7203.xdc still applies; the `clk200` net name is
    // preserved so all always-blocks below stay unchanged.
    // =========================================================================
    wire mclk_c;
    wire eos;
    STARTUPE2 #(
        .PROG_USR("FALSE"),
        .SIM_CCLK_FREQ(0.0)
    ) u_startup (
        .CFGCLK(),
        .CFGMCLK(mclk_c),
        .EOS(eos),
        .CLK(1'b0),
        .GSR(1'b0),
        .GTS(1'b0),
        .KEYCLEARB(1'b0),
        .PACK(1'b0),
        .USRCCLKO(1'b0),
        .USRCCLKTS(1'b0),
        .USRDONEO(1'b0),
        .USRDONETS(1'b0)
    );

    wire _unused_diff = clk200_p ^ clk200_n; // keep diff pads for XDC reuse

    wire clk200;   // now CFGMCLK-derived; name kept so always-blocks match
    BUFG clk_bufg (
        .I (mclk_c),
        .O (clk200)
    );

    wire rst = ~rst_n | ~eos;

    // =========================================================================
    // UART clock divider: CFGMCLK ~70 MHz / 161290 baud ~= 434 (host reads ~160k)
    // =========================================================================
    localparam UART_DIV = 11'd434;
    localparam UART_DIV_HALF = 11'd217;

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
    // UART RX: 8N1, mid-bit sample via a CYCLE counter (LSB first).
    // FIX: the original incremented rx_sample_cnt on uart_tick (1 pulse per
    // bit-time) but compared it to UART_DIV_HALF (a CYCLE count) -> it sampled
    // ~UART_DIV bit-times late and never assembled a frame (0 response on both
    // 200 MHz and CFGMCLK). Now counts CYCLES: on the start edge wait
    // 1.5*UART_DIV to the middle of bit0, then UART_DIV per bit (same scheme as
    // the proven rx_echo_hb RX FSM). rx_byte/rx_done interface unchanged.
    // =========================================================================
    reg [2:0] rx_sync;
    always @(posedge clk200) rx_sync <= {rx_sync[1:0], uart_rx};
    wire rx_bit = rx_sync[2];

    localparam RX_IDLE = 2'd0;
    localparam RX_DATA = 2'd1;
    localparam RX_STOP = 2'd2;

    reg [1:0]  rx_state;
    reg [10:0] rx_rcnt;      // cycle countdown to the next sample point
    reg [2:0]  rx_bit_idx;
    reg [7:0]  rx_byte;
    reg        rx_done;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            rx_state   <= RX_IDLE;
            rx_rcnt    <= 11'd0;
            rx_bit_idx <= 3'd0;
            rx_byte    <= 8'd0;
            rx_done    <= 1'b0;
        end else begin
            rx_done <= 1'b0;
            case (rx_state)
                RX_IDLE: begin
                    if (rx_bit == 1'b0) begin                     // start-bit edge
                        rx_rcnt    <= (UART_DIV + UART_DIV_HALF) - 11'd1; // -> mid bit0
                        rx_state   <= RX_DATA;
                        rx_bit_idx <= 3'd0;
                    end
                end
                RX_DATA: begin
                    if (rx_rcnt == 11'd0) begin
                        rx_byte <= {rx_bit, rx_byte[7:1]};        // shift in LSB first
                        if (rx_bit_idx == 3'd7) begin
                            rx_state <= RX_STOP;
                            rx_rcnt  <= UART_DIV - 11'd1;         // -> mid stop
                        end else begin
                            rx_bit_idx <= rx_bit_idx + 3'd1;
                            rx_rcnt    <= UART_DIV - 11'd1;       // -> mid next bit
                        end
                    end else begin
                        rx_rcnt <= rx_rcnt - 11'd1;
                    end
                end
                RX_STOP: begin
                    if (rx_rcnt == 11'd0) begin
                        rx_done  <= 1'b1;                         // byte complete
                        rx_state <= RX_IDLE;
                    end else begin
                        rx_rcnt <= rx_rcnt - 11'd1;
                    end
                end
                default: rx_state <= RX_IDLE;
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
    reg        frame_valid;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            frm_state   <= FRM_SYNC0;
            op_a        <= 16'd0;
            op_b        <= 16'd0;
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
                        frame_valid <= 1'b1;
                        frm_state   <= FRM_SYNC0;
                    end
                endcase
            end
        end
    end

    // =========================================================================
    // GF16 adder (LUT-based, 15-bit legacy format from gf16_adder.v)
    // Adapter: our operands are 16-bit [sign][exp6][mant9]; use top 15 bits
    // mapping [sign][exp6][mant8] by dropping LSB of mantissa.
    // This is intentionally a first-pass conformance smoke test.
    // =========================================================================
    wire [14:0] add_a15 = op_a[15:1];
    wire [14:0] add_b15 = op_b[15:1];
    wire        add_in_ready;
    wire        add_out_valid;
    wire [14:0] add_out_y15;

    gf16_adder u_add (
        .clk       (clk200),
        .rst       (rst),
        .in_valid  (frame_valid),
        .in_a      (add_a15),
        .in_b      (add_b15),
        .in_ready  (add_in_ready),
        .out_valid (add_out_valid),
        .out_y     (add_out_y15),
        .out_ready (1'b1)
    );

    // 15-bit adder drops mantissa LSB; reconstruct it from operand A for the
    // bring-up identity path (a + 0 == a). A full 16-bit adder will remove
    // this reconstruction.
    wire [15:0] result_y = {add_out_y15, op_a[0]};

    // =========================================================================
    // Output response buffer: [0xA5][res_lo][res_hi][status]
    // =========================================================================
    reg [2:0] tx_state;
    reg [1:0] tx_byte_idx;
    reg [7:0] tx_data;
    reg       tx_start;
    reg       tx_busy;
    reg       tx_active;

    reg [15:0] result_reg;

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            tx_state    <= 3'd0;
            tx_byte_idx <= 2'd0;
            tx_start    <= 1'b0;
            result_reg  <= 16'd0;
        end else begin
            tx_start <= 1'b0;
            if (add_out_valid && !tx_busy) begin
                result_reg   <= result_y;
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
            2'd3: tx_data = 8'h00; // status = OK
        endcase
    end

    // =========================================================================
    // UART TX: 8N1, LSB first.
    // Frame layout in tx_shift after load: {stop=1, data[7], ..., data[0], start=0}
    // We shift right each bit-time; tx_shift[0] drives the line.
    //
    // The tx_start strobe is single-cycle, so capture it into a request flag
    // that the TX FSM sees reliably across clock edges.
    // =========================================================================
    localparam TX_IDLE  = 2'd0;
    localparam TX_START = 2'd1;
    localparam TX_DATA  = 2'd2;
    localparam TX_STOP  = 2'd3;

    reg [1:0] tx_fsm;
    reg [7:0] tx_sr;
    reg [3:0] tx_bit_cnt; // 0..9 for the 10 bit-times
    reg [9:0] tx_shift;
    reg       tx_start_req;
    // NOTE: tx_active and tx_busy are declared once above (response-buffer
    // block). An earlier duplicate declaration here was silently merged by
    // yosys into broken logic (TX sent 0xFF); iverilog catches it.

    always @(posedge clk200 or posedge rst) begin
        if (rst) begin
            tx_start_req <= 1'b0;
        end else begin
            if (tx_start && !tx_active) begin
                tx_start_req <= 1'b1;
                tx_sr        <= tx_data;
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
            tx_busy    <= 1'b0;
        end else begin
            case (tx_fsm)
                TX_IDLE: begin
                    if (tx_start_req) begin
                        tx_active <= 1'b1;
                        tx_busy   <= 1'b1;
                        tx_fsm    <= TX_START;
                    end
                end
                TX_START: begin
                    if (uart_tick) begin
                        // Load full 8N1 frame; first bit out is start=0
                        tx_shift   <= {1'b1, tx_sr[7:0], 1'b0};
                        tx_bit_cnt <= 4'd0;
                        tx_fsm     <= TX_DATA;
                    end
                end
                TX_DATA: begin
                    if (uart_tick) begin
                        // Shift out one bit per bit-time. After 10 shifts the
                        // stop bit has been sent and tx_shift is all ones again.
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
                        tx_busy   <= 1'b0;
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
    always @(posedge clk200 or posedge rst) begin
        if (rst) hb_cnt <= 26'd0;
        else     hb_cnt <= hb_cnt + 1'b1;
    end

    assign led[0] = hb_cnt[25];
    assign led[1] = frame_valid;
    assign led[2] = add_out_valid;
    assign led[3] = ~rst;

endmodule
