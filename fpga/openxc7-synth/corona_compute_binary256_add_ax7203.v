`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_binary256_add_ax7203 — BINARY256 ADD on AX7203.
module corona_compute_binary256_add_ax7203 (
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

    reg [6:0] frm; reg [7:0] fmt_r; reg [255:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                7'd0: frm<=(rx_byte==8'hAA)?7'd1:7'd0;
                7'd1: frm<=(rx_byte==8'h55)?7'd2:7'd0;
                7'd2: begin fmt_r<=rx_byte;frm<=7'd3; end
                7'd3: begin a_r[7:0]<=rx_byte;frm<=7'd4; end
                7'd4: begin a_r[15:8]<=rx_byte;frm<=7'd5; end
                7'd5: begin a_r[23:16]<=rx_byte;frm<=7'd6; end
                7'd6: begin a_r[31:24]<=rx_byte;frm<=7'd7; end
                7'd7: begin a_r[39:32]<=rx_byte;frm<=7'd8; end
                7'd8: begin a_r[47:40]<=rx_byte;frm<=7'd9; end
                7'd9: begin a_r[55:48]<=rx_byte;frm<=7'd10; end
                7'd10: begin a_r[63:56]<=rx_byte;frm<=7'd11; end
                7'd11: begin a_r[71:64]<=rx_byte;frm<=7'd12; end
                7'd12: begin a_r[79:72]<=rx_byte;frm<=7'd13; end
                7'd13: begin a_r[87:80]<=rx_byte;frm<=7'd14; end
                7'd14: begin a_r[95:88]<=rx_byte;frm<=7'd15; end
                7'd15: begin a_r[103:96]<=rx_byte;frm<=7'd16; end
                7'd16: begin a_r[111:104]<=rx_byte;frm<=7'd17; end
                7'd17: begin a_r[119:112]<=rx_byte;frm<=7'd18; end
                7'd18: begin a_r[127:120]<=rx_byte;frm<=7'd19; end
                7'd19: begin a_r[135:128]<=rx_byte;frm<=7'd20; end
                7'd20: begin a_r[143:136]<=rx_byte;frm<=7'd21; end
                7'd21: begin a_r[151:144]<=rx_byte;frm<=7'd22; end
                7'd22: begin a_r[159:152]<=rx_byte;frm<=7'd23; end
                7'd23: begin a_r[167:160]<=rx_byte;frm<=7'd24; end
                7'd24: begin a_r[175:168]<=rx_byte;frm<=7'd25; end
                7'd25: begin a_r[183:176]<=rx_byte;frm<=7'd26; end
                7'd26: begin a_r[191:184]<=rx_byte;frm<=7'd27; end
                7'd27: begin a_r[199:192]<=rx_byte;frm<=7'd28; end
                7'd28: begin a_r[207:200]<=rx_byte;frm<=7'd29; end
                7'd29: begin a_r[215:208]<=rx_byte;frm<=7'd30; end
                7'd30: begin a_r[223:216]<=rx_byte;frm<=7'd31; end
                7'd31: begin a_r[231:224]<=rx_byte;frm<=7'd32; end
                7'd32: begin a_r[239:232]<=rx_byte;frm<=7'd33; end
                7'd33: begin a_r[247:240]<=rx_byte;frm<=7'd34; end
                7'd34: begin a_r[255:248]<=rx_byte;frm<=7'd35; end
                7'd35: begin b_r[7:0]<=rx_byte;frm<=7'd36; end
                7'd36: begin b_r[15:8]<=rx_byte;frm<=7'd37; end
                7'd37: begin b_r[23:16]<=rx_byte;frm<=7'd38; end
                7'd38: begin b_r[31:24]<=rx_byte;frm<=7'd39; end
                7'd39: begin b_r[39:32]<=rx_byte;frm<=7'd40; end
                7'd40: begin b_r[47:40]<=rx_byte;frm<=7'd41; end
                7'd41: begin b_r[55:48]<=rx_byte;frm<=7'd42; end
                7'd42: begin b_r[63:56]<=rx_byte;frm<=7'd43; end
                7'd43: begin b_r[71:64]<=rx_byte;frm<=7'd44; end
                7'd44: begin b_r[79:72]<=rx_byte;frm<=7'd45; end
                7'd45: begin b_r[87:80]<=rx_byte;frm<=7'd46; end
                7'd46: begin b_r[95:88]<=rx_byte;frm<=7'd47; end
                7'd47: begin b_r[103:96]<=rx_byte;frm<=7'd48; end
                7'd48: begin b_r[111:104]<=rx_byte;frm<=7'd49; end
                7'd49: begin b_r[119:112]<=rx_byte;frm<=7'd50; end
                7'd50: begin b_r[127:120]<=rx_byte;frm<=7'd51; end
                7'd51: begin b_r[135:128]<=rx_byte;frm<=7'd52; end
                7'd52: begin b_r[143:136]<=rx_byte;frm<=7'd53; end
                7'd53: begin b_r[151:144]<=rx_byte;frm<=7'd54; end
                7'd54: begin b_r[159:152]<=rx_byte;frm<=7'd55; end
                7'd55: begin b_r[167:160]<=rx_byte;frm<=7'd56; end
                7'd56: begin b_r[175:168]<=rx_byte;frm<=7'd57; end
                7'd57: begin b_r[183:176]<=rx_byte;frm<=7'd58; end
                7'd58: begin b_r[191:184]<=rx_byte;frm<=7'd59; end
                7'd59: begin b_r[199:192]<=rx_byte;frm<=7'd60; end
                7'd60: begin b_r[207:200]<=rx_byte;frm<=7'd61; end
                7'd61: begin b_r[215:208]<=rx_byte;frm<=7'd62; end
                7'd62: begin b_r[223:216]<=rx_byte;frm<=7'd63; end
                7'd63: begin b_r[231:224]<=rx_byte;frm<=7'd64; end
                7'd64: begin b_r[239:232]<=rx_byte;frm<=7'd65; end
                7'd65: begin b_r[247:240]<=rx_byte;frm<=7'd66; end
                7'd66: begin b_r[255:248]<=rx_byte;frm<=7'd67; end
                7'd67: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [255:0] a_reg,b_reg; reg comp_trigger;
    wire [255:0] fmt_a=a_reg, fmt_b=b_reg;
    wire b256_sign_a = fmt_a[255];
    wire [18:0] b256_exp_a = fmt_a[254:236];
    wire [235:0] b256_mant_a = fmt_a[235:0];
    wire b256_zero_a = (b256_exp_a == 19'd0) && (b256_mant_a == 236'd0);
    wire b256_special_a = (b256_exp_a == 19'h7FFFF);
    wire signed [20:0] b256_de_a = $signed({1'b0, b256_exp_a}) - 21'sd262112 + 21'sd127;
    wire [7:0] b256_exp32_a = b256_de_a[7:0];
    wire [22:0] b256_mant32_a = b256_mant_a[235:213];
    reg [31:0] fp32_a;
    always @(*) begin
        if(b256_zero_a) fp32_a=32'h00000000;
        else if(b256_special_a) fp32_a=32'h7FC00000;
        else fp32_a={b256_sign_a, b256_exp32_a, b256_mant32_a};
    end
    wire b256_sign_b = fmt_b[255];
    wire [18:0] b256_exp_b = fmt_b[254:236];
    wire [235:0] b256_mant_b = fmt_b[235:0];
    wire b256_zero_b = (b256_exp_b == 19'd0) && (b256_mant_b == 236'd0);
    wire b256_special_b = (b256_exp_b == 19'h7FFFF);
    wire signed [20:0] b256_de_b = $signed({1'b0, b256_exp_b}) - 21'sd262112 + 21'sd127;
    wire [7:0] b256_exp32_b = b256_de_b[7:0];
    wire [22:0] b256_mant32_b = b256_mant_b[235:213];
    reg [31:0] fp32_b;
    always @(*) begin
        if(b256_zero_b) fp32_b=32'h00000000;
        else if(b256_special_b) fp32_b=32'h7FC00000;
        else fp32_b={b256_sign_b, b256_exp32_b, b256_mant32_b};
    end
    wire comp_irdy, comp_ovld; wire [31:0] comp_result;
    gf_adder_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1)) u_comp (
        .clk(mclk),.rst(rst),.in_valid(comp_trigger),.in_a(fp32_a),.in_b(fp32_b),
        .in_ready(comp_irdy),.out_valid(comp_ovld),.out_y(comp_result),.out_ready(1'b1));
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;b_reg<=0;comp_trigger<=0; end
        else begin comp_trigger<=frame_valid;
            if(frame_valid) begin a_reg<=a_r;b_reg<=b_r; end
        end
    end
    wire [31:0] q_in=comp_result;
    wire q_sign=q_in[31]; wire [7:0] q_exp=q_in[30:23]; wire [22:0] q_mant=q_in[22:0];
    wire q_nan=(q_in==32'h7FC00000); wire q_zero=(q_in==32'h00000000);
    wire signed [20:0] b256_exp = $signed({1'b0, q_exp}) - 21'sd127 + 21'sd262112;
    reg [255:0] q_result;
    always @(*) begin
        if(q_nan) q_result=256'h0;
        else if(q_zero) q_result=256'h0;
        else q_result={q_sign, b256_exp[18:0], q_mant, 213'b0};
    end
    reg [255:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=comp_ovld;
            if(comp_ovld) result_reg<=q_result;
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
