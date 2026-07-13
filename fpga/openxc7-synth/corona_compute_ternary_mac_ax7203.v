`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_ternary_mac_ax7203 — Ternary MAC UART wrapper for AX7203.
// Wraps ternary_mac_16.v logic with UART for HW conformance.
// Frame: AA 55 fmt a[0..3] b[0..3] trig → A5 result[0..4] (5-bit signed dot product)
module corona_compute_ternary_mac_ax7203 (
    input wire rst_n, input wire uart_rx, output reg uart_tx, output wire [3:0] led
);
    wire mclk, eos;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startup (
        .CFGCLK(), .CFGMCLK(mclk), .EOS(eos),
        .CLK(1'b0),.GSR(1'b0),.GTS(1'b0),.KEYCLEARB(1'b0),.PACK(1'b0),
        .USRCCLKO(1'b0),.USRCCLKTS(1'b0),.USRDONEO(1'b0),.USRDONETS(1'b0));
    wire rst = ~rst_n | ~eos;
    localparam [8:0] BAUD_DIV = 9'd434;
    reg [26:0] cnt_c;
    always @(posedge mclk or posedge rst) if(rst) cnt_c<=0; else cnt_c<=cnt_c+1;
    assign led[0]=cnt_c[25]; assign led[3]=~rst;
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst) if(rst) rsync<=3'b111; else rsync<={rsync[1:0],uart_rx};
    wire rxd=rsync[2];
    reg [1:0] rxs; reg [9:0] rxcnt; reg [3:0] rbi; reg [7:0] rxsr; reg [7:0] rx_byte; reg rx_new;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin rxs<=0;rxcnt<=0;rbi<=0;rxsr<=0;rx_byte<=0;rx_new<=0; end
        else begin rx_new<=0;
            case(rxs)
                2'd0: if(~rxd) begin rxcnt<=(BAUD_DIV+(BAUD_DIV>>1))-1;rxs<=1;rbi<=0; end
                2'd1: begin if(rxcnt==0) begin rxsr<={rxd,rxsr[7:1]}; if(rbi==7) begin rxs<=2;rxcnt<=BAUD_DIV-1; end else begin rbi<=rbi+1;rxcnt<=BAUD_DIV-1; end end else rxcnt<=rxcnt-1; end
                2'd2: begin if(rxcnt==0) begin rx_byte<=rxsr;rx_new<=1;rxs<=0; end else rxcnt<=rxcnt-1; end
                default: rxs<=0;
            endcase
        end
    end

    // Frame FSM: AA 55 fmt w0 w1 w2 w3 x0 x1 x2 x3 trig (11 bytes)
    reg [3:0] frm; reg [7:0] fmt_r; reg [31:0] w_r, x_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;w_r<=0;x_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                4'd0: frm<=(rx_byte==8'hAA)?4'd1:4'd0;
                4'd1: frm<=(rx_byte==8'h55)?4'd2:4'd0;
                4'd2: begin fmt_r<=rx_byte;frm<=4'd3; end
                4'd3: begin w_r[7:0]<=rx_byte;frm<=4'd4; end
                4'd4: begin w_r[15:8]<=rx_byte;frm<=4'd5; end
                4'd5: begin w_r[23:16]<=rx_byte;frm<=4'd6; end
                4'd6: begin w_r[31:24]<=rx_byte;frm<=4'd7; end
                4'd7: begin x_r[7:0]<=rx_byte;frm<=4'd8; end
                4'd8: begin x_r[15:8]<=rx_byte;frm<=4'd9; end
                4'd9: begin x_r[23:16]<=rx_byte;frm<=4'd10; end
                4'd10: begin x_r[31:24]<=rx_byte;frm<=4'd11; end
                4'd11: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    // Ternary MAC: 16-element dot product, w×x, result = sum of w[i]*x[i]
    // Encoding: 00=-1, 01=0, 10=+1
    reg [31:0] w_reg, x_reg; reg comp_trigger;
    reg [31:0] result_reg; reg result_ready;

    // Ternary multiply: returns +1, 0, or -1
    function signed [1:0] ternary_mul;
        input [1:0] a, b;
        reg a_val, b_val, a_neg, b_neg;
        begin
            a_neg = (a == 2'b00);
            b_neg = (b == 2'b00);
            a_val = (a == 2'b10) || a_neg;  // nonzero
            b_val = (b == 2'b10) || b_neg;
            if (!a_val || !b_val)
                ternary_mul = 0;
            else if (a_neg ^ b_neg)
                ternary_mul = -1;  // signs differ
            else
                ternary_mul = 1;   // signs same
        end
    endfunction

    // Combinational dot product (16 elements)
    reg signed [5:0] dot_result;
    integer k;
    always @(*) begin
        dot_result = 0;
        for (k = 0; k < 16; k = k + 1) begin
            dot_result = dot_result + ternary_mul(w_reg[2*k +: 2], x_reg[2*k +: 2]);
        end
    end

    always @(posedge mclk or posedge rst) begin
        if(rst) begin
            w_reg<=0;x_reg<=0;comp_trigger<=0;
            result_reg<=0;result_ready<=0;
        end else begin
            comp_trigger<=frame_valid;
            result_ready<=0;
            if(frame_valid) begin w_reg<=w_r;x_reg<=x_r; end
            if(comp_trigger) begin
                // Pack 5-bit signed result into 32-bit
                result_reg <= {27'b0, dot_result[4:0]};
                result_ready <= 1;
            end
        end
    end
    assign led[2]=|result_reg;

    // UART TX: send A5 + 4 bytes
    reg responding; reg [2:0] tx_idx; reg [7:0] tx_buf0,tx_buf1,tx_buf2,tx_buf3,tx_buf4;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF;tx_buf1<=8'hFF;tx_buf2<=8'hFF;tx_buf3<=8'hFF;tx_buf4<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=8'hA5; tx_buf1<=result_reg[7:0]; tx_buf2<=result_reg[15:8];
                tx_buf3<=result_reg[23:16]; tx_buf4<=result_reg[31:24]; responding<=1; tx_idx<=0;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        case(tx_idx)
                            3'd0: tsr<={1'b1,tx_buf0,1'b0}; 3'd1: tsr<={1'b1,tx_buf1,1'b0};
                            3'd2: tsr<={1'b1,tx_buf2,1'b0}; 3'd3: tsr<={1'b1,tx_buf3,1'b0};
                            3'd4: tsr<={1'b1,tx_buf4,1'b0};
                        endcase
                        if(tx_idx==4) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
endmodule
`default_nettype wire
