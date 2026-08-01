`default_nettype wire
`timescale 1ns / 1ps
//=============================================================================
// trinet_dna_probe_ax7203 — can a TRI-NET receipt be bound to this chip?
//
// Reads the Xilinx 7-series factory device DNA through the DNA_PORT primitive
// and streams it over the same UART the compute nodes use. The point is to
// answer one question that the whole "FPGA compute network" claim rests on:
// is any device-bound identity reachable at all through the open toolchain?
//
// The question has three parts and this cell answers the first two.
//   1. Does yosys know DNA_PORT?              answered: yes, it survives synth
//   2. Does nextpnr-xilinx place and route it? answered by building this cell
//   3. Is the DNA usable as a receipt secret?  NO — see the note below
//
// WHAT DEVICE DNA IS NOT. The DNA is a factory-programmed identifier, not a
// key. It is readable over JTAG and by any bitstream loaded on the part, so
// once a value has been read once, software can claim it forever. Binding a
// receipt to the DNA therefore proves that a *bitstream asserted* a particular
// identity — it does not prove the arithmetic happened on that chip, and it
// does not make a receipt unforgeable. Unforgeability needs a secret that
// never leaves the device, which on this part means a key in eFUSE or BBRAM
// plus an encrypted bitstream. Recording that limit here so the probe's result
// cannot be over-read later.
//
// REQUEST  (4 bytes):  AA 55 OP TRIG
// RESPONSE (11 bytes): A5 STATUS DNA[8] BITS
//   STATUS 0x01 = the read sequence completed
//   DNA    little-endian, 57 significant bits zero-extended to 64
//   BITS   number of significant bits (57), so a host cannot mistake padding
//          for data
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module trinet_dna_probe_ax7203 (
    input  wire rst_n,
    input  wire uart_rx,
    output reg  uart_tx,
    output wire [3:0] led
);

    localparam integer DNA_BITS = 57;

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
    // Frame parser — AA 55 OP TRIG.
    //-------------------------------------------------------------------------
    reg [1:0] fstate;
    reg [7:0] op_r;
    reg       frame_valid;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin fstate <= 2'd0; op_r <= 8'd0; frame_valid <= 1'b0; end
        else begin
            frame_valid <= 1'b0;
            if (rx_new) begin
                case (fstate)
                    2'd0: fstate <= (rx_byte == 8'hAA) ? 2'd1 : 2'd0;
                    2'd1: begin
                        if (rx_byte == 8'h55) fstate <= 2'd2;
                        else if (rx_byte == 8'hAA) fstate <= 2'd1;
                        else fstate <= 2'd0;
                    end
                    2'd2: begin op_r <= rx_byte; fstate <= 2'd3; end
                    2'd3: begin frame_valid <= 1'b1; fstate <= 2'd0; end
                endcase
            end
        end
    end

    //-------------------------------------------------------------------------
    // Device DNA read.
    //
    // READ high for one clock loads the DNA into the primitive's shift
    // register; SHIFT then walks it out one bit per clock on DOUT.
    //-------------------------------------------------------------------------
    wire dna_dout;
    reg  dna_read, dna_shift;

    DNA_PORT #(.SIM_DNA_VALUE(57'h0AB_CDEF_1234_5678)) u_dna (
        .DOUT(dna_dout),
        .CLK(mclk),
        .DIN(1'b0),
        .READ(dna_read),
        .SHIFT(dna_shift));

    localparam [2:0] D_IDLE = 3'd0,
                     D_LOAD = 3'd1,
                     D_SHIFT = 3'd2,
                     D_DONE = 3'd3;

    reg [2:0]  dstate;
    reg [5:0]  dbit;
    reg [63:0] dna_reg;
    reg        dna_valid;
    reg        respond;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            dstate <= D_IDLE; dbit <= 6'd0; dna_reg <= 64'd0;
            dna_read <= 1'b0; dna_shift <= 1'b0; dna_valid <= 1'b0; respond <= 1'b0;
        end else begin
            respond <= 1'b0;
            case (dstate)
                D_IDLE: begin
                    dna_read <= 1'b0; dna_shift <= 1'b0;
                    if (frame_valid) begin
                        if (dna_valid) begin
                            // Already read once — the DNA does not change, so
                            // answer immediately rather than re-shifting.
                            respond <= 1'b1;
                        end else begin
                            dna_read <= 1'b1;
                            dstate <= D_LOAD;
                        end
                    end
                end
                D_LOAD: begin
                    dna_read <= 1'b0;
                    dna_shift <= 1'b1;
                    dbit <= 6'd0;
                    dstate <= D_SHIFT;
                end
                D_SHIFT: begin
                    // Shift left, inserting at the bottom, so after DNA_BITS
                    // cycles the first bit read sits at dna_reg[DNA_BITS-1].
                    dna_reg <= {dna_reg[62:0], dna_dout};
                    if (dbit == DNA_BITS[5:0] - 6'd1) begin
                        dna_shift <= 1'b0;
                        dna_valid <= 1'b1;
                        dstate <= D_DONE;
                    end else dbit <= dbit + 6'd1;
                end
                D_DONE: begin
                    respond <= 1'b1;
                    dstate <= D_IDLE;
                end
                default: dstate <= D_IDLE;
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // UART transmit — 11-byte response.
    //-------------------------------------------------------------------------
    reg        responding;
    reg [3:0]  tx_idx;
    reg [7:0]  tx_buf [0:10];
    reg [9:0]  tcnt;
    reg [3:0]  tbi;
    reg [9:0]  tsr;

    integer ti;
    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            responding <= 1'b0; tx_idx <= 4'd0; tcnt <= {1'b0, BAUD_DIV} - 10'd1;
            tbi <= 4'd0; tsr <= 10'h3FF; uart_tx <= 1'b1;
            for (ti = 0; ti < 11; ti = ti + 1) tx_buf[ti] <= 8'hFF;
        end else begin
            uart_tx <= tsr[0];

            if (respond) begin
                tx_buf[0]  <= 8'hA5;
                tx_buf[1]  <= dna_valid ? 8'h01 : 8'h00;
                tx_buf[2]  <= dna_reg[7:0];
                tx_buf[3]  <= dna_reg[15:8];
                tx_buf[4]  <= dna_reg[23:16];
                tx_buf[5]  <= dna_reg[31:24];
                tx_buf[6]  <= dna_reg[39:32];
                tx_buf[7]  <= dna_reg[47:40];
                tx_buf[8]  <= dna_reg[55:48];
                tx_buf[9]  <= dna_reg[63:56];
                tx_buf[10] <= DNA_BITS[7:0];
                responding <= 1'b1;
                tx_idx     <= 4'd0;
            end

            if (tcnt == 10'd0) begin
                tcnt <= {1'b0, BAUD_DIV} - 10'd1;
                if (tbi == 4'd9) begin
                    tbi <= 4'd0;
                    if (responding) begin
                        tsr <= {1'b1, tx_buf[tx_idx], 1'b0};
                        if (tx_idx == 4'd10) responding <= 1'b0;
                        else tx_idx <= tx_idx + 4'd1;
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
    assign led[2] = dna_valid;
    assign led[3] = ~rst;

endmodule
`default_nettype wire
