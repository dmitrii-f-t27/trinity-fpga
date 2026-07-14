`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_fp32_to_quad_double_ax7203 — QUAD_DOUBLE FP32_TO on AX7203.
module corona_compute_fp32_to_quad_double_ax7203 (
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

    reg [2:0] frm; reg [7:0] fmt_r; reg [31:0] a_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3'd3; end
                3'd3: begin a_r[7:0]<=rx_byte;frm<=3'd4; end
                3'd4: begin a_r[15:8]<=rx_byte;frm<=3'd5; end
                3'd5: begin a_r[23:16]<=rx_byte;frm<=3'd6; end
                3'd6: begin a_r[31:24]<=rx_byte;frm<=0; frame_valid<=1; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [31:0] a_reg; reg conv_trigger;
    wire [31:0] q_in = a_reg;
    wire q_sign=q_in[31]; wire [7:0] q_exp=q_in[30:23]; wire [22:0] q_mant=q_in[22:0];
    wire q_nan=(q_in==32'h7FC00000); wire q_zero=(q_in==32'h00000000);
    wire signed [12:0] qd_exp = $signed({1'b0, q_exp}) - 13'sd127 + 13'sd1023;
    reg [255:0] q_result;
    always @(*) begin
        if(q_nan) q_result=256'h0;
        else if(q_zero) q_result=256'h0;
        else q_result={q_sign, qd_exp[10:0], q_mant, 29'b0, 192'b0};
    end
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;conv_trigger<=0; end
        else begin conv_trigger<=frame_valid;
            if(frame_valid) a_reg<=a_r;
        end
    end
    reg [255:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=conv_trigger;
            if(conv_trigger) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [5:0] TX_LEN = 33;
    // TX: buffer+mux (no conflicting NBA — fixes tx race). 33 bytes sliced from tx_load[263:0].
    wire [263:0] tx_load = {result_reg, 8'hA5};
    reg responding; reg [5:0] tx_idx; reg [7:0] tx_buf0, tx_buf1, tx_buf2, tx_buf3, tx_buf4, tx_buf5, tx_buf6, tx_buf7, tx_buf8, tx_buf9, tx_buf10, tx_buf11, tx_buf12, tx_buf13, tx_buf14, tx_buf15, tx_buf16, tx_buf17, tx_buf18, tx_buf19, tx_buf20, tx_buf21, tx_buf22, tx_buf23, tx_buf24, tx_buf25, tx_buf26, tx_buf27, tx_buf28, tx_buf29, tx_buf30, tx_buf31, tx_buf32;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF; tx_buf1<=8'hFF; tx_buf2<=8'hFF; tx_buf3<=8'hFF; tx_buf4<=8'hFF; tx_buf5<=8'hFF; tx_buf6<=8'hFF; tx_buf7<=8'hFF; tx_buf8<=8'hFF; tx_buf9<=8'hFF; tx_buf10<=8'hFF; tx_buf11<=8'hFF; tx_buf12<=8'hFF; tx_buf13<=8'hFF; tx_buf14<=8'hFF; tx_buf15<=8'hFF; tx_buf16<=8'hFF; tx_buf17<=8'hFF; tx_buf18<=8'hFF; tx_buf19<=8'hFF; tx_buf20<=8'hFF; tx_buf21<=8'hFF; tx_buf22<=8'hFF; tx_buf23<=8'hFF; tx_buf24<=8'hFF; tx_buf25<=8'hFF; tx_buf26<=8'hFF; tx_buf27<=8'hFF; tx_buf28<=8'hFF; tx_buf29<=8'hFF; tx_buf30<=8'hFF; tx_buf31<=8'hFF; tx_buf32<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=tx_load[7:0]; tx_buf1<=tx_load[15:8]; tx_buf2<=tx_load[23:16]; tx_buf3<=tx_load[31:24]; tx_buf4<=tx_load[39:32]; tx_buf5<=tx_load[47:40]; tx_buf6<=tx_load[55:48]; tx_buf7<=tx_load[63:56]; tx_buf8<=tx_load[71:64]; tx_buf9<=tx_load[79:72]; tx_buf10<=tx_load[87:80]; tx_buf11<=tx_load[95:88]; tx_buf12<=tx_load[103:96]; tx_buf13<=tx_load[111:104]; tx_buf14<=tx_load[119:112]; tx_buf15<=tx_load[127:120]; tx_buf16<=tx_load[135:128]; tx_buf17<=tx_load[143:136]; tx_buf18<=tx_load[151:144]; tx_buf19<=tx_load[159:152]; tx_buf20<=tx_load[167:160]; tx_buf21<=tx_load[175:168]; tx_buf22<=tx_load[183:176]; tx_buf23<=tx_load[191:184]; tx_buf24<=tx_load[199:192]; tx_buf25<=tx_load[207:200]; tx_buf26<=tx_load[215:208]; tx_buf27<=tx_load[223:216]; tx_buf28<=tx_load[231:224]; tx_buf29<=tx_load[239:232]; tx_buf30<=tx_load[247:240]; tx_buf31<=tx_load[255:248]; tx_buf32<=tx_load[263:256]; responding<=1; tx_idx<=0;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        case(tx_idx)
                            6'd0: tsr<={1'b1,tx_buf0,1'b0};
                            6'd1: tsr<={1'b1,tx_buf1,1'b0};
                            6'd2: tsr<={1'b1,tx_buf2,1'b0};
                            6'd3: tsr<={1'b1,tx_buf3,1'b0};
                            6'd4: tsr<={1'b1,tx_buf4,1'b0};
                            6'd5: tsr<={1'b1,tx_buf5,1'b0};
                            6'd6: tsr<={1'b1,tx_buf6,1'b0};
                            6'd7: tsr<={1'b1,tx_buf7,1'b0};
                            6'd8: tsr<={1'b1,tx_buf8,1'b0};
                            6'd9: tsr<={1'b1,tx_buf9,1'b0};
                            6'd10: tsr<={1'b1,tx_buf10,1'b0};
                            6'd11: tsr<={1'b1,tx_buf11,1'b0};
                            6'd12: tsr<={1'b1,tx_buf12,1'b0};
                            6'd13: tsr<={1'b1,tx_buf13,1'b0};
                            6'd14: tsr<={1'b1,tx_buf14,1'b0};
                            6'd15: tsr<={1'b1,tx_buf15,1'b0};
                            6'd16: tsr<={1'b1,tx_buf16,1'b0};
                            6'd17: tsr<={1'b1,tx_buf17,1'b0};
                            6'd18: tsr<={1'b1,tx_buf18,1'b0};
                            6'd19: tsr<={1'b1,tx_buf19,1'b0};
                            6'd20: tsr<={1'b1,tx_buf20,1'b0};
                            6'd21: tsr<={1'b1,tx_buf21,1'b0};
                            6'd22: tsr<={1'b1,tx_buf22,1'b0};
                            6'd23: tsr<={1'b1,tx_buf23,1'b0};
                            6'd24: tsr<={1'b1,tx_buf24,1'b0};
                            6'd25: tsr<={1'b1,tx_buf25,1'b0};
                            6'd26: tsr<={1'b1,tx_buf26,1'b0};
                            6'd27: tsr<={1'b1,tx_buf27,1'b0};
                            6'd28: tsr<={1'b1,tx_buf28,1'b0};
                            6'd29: tsr<={1'b1,tx_buf29,1'b0};
                            6'd30: tsr<={1'b1,tx_buf30,1'b0};
                            6'd31: tsr<={1'b1,tx_buf31,1'b0};
                            6'd32: tsr<={1'b1,tx_buf32,1'b0};
                        endcase
                        if(tx_idx==32) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
    endmodule
`default_nettype wire
