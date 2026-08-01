`default_nettype wire
`timescale 1ns / 1ps
//=============================================================================
// trinet_node_v2_ax7203 — the TRI-NET compute node with a keyed receipt.
//
// Same ternary datapath as trinet_mac32_ax7203 — a 32-wide dot product taken
// as popcount(agreements) minus popcount(disagreements), no multiplier, no DSP
// — with the receipt tag upgraded from CRC-32 to SipHash-2-4 under a key that
// exists only inside the bitstream.
//
// WHY THE CHANGE. A CRC tag proves a response is self-consistent with its job.
// It proves nothing about who produced it, because the function is keyless and
// anyone can compute it. A keyed tag can only be produced by a key holder, so
// a receipt becomes evidence of authorship rather than of arithmetic.
//
// WHAT IT STILL DOES NOT PROVE. The key lives in the bitstream, and the node
// operator holds the bitstream. So this stops third parties forging receipts
// on an operator's behalf, and with per-node keys it stops one operator forging
// for another — it does not stop an operator forging their own. Closing that
// needs a key that never leaves the device: on 7-series, an eFUSE or BBRAM key
// with an encrypted bitstream.
//
// NODE IDENTITY. With USE_DNA = 1 the node id is taken from the factory device
// DNA, so it is tied to the physical part rather than chosen at synthesis. That
// is worth having and worth not over-reading: the DNA is readable over JTAG and
// by any bitstream on the part, so it is an identifier, not a secret. It stops
// an operator accidentally shipping two boards with the same id; it does not
// stop software claiming an id it has seen.
//
// REQUEST  (24 bytes): AA 55 OP NONCE[4] W[8] X[8] TRIG
// RESPONSE (19 bytes): A5 Y STATUS NONCE[4] NODE_ID[4] TAG[8]
//
// TAG = SipHash-2-4 over OP | NONCE[4] | W[8] | X[8] | Y | NODE_ID[4].
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module trinet_node_v2_ax7203 #(
    parameter integer USE_DNA = 1,
    parameter [31:0]  FALLBACK_NODE_ID = 32'h5452_494E,   // "TRIN"
    // Per-node secret. A deployment must override this; the default exists so
    // the cell builds and simulates, not so it ships.
    parameter [127:0] RECEIPT_KEY = 128'h0f0e0d0c0b0a09080706050403020100
) (
    input  wire rst_n,
    input  wire uart_rx,
    output reg  uart_tx,
    output wire [3:0] led
);

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
    // Node identity.
    //-------------------------------------------------------------------------
    wire [31:0] node_id;
    generate
        if (USE_DNA != 0) begin : gen_dna_id
            wire dna_dout;
            reg  dna_read, dna_shift;
            reg [5:0]  dna_bit;
            reg [63:0] dna_sr;
            reg        dna_ready;
            reg [1:0]  dna_st;

            DNA_PORT #(.SIM_DNA_VALUE(57'h0AB_CDEF_1234_5678)) u_dna (
                .DOUT(dna_dout), .CLK(mclk), .DIN(1'b0),
                .READ(dna_read), .SHIFT(dna_shift));

            always @(posedge mclk or posedge rst) begin
                if (rst) begin
                    dna_st <= 2'd0; dna_bit <= 6'd0; dna_sr <= 64'd0;
                    dna_read <= 1'b0; dna_shift <= 1'b0; dna_ready <= 1'b0;
                end else case (dna_st)
                    2'd0: begin dna_read <= 1'b1; dna_st <= 2'd1; end
                    2'd1: begin dna_read <= 1'b0; dna_shift <= 1'b1; dna_bit <= 6'd0; dna_st <= 2'd2; end
                    2'd2: begin
                        dna_sr <= {dna_sr[62:0], dna_dout};
                        if (dna_bit == 6'd56) begin
                            dna_shift <= 1'b0; dna_ready <= 1'b1; dna_st <= 2'd3;
                        end else dna_bit <= dna_bit + 6'd1;
                    end
                    default: ;
                endcase
            end
            // Measured on an AX7203 through openXC7 on 2026-08-01: the
            // primitive places and routes, the read sequence completes, and
            // DOUT is zero for all 57 bits. So an all-zero DNA is a real
            // outcome on this flow, not a transient, and it must never become
            // a node id — every board would claim the same one. Fall back
            // whenever the DNA is unavailable OR zero.
            assign node_id = (dna_ready && dna_sr[31:0] != 32'd0)
                           ? dna_sr[31:0] : FALLBACK_NODE_ID;
        end else begin : gen_param_id
            assign node_id = FALLBACK_NODE_ID;
        end
    endgenerate

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
    reg [4:0]  fstate;
    reg [4:0]  bidx;
    reg [7:0]  op_r;
    reg [7:0]  nonce_b [0:3];
    reg [7:0]  w_b     [0:7];
    reg [7:0]  x_b     [0:7];
    reg        frame_valid;

    localparam [4:0] F_MAGIC0 = 5'd0, F_MAGIC1 = 5'd1, F_BODY = 5'd2;

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
                        if      (bidx == 5'd0)  op_r            <= rx_byte;
                        else if (bidx <= 5'd4)  nonce_b[bidx-1] <= rx_byte;
                        else if (bidx <= 5'd12) w_b[bidx-5]     <= rx_byte;
                        else if (bidx <= 5'd20) x_b[bidx-13]    <= rx_byte;

                        if (bidx == 5'd21) begin
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
    // Ternary dot product — popcount(pos) - popcount(neg).
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
    // Keyed receipt.
    //-------------------------------------------------------------------------
    reg [7:0]  y_reg;
    reg [31:0] id_latched;
    reg        mac_start;

    // Preimage: OP | NONCE[4] | W[8] | X[8] | Y | NODE_ID[4], byte 0 low.
    wire [207:0] preimage = {
        id_latched[31:24], id_latched[23:16], id_latched[15:8], id_latched[7:0],
        y_reg,
        x_b[7], x_b[6], x_b[5], x_b[4], x_b[3], x_b[2], x_b[1], x_b[0],
        w_b[7], w_b[6], w_b[5], w_b[4], w_b[3], w_b[2], w_b[1], w_b[0],
        nonce_b[3], nonce_b[2], nonce_b[1], nonce_b[0],
        op_r
    };

    wire [63:0] mac_tag;
    wire        mac_done;

    trinet_siphash24 #(.MSG_BYTES(26)) u_mac (
        .clk(mclk), .rst(rst), .start(mac_start),
        .msg(preimage), .key(RECEIPT_KEY),
        .tag(mac_tag), .done(mac_done));

    reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            y_reg <= 8'd0; id_latched <= 32'd0; mac_start <= 1'b0; result_ready <= 1'b0;
        end else begin
            mac_start <= 1'b0;
            result_ready <= mac_done;
            if (frame_valid) begin
                y_reg      <= dot_result;
                id_latched <= node_id;
                mac_start  <= 1'b1;
            end
        end
    end

    //-------------------------------------------------------------------------
    // UART transmit — 19-byte response.
    //-------------------------------------------------------------------------
    reg        responding;
    reg [4:0]  tx_idx;
    reg [7:0]  tx_buf [0:18];
    reg [9:0]  tcnt;
    reg [3:0]  tbi;
    reg [9:0]  tsr;

    integer ti;
    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            responding <= 1'b0; tx_idx <= 5'd0; tcnt <= {1'b0, BAUD_DIV} - 10'd1;
            tbi <= 4'd0; tsr <= 10'h3FF; uart_tx <= 1'b1;
            for (ti = 0; ti < 19; ti = ti + 1) tx_buf[ti] <= 8'hFF;
        end else begin
            uart_tx <= tsr[0];

            if (result_ready) begin
                tx_buf[0]  <= 8'hA5;
                tx_buf[1]  <= y_reg;
                tx_buf[2]  <= 8'h01;
                tx_buf[3]  <= nonce_b[0];
                tx_buf[4]  <= nonce_b[1];
                tx_buf[5]  <= nonce_b[2];
                tx_buf[6]  <= nonce_b[3];
                tx_buf[7]  <= id_latched[7:0];
                tx_buf[8]  <= id_latched[15:8];
                tx_buf[9]  <= id_latched[23:16];
                tx_buf[10] <= id_latched[31:24];
                tx_buf[11] <= mac_tag[7:0];
                tx_buf[12] <= mac_tag[15:8];
                tx_buf[13] <= mac_tag[23:16];
                tx_buf[14] <= mac_tag[31:24];
                tx_buf[15] <= mac_tag[39:32];
                tx_buf[16] <= mac_tag[47:40];
                tx_buf[17] <= mac_tag[55:48];
                tx_buf[18] <= mac_tag[63:56];
                responding <= 1'b1;
                tx_idx     <= 5'd0;
            end

            if (tcnt == 10'd0) begin
                tcnt <= {1'b0, BAUD_DIV} - 10'd1;
                if (tbi == 4'd9) begin
                    tbi <= 4'd0;
                    if (responding) begin
                        tsr <= {1'b1, tx_buf[tx_idx], 1'b0};
                        if (tx_idx == 5'd18) responding <= 1'b0;
                        else tx_idx <= tx_idx + 5'd1;
                    end else tsr <= 10'h3FF;
                end else begin
                    tbi <= tbi + 4'd1;
                    tsr <= {1'b1, tsr[9:1]};
                end
            end else tcnt <= tcnt - 10'd1;
        end
    end

    assign led[0] = heartbeat[25];
    assign led[1] = frame_valid;
    assign led[2] = |y_reg;
    assign led[3] = ~rst;

endmodule
`default_nettype wire
