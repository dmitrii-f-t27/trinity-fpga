`default_nettype wire
`timescale 1ns / 1ps
//=============================================================================
// trinet_mac32_ax7203 — TRI-NET compute node cell for AX7203 (XC7A200T).
//
// The node accepts a job over UART, computes a 32-wide TERNARY dot product
// entirely in LUT logic (no multipliers, no DSP, no soft CPU), and returns a
// deterministic compute RECEIPT that a host can verify independently.
//
//   y = sum_{i=0..31} w[i] * x[i],   w[i], x[i] in {-1, 0, +1}
//
// Implemented as popcount(pos) - popcount(neg), so the datapath is pure
// AND/OR/XOR/add — it honours the zero-multiplier discipline (issue #48 rule 2,
// issue #19 Article III).
//
// TRIT ENCODING (TF3 packed, 2 bits per trit, LSB-first within a byte):
//   2'b00 =  0
//   2'b01 = +1
//   2'b10 = -1
//   2'b11 =  0   (reserved code, canonicalised to zero)
//
// REQUEST FRAME (24 bytes, MSB of the stream first):
//   [0]      0xAA          magic
//   [1]      0x55          magic
//   [2]      OP            0x01 = MAC32
//   [3..6]   NONCE[0..3]   job nonce, little-endian
//   [7..14]  W[0..7]       32 packed trits, byte 0 holds trits 0..3
//   [15..22] X[0..7]       32 packed trits, byte 0 holds trits 0..3
//   [23]     TRIG          any value; latches the job and starts compute
//
// RESPONSE FRAME (15 bytes):
//   [0]      0xA5          magic
//   [1]      Y             dot product, 8-bit two's complement, range -32..+32
//   [2]      STATUS        0x01 = ok
//   [3..6]   NONCE[0..3]   echoed
//   [7..10]  NODE_ID[0..3] little-endian node identity
//   [11..14] CRC[0..3]     CRC-32 receipt tag, little-endian
//
// RECEIPT TAG: CRC-32 (IEEE 802.3, reflected, poly 0xEDB88320, init 0xFFFFFFFF,
// final XOR 0xFFFFFFFF — bit-identical to Python zlib.crc32) taken over the
// 26-byte preimage
//
//   OP | NONCE[0..3] | W[0..7] | X[0..7] | Y | NODE_ID[0..3]
//
// so the tag binds the answer to the exact job, the nonce and the node. A host
// that changes any input byte, the result, or the claimed node identity
// produces a different tag. CRC is a checksum, not a signature: it detects
// corruption and mismatch, it does not by itself prove the work ran on this
// silicon. Physical binding is a separate question — see trinet_dna_probe.
//
// Clock: STARTUPE2 CFGMCLK, measured ~69-70 MHz on AX7203. BAUD_DIV 434 gives
// ~160000 baud, the rate every proven conformance host on this board uses.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module trinet_mac32_ax7203 #(
    parameter [31:0] NODE_ID = 32'h5452_494E  // "TRIN" — override per board
) (
    input  wire rst_n,
    input  wire uart_rx,
    output reg  uart_tx,
    output wire [3:0] led
);

    //-------------------------------------------------------------------------
    // Clock and reset — CFGMCLK from the configuration oscillator.
    //-------------------------------------------------------------------------
    wire mclk, eos;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startup (
        .CFGCLK(), .CFGMCLK(mclk), .EOS(eos),
        .CLK(1'b0), .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b0), .PACK(1'b0),
        .USRCCLKO(1'b0), .USRCCLKTS(1'b0), .USRDONEO(1'b0), .USRDONETS(1'b0));

    wire rst = ~rst_n | ~eos;

    localparam [8:0] BAUD_DIV = 9'd434;

    reg [26:0] heartbeat;
    always @(posedge mclk or posedge rst)
        if (rst) heartbeat <= 27'd0; else heartbeat <= heartbeat + 27'd1;

    //-------------------------------------------------------------------------
    // UART receive.
    //-------------------------------------------------------------------------
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst)
        if (rst) rsync <= 3'b111; else rsync <= {rsync[1:0], uart_rx};
    wire rxd = rsync[2];

    reg [1:0] rxs;
    reg [9:0] rxcnt;
    reg [3:0] rbi;
    reg [7:0] rxsr, rx_byte;
    reg       rx_new;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            rxs <= 2'd0; rxcnt <= 10'd0; rbi <= 4'd0;
            rxsr <= 8'd0; rx_byte <= 8'd0; rx_new <= 1'b0;
        end else begin
            rx_new <= 1'b0;
            case (rxs)
                2'd0: if (~rxd) begin
                          rxcnt <= (BAUD_DIV + (BAUD_DIV >> 1)) - 10'd1;
                          rxs <= 2'd1; rbi <= 4'd0;
                      end
                2'd1: if (rxcnt == 10'd0) begin
                          rxsr <= {rxd, rxsr[7:1]};
                          if (rbi == 4'd7) begin rxs <= 2'd2; rxcnt <= {1'b0, BAUD_DIV} - 10'd1; end
                          else            begin rbi <= rbi + 4'd1; rxcnt <= {1'b0, BAUD_DIV} - 10'd1; end
                      end else rxcnt <= rxcnt - 10'd1;
                2'd2: if (rxcnt == 10'd0) begin
                          rx_byte <= rxsr; rx_new <= 1'b1; rxs <= 2'd0;
                      end else rxcnt <= rxcnt - 10'd1;
                default: rxs <= 2'd0;
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // Frame parser — 24-byte request.
    //-------------------------------------------------------------------------
    localparam [4:0] F_MAGIC0 = 5'd0,
                     F_MAGIC1 = 5'd1,
                     F_BODY   = 5'd2;

    reg [4:0]  fstate;
    reg [4:0]  bidx;            // 0..20 over OP|NONCE|W|X, then TRIG at 21
    reg [7:0]  op_r;
    reg [7:0]  nonce_b [0:3];
    reg [7:0]  w_b     [0:7];
    reg [7:0]  x_b     [0:7];
    reg        frame_valid;

    integer ini;
    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            fstate <= F_MAGIC0; bidx <= 5'd0; op_r <= 8'd0; frame_valid <= 1'b0;
            for (ini = 0; ini < 4; ini = ini + 1) nonce_b[ini] <= 8'd0;
            for (ini = 0; ini < 8; ini = ini + 1) begin w_b[ini] <= 8'd0; x_b[ini] <= 8'd0; end
        end else begin
            frame_valid <= 1'b0;
            if (rx_new) begin
                case (fstate)
                    F_MAGIC0: fstate <= (rx_byte == 8'hAA) ? F_MAGIC1 : F_MAGIC0;
                    F_MAGIC1: begin
                        if (rx_byte == 8'h55) begin fstate <= F_BODY; bidx <= 5'd0; end
                        else if (rx_byte == 8'hAA) fstate <= F_MAGIC1;
                        else fstate <= F_MAGIC0;
                    end
                    F_BODY: begin
                        if      (bidx == 5'd0)                    op_r            <= rx_byte;
                        else if (bidx <= 5'd4)                    nonce_b[bidx-1] <= rx_byte;
                        else if (bidx <= 5'd12)                   w_b[bidx-5]     <= rx_byte;
                        else if (bidx <= 5'd20)                   x_b[bidx-13]    <= rx_byte;

                        if (bidx == 5'd21) begin              // TRIG byte
                            frame_valid <= 1'b1;
                            fstate <= F_MAGIC0; bidx <= 5'd0;
                        end else bidx <= bidx + 5'd1;
                    end
                    default: fstate <= F_MAGIC0;
                endcase
            end
        end
    end

    //-------------------------------------------------------------------------
    // Ternary dot product — popcount(pos) - popcount(neg). No multipliers.
    //-------------------------------------------------------------------------
    wire [63:0] w_bus = {w_b[7], w_b[6], w_b[5], w_b[4], w_b[3], w_b[2], w_b[1], w_b[0]};
    wire [63:0] x_bus = {x_b[7], x_b[6], x_b[5], x_b[4], x_b[3], x_b[2], x_b[1], x_b[0]};

    wire [31:0] prod_pos, prod_neg;
    genvar gi;
    generate
        for (gi = 0; gi < 32; gi = gi + 1) begin : gen_trit
            wire [1:0] wt = w_bus[2*gi +: 2];
            wire [1:0] xt = x_bus[2*gi +: 2];
            wire w_pos = (wt == 2'b01);
            wire w_neg = (wt == 2'b10);
            wire x_pos = (xt == 2'b01);
            wire x_neg = (xt == 2'b10);
            // reserved code 2'b11 is neither pos nor neg, so it acts as zero
            assign prod_pos[gi] = (w_pos & x_pos) | (w_neg & x_neg);
            assign prod_neg[gi] = (w_pos & x_neg) | (w_neg & x_pos);
        end
    endgenerate

    reg [5:0] cnt_pos, cnt_neg;
    integer pk;
    always @(*) begin
        cnt_pos = 6'd0;
        cnt_neg = 6'd0;
        for (pk = 0; pk < 32; pk = pk + 1) begin
            cnt_pos = cnt_pos + {5'd0, prod_pos[pk]};
            cnt_neg = cnt_neg + {5'd0, prod_neg[pk]};
        end
    end

    wire signed [7:0] dot_result = $signed({2'b00, cnt_pos}) - $signed({2'b00, cnt_neg});

    //-------------------------------------------------------------------------
    // Receipt engine — CRC-32 over the 26-byte preimage.
    //-------------------------------------------------------------------------
    function [31:0] crc32_byte;
        input [31:0] crc_in;
        input [7:0]  data;
        reg   [31:0] c;
        integer ci;
        begin
            c = crc_in ^ {24'd0, data};
            for (ci = 0; ci < 8; ci = ci + 1)
                c = c[0] ? ((c >> 1) ^ 32'hEDB88320) : (c >> 1);
            crc32_byte = c;
        end
    endfunction

    localparam [2:0] S_IDLE  = 3'd0,
                     S_FEED  = 3'd1,
                     S_FINAL = 3'd2,
                     S_SEND  = 3'd3;

    reg [2:0]  cstate;
    reg [4:0]  feed_idx;        // 0..25 over the preimage
    reg [31:0] crc_acc;
    reg [7:0]  y_reg;
    reg [31:0] crc_reg;
    reg        result_ready;

    // preimage byte selector
    reg [7:0] preimage_byte;
    always @(*) begin
        if      (feed_idx == 5'd0)  preimage_byte = op_r;
        else if (feed_idx <= 5'd4)  preimage_byte = nonce_b[feed_idx-1];
        else if (feed_idx <= 5'd12) preimage_byte = w_b[feed_idx-5];
        else if (feed_idx <= 5'd20) preimage_byte = x_b[feed_idx-13];
        else if (feed_idx == 5'd21) preimage_byte = y_reg;
        else if (feed_idx == 5'd22) preimage_byte = NODE_ID[7:0];
        else if (feed_idx == 5'd23) preimage_byte = NODE_ID[15:8];
        else if (feed_idx == 5'd24) preimage_byte = NODE_ID[23:16];
        else                        preimage_byte = NODE_ID[31:24];
    end

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            cstate <= S_IDLE; feed_idx <= 5'd0; crc_acc <= 32'hFFFFFFFF;
            y_reg <= 8'd0; crc_reg <= 32'd0; result_ready <= 1'b0;
        end else begin
            result_ready <= 1'b0;
            case (cstate)
                S_IDLE: if (frame_valid) begin
                            y_reg    <= dot_result;
                            crc_acc  <= 32'hFFFFFFFF;
                            feed_idx <= 5'd0;
                            cstate   <= S_FEED;
                        end
                S_FEED: begin
                    crc_acc <= crc32_byte(crc_acc, preimage_byte);
                    if (feed_idx == 5'd25) cstate <= S_FINAL;
                    else feed_idx <= feed_idx + 5'd1;
                end
                S_FINAL: begin
                    crc_reg      <= crc_acc ^ 32'hFFFFFFFF;
                    result_ready <= 1'b1;
                    cstate       <= S_SEND;
                end
                S_SEND: cstate <= S_IDLE;
                default: cstate <= S_IDLE;
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // UART transmit — 15-byte response.
    //-------------------------------------------------------------------------
    reg        responding;
    reg [3:0]  tx_idx;
    reg [7:0]  tx_buf [0:14];
    reg [9:0]  tcnt;
    reg [3:0]  tbi;
    reg [9:0]  tsr;

    integer ti;
    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            responding <= 1'b0; tx_idx <= 4'd0; tcnt <= {1'b0, BAUD_DIV} - 10'd1;
            tbi <= 4'd0; tsr <= 10'h3FF; uart_tx <= 1'b1;
            for (ti = 0; ti < 15; ti = ti + 1) tx_buf[ti] <= 8'hFF;
        end else begin
            uart_tx <= tsr[0];

            if (result_ready) begin
                tx_buf[0]  <= 8'hA5;
                tx_buf[1]  <= y_reg;
                tx_buf[2]  <= 8'h01;              // STATUS ok
                tx_buf[3]  <= nonce_b[0];
                tx_buf[4]  <= nonce_b[1];
                tx_buf[5]  <= nonce_b[2];
                tx_buf[6]  <= nonce_b[3];
                tx_buf[7]  <= NODE_ID[7:0];
                tx_buf[8]  <= NODE_ID[15:8];
                tx_buf[9]  <= NODE_ID[23:16];
                tx_buf[10] <= NODE_ID[31:24];
                tx_buf[11] <= crc_reg[7:0];
                tx_buf[12] <= crc_reg[15:8];
                tx_buf[13] <= crc_reg[23:16];
                tx_buf[14] <= crc_reg[31:24];
                responding <= 1'b1;
                tx_idx     <= 4'd0;
            end

            if (tcnt == 10'd0) begin
                tcnt <= {1'b0, BAUD_DIV} - 10'd1;
                if (tbi == 4'd9) begin
                    tbi <= 4'd0;
                    if (responding) begin
                        tsr <= {1'b1, tx_buf[tx_idx], 1'b0};
                        if (tx_idx == 4'd14) responding <= 1'b0;
                        else tx_idx <= tx_idx + 4'd1;
                    end else tsr <= 10'h3FF;
                end else begin
                    tbi <= tbi + 4'd1;
                    tsr <= {1'b1, tsr[9:1]};
                end
            end else tcnt <= tcnt - 10'd1;
        end
    end

    //-------------------------------------------------------------------------
    // LEDs: heartbeat, frame seen, result non-zero, not-in-reset.
    //-------------------------------------------------------------------------
    assign led[0] = heartbeat[25];
    assign led[1] = frame_valid;
    assign led[2] = |y_reg;
    assign led[3] = ~rst;

endmodule
`default_nettype wire
