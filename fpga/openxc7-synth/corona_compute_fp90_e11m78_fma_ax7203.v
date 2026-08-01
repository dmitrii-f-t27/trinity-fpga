`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_fp90_e11m78_fma_ax7203 — FP90_E11M78 FMA on AX7203.
module corona_compute_fp90_e11m78_fma_ax7203 (
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

    reg [5:0] frm; reg [7:0] fmt_r; reg [89:0] a_r,b_r,c_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;c_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                6'd0: frm<=(rx_byte==8'hAA)?6'd1:6'd0;
                6'd1: frm<=(rx_byte==8'h55)?6'd2:6'd0;
                6'd2: begin fmt_r<=rx_byte;frm<=6'd3; end
                6'd3: begin a_r[7:0]<=rx_byte;frm<=6'd4; end
                6'd4: begin a_r[15:8]<=rx_byte;frm<=6'd5; end
                6'd5: begin a_r[23:16]<=rx_byte;frm<=6'd6; end
                6'd6: begin a_r[31:24]<=rx_byte;frm<=6'd7; end
                6'd7: begin a_r[39:32]<=rx_byte;frm<=6'd8; end
                6'd8: begin a_r[47:40]<=rx_byte;frm<=6'd9; end
                6'd9: begin a_r[55:48]<=rx_byte;frm<=6'd10; end
                6'd10: begin a_r[63:56]<=rx_byte;frm<=6'd11; end
                6'd11: begin a_r[71:64]<=rx_byte;frm<=6'd12; end
                6'd12: begin a_r[79:72]<=rx_byte;frm<=6'd13; end
                6'd13: begin a_r[87:80]<=rx_byte;frm<=6'd14; end
                6'd14: begin a_r[89:88]<=rx_byte;frm<=6'd15; end
                6'd15: begin b_r[7:0]<=rx_byte;frm<=6'd16; end
                6'd16: begin b_r[15:8]<=rx_byte;frm<=6'd17; end
                6'd17: begin b_r[23:16]<=rx_byte;frm<=6'd18; end
                6'd18: begin b_r[31:24]<=rx_byte;frm<=6'd19; end
                6'd19: begin b_r[39:32]<=rx_byte;frm<=6'd20; end
                6'd20: begin b_r[47:40]<=rx_byte;frm<=6'd21; end
                6'd21: begin b_r[55:48]<=rx_byte;frm<=6'd22; end
                6'd22: begin b_r[63:56]<=rx_byte;frm<=6'd23; end
                6'd23: begin b_r[71:64]<=rx_byte;frm<=6'd24; end
                6'd24: begin b_r[79:72]<=rx_byte;frm<=6'd25; end
                6'd25: begin b_r[87:80]<=rx_byte;frm<=6'd26; end
                6'd26: begin b_r[89:88]<=rx_byte;frm<=6'd27; end
                6'd27: begin c_r[7:0]<=rx_byte;frm<=6'd28; end
                6'd28: begin c_r[15:8]<=rx_byte;frm<=6'd29; end
                6'd29: begin c_r[23:16]<=rx_byte;frm<=6'd30; end
                6'd30: begin c_r[31:24]<=rx_byte;frm<=6'd31; end
                6'd31: begin c_r[39:32]<=rx_byte;frm<=6'd32; end
                6'd32: begin c_r[47:40]<=rx_byte;frm<=6'd33; end
                6'd33: begin c_r[55:48]<=rx_byte;frm<=6'd34; end
                6'd34: begin c_r[63:56]<=rx_byte;frm<=6'd35; end
                6'd35: begin c_r[71:64]<=rx_byte;frm<=6'd36; end
                6'd36: begin c_r[79:72]<=rx_byte;frm<=6'd37; end
                6'd37: begin c_r[87:80]<=rx_byte;frm<=6'd38; end
                6'd38: begin c_r[89:88]<=rx_byte;frm<=6'd39; end
                6'd39: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [89:0] a_reg,b_reg,c_reg; reg comp_trigger;
    wire [89:0] fmt_a=a_reg, fmt_b=b_reg, fmt_c=c_reg;
    wire f_sign_a = fmt_a[89];
    wire [10:0] f_exp_a = fmt_a[88:78];
    wire [77:0] f_mant_a = fmt_a[77:0];
    wire f_zero_a = (f_exp_a == 0) && ((f_mant_a == 0));
    wire f_inf_a = (f_exp_a == 2047) && ((f_mant_a == 0));
    wire f_nan_a = (f_exp_a == 2047) && ((f_mant_a != 0));
    wire f_sub_a = (f_exp_a == 0) && ((f_mant_a != 0));
    wire signed [20:0] f_de_a = $signed({1'b0, f_exp_a}) - 21'sd1023 + 21'sd127;
    wire [7:0] f_exp32_a = (f_de_a > 21'sd254) ? 8'd254 : (f_de_a < 0) ? 8'd0 : f_de_a[7:0];
    wire [22:0] f_mant32_a = {f_mant_a, -55'b0};
    wire [22:0] f_mant32_norm_a = f_mant_a;
    reg [31:0] fp32_a;
    always @(*) begin
        if(f_zero_a) fp32_a=32'h00000000;
        else if(f_inf_a) fp32_a=f_sign_a?32'hFF800000:32'h7F800000;
        else if(f_nan_a) fp32_a=32'h7FC00000;
        else if(f_sub_a) fp32_a={f_sign_a, 8'd0, f_mant32_norm_a};
        else fp32_a={f_sign_a, f_exp32_a, f_mant32_a};
    end
    wire f_sign_b = fmt_b[89];
    wire [10:0] f_exp_b = fmt_b[88:78];
    wire [77:0] f_mant_b = fmt_b[77:0];
    wire f_zero_b = (f_exp_b == 0) && ((f_mant_b == 0));
    wire f_inf_b = (f_exp_b == 2047) && ((f_mant_b == 0));
    wire f_nan_b = (f_exp_b == 2047) && ((f_mant_b != 0));
    wire f_sub_b = (f_exp_b == 0) && ((f_mant_b != 0));
    wire signed [20:0] f_de_b = $signed({1'b0, f_exp_b}) - 21'sd1023 + 21'sd127;
    wire [7:0] f_exp32_b = (f_de_b > 21'sd254) ? 8'd254 : (f_de_b < 0) ? 8'd0 : f_de_b[7:0];
    wire [22:0] f_mant32_b = {f_mant_b, -55'b0};
    wire [22:0] f_mant32_norm_b = f_mant_b;
    reg [31:0] fp32_b;
    always @(*) begin
        if(f_zero_b) fp32_b=32'h00000000;
        else if(f_inf_b) fp32_b=f_sign_b?32'hFF800000:32'h7F800000;
        else if(f_nan_b) fp32_b=32'h7FC00000;
        else if(f_sub_b) fp32_b={f_sign_b, 8'd0, f_mant32_norm_b};
        else fp32_b={f_sign_b, f_exp32_b, f_mant32_b};
    end
    wire f_sign_c = fmt_c[89];
    wire [10:0] f_exp_c = fmt_c[88:78];
    wire [77:0] f_mant_c = fmt_c[77:0];
    wire f_zero_c = (f_exp_c == 0) && ((f_mant_c == 0));
    wire f_inf_c = (f_exp_c == 2047) && ((f_mant_c == 0));
    wire f_nan_c = (f_exp_c == 2047) && ((f_mant_c != 0));
    wire f_sub_c = (f_exp_c == 0) && ((f_mant_c != 0));
    wire signed [20:0] f_de_c = $signed({1'b0, f_exp_c}) - 21'sd1023 + 21'sd127;
    wire [7:0] f_exp32_c = (f_de_c > 21'sd254) ? 8'd254 : (f_de_c < 0) ? 8'd0 : f_de_c[7:0];
    wire [22:0] f_mant32_c = {f_mant_c, -55'b0};
    wire [22:0] f_mant32_norm_c = f_mant_c;
    reg [31:0] fp32_c;
    always @(*) begin
        if(f_zero_c) fp32_c=32'h00000000;
        else if(f_inf_c) fp32_c=f_sign_c?32'hFF800000:32'h7F800000;
        else if(f_nan_c) fp32_c=32'h7FC00000;
        else if(f_sub_c) fp32_c={f_sign_c, 8'd0, f_mant32_norm_c};
        else fp32_c={f_sign_c, f_exp32_c, f_mant32_c};
    end
    wire mul_irdy,mul_ovld; wire [31:0] mul_result;
    wire add_irdy,add_ovld; wire [31:0] add_result;
    gf_mul_param #(.EXP_BITS(8),.MANT_BITS(23),.HAS_INF(1)) u_mul (
        .clk(mclk),.rst(rst),.in_valid(comp_trigger),.in_a(fp32_a),.in_b(fp32_b),
        .in_ready(mul_irdy),.out_valid(mul_ovld),.out_y(mul_result),.out_ready(1'b1));
    gf_adder_param #(.EXP_BITS(8),.MANT_BITS(23),.HAS_INF(1)) u_add (
        .clk(mclk),.rst(rst),.in_valid(mul_ovld),.in_a(mul_result),.in_b(fp32_c),
        .in_ready(add_irdy),.out_valid(add_ovld),.out_y(add_result),.out_ready(1'b1));
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;b_reg<=0;c_reg<=0;comp_trigger<=0; end
        else begin comp_trigger<=frame_valid;
            if(frame_valid) begin a_reg<=a_r;b_reg<=b_r;c_reg<=c_r; end
        end
    end
    wire [31:0] q_in=add_result;
    wire q_sign=q_in[31]; wire [7:0] q_exp=q_in[30:23]; wire [22:0] q_mant=q_in[22:0];
    wire q_nan=(q_in==32'h7FC00000); wire q_zero=(q_in==32'h00000000);
    wire q_inf=(q_exp==8'hFF)&&(q_mant==0);
    wire signed [20:0] tgt_exp_s = $signed({1'b0, q_exp}) - 21'sd127 + 21'sd1023;
    reg [89:0] q_result;
    always @(*) begin
        if(q_nan) q_result=90'd0;
        else if(q_zero) q_result=90'd0;
        else if(q_inf) q_result={q_sign, 11'd2047, 78'd0};
        else if(q_exp >= 8'd254) q_result={q_sign, 11'd2047, 78'd0};
        else if(q_exp < 8'd0) q_result={q_sign, 89'b0};
        else if(tgt_exp_s < 1) q_result={q_sign, 11'b0, q_mant[22:0]};
        else q_result={q_sign, tgt_exp_s[10:0], q_mant[22:0]};
    end
    reg [89:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=add_ovld;
            if(add_ovld) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [3:0] TX_LEN = 13;
    // TX: buffer+mux (no conflicting NBA — fixes tx race). 13 bytes sliced from tx_load[103:0].
    wire [103:0] tx_load = {result_reg, 8'hA5};
    reg responding; reg [3:0] tx_idx; reg [7:0] tx_buf0, tx_buf1, tx_buf2, tx_buf3, tx_buf4, tx_buf5, tx_buf6, tx_buf7, tx_buf8, tx_buf9, tx_buf10, tx_buf11, tx_buf12;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF; tx_buf1<=8'hFF; tx_buf2<=8'hFF; tx_buf3<=8'hFF; tx_buf4<=8'hFF; tx_buf5<=8'hFF; tx_buf6<=8'hFF; tx_buf7<=8'hFF; tx_buf8<=8'hFF; tx_buf9<=8'hFF; tx_buf10<=8'hFF; tx_buf11<=8'hFF; tx_buf12<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=tx_load[7:0]; tx_buf1<=tx_load[15:8]; tx_buf2<=tx_load[23:16]; tx_buf3<=tx_load[31:24]; tx_buf4<=tx_load[39:32]; tx_buf5<=tx_load[47:40]; tx_buf6<=tx_load[55:48]; tx_buf7<=tx_load[63:56]; tx_buf8<=tx_load[71:64]; tx_buf9<=tx_load[79:72]; tx_buf10<=tx_load[87:80]; tx_buf11<=tx_load[95:88]; tx_buf12<=tx_load[103:96]; responding<=1; tx_idx<=0;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        case(tx_idx)
                            4'd0: tsr<={1'b1,tx_buf0,1'b0};
                            4'd1: tsr<={1'b1,tx_buf1,1'b0};
                            4'd2: tsr<={1'b1,tx_buf2,1'b0};
                            4'd3: tsr<={1'b1,tx_buf3,1'b0};
                            4'd4: tsr<={1'b1,tx_buf4,1'b0};
                            4'd5: tsr<={1'b1,tx_buf5,1'b0};
                            4'd6: tsr<={1'b1,tx_buf6,1'b0};
                            4'd7: tsr<={1'b1,tx_buf7,1'b0};
                            4'd8: tsr<={1'b1,tx_buf8,1'b0};
                            4'd9: tsr<={1'b1,tx_buf9,1'b0};
                            4'd10: tsr<={1'b1,tx_buf10,1'b0};
                            4'd11: tsr<={1'b1,tx_buf11,1'b0};
                            4'd12: tsr<={1'b1,tx_buf12,1'b0};
                        endcase
                        if(tx_idx==12) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
    endmodule
`default_nettype wire
