`default_nettype wire
`timescale 1ns / 1ps
//=============================================================================
// trinet_node_v2_ax7203 — board wrapper for the AX7203.
//
// The node itself is `fpga/portable/trinet_node_core.v`, which contains no
// vendor primitives and synthesises on seven FPGA families. Everything Xilinx
// about this design lives here, and it is only two things:
//
//   STARTUPE2  the configuration oscillator, used as the system clock.
//   DNA_PORT   the factory device identity.
//
// The wrapper instantiates the core rather than carrying its own copy on
// purpose. A parallel copy would drift, and the claim that the cell is portable
// would quietly stop being true while both files still worked.
//
// ON THE DNA. Measured on this board through openXC7 on 2026-08-01: the
// primitive places, routes and completes its read sequence, and DOUT is zero
// for all 57 bits. An all-zero DNA is therefore a real outcome on this flow,
// not a transient, and it must never become a node id — every board would claim
// the same one. Hence the fallback below.
//
// ON THE KEY. The default is deliberately all-zero. A plausible-looking default
// is how a real key ended up committed to a public repository once already; an
// obviously-null one fails loudly instead of looking secure. Any deployment
// must override it with a key the operator generated and did not commit.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module trinet_node_v2_ax7203 #(
    parameter integer USE_DNA = 1,
    parameter [31:0]  FALLBACK_NODE_ID = 32'h5452_494E,   // "TRIN"
    parameter [127:0] RECEIPT_KEY = 128'h0,
    // CFGMCLK divided by this is the line rate. CFGMCLK measured 2026-08-02 at
    // ~71.18 MHz on one board and ~72.07 on another — it is an internal RC
    // oscillator, so it is a property of the chip, not the part.
    parameter integer BAUD_DIV_P = 434
) (
    input  wire rst_n,
    input  wire uart_rx,
    output wire uart_tx,
    output wire [3:0] led
);

    wire mclk, eos;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startup (
        .CFGCLK(), .CFGMCLK(mclk), .EOS(eos),
        .CLK(1'b0), .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b0), .PACK(1'b0),
        .USRCCLKO(1'b0), .USRCCLKTS(1'b0), .USRDONEO(1'b0), .USRDONETS(1'b0));

    wire rst = ~rst_n | ~eos;

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

            assign node_id = (dna_ready && dna_sr[31:0] != 32'd0)
                           ? dna_sr[31:0] : FALLBACK_NODE_ID;
        end else begin : gen_param_id
            assign node_id = FALLBACK_NODE_ID;
        end
    endgenerate

    //-------------------------------------------------------------------------
    // The node.
    //-------------------------------------------------------------------------
    wire frame_seen, result_nonzero;

    trinet_node_core #(
        .BAUD_DIV_P(BAUD_DIV_P),
        .RECEIPT_KEY(RECEIPT_KEY)
    ) u_core (
        .clk(mclk),
        .rst(rst),
        .node_id(node_id),
        .uart_rx(uart_rx),
        .uart_tx(uart_tx),
        .frame_seen(frame_seen),
        .result_nonzero(result_nonzero)
    );

    assign led[0] = heartbeat[25];
    assign led[1] = frame_seen;
    assign led[2] = result_nonzero;
    assign led[3] = ~rst;

endmodule
`default_nettype wire
