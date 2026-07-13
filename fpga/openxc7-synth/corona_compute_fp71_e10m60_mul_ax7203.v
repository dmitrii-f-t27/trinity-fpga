`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_fp71_e10m60_mul_ax7203 — FP71_E10M60 MUL on AX7203.
module corona_compute_fp71_e10m60_mul_ax7203 (
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

    reg [4:0] frm; reg [7:0] fmt_r; reg [70:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                5'd0: frm<=(rx_byte==8'hAA)?5'd1:5'd0;
                5'd1: frm<=(rx_byte==8'h55)?5'd2:5'd0;
                5'd2: begin fmt_r<=rx_byte;frm<=5'd3; end
                5'd3: begin a_r[7:0]<=rx_byte;frm<=5'd4; end
                5'd4: begin a_r[15:8]<=rx_byte;frm<=5'd5; end
                5'd5: begin a_r[23:16]<=rx_byte;frm<=5'd6; end
                5'd6: begin a_r[31:24]<=rx_byte;frm<=5'd7; end
                5'd7: begin a_r[39:32]<=rx_byte;frm<=5'd8; end
                5'd8: begin a_r[47:40]<=rx_byte;frm<=5'd9; end
                5'd9: begin a_r[55:48]<=rx_byte;frm<=5'd10; end
                5'd10: begin a_r[63:56]<=rx_byte;frm<=5'd11; end
                5'd11: begin a_r[70:64]<=rx_byte;frm<=5'd12; end
                5'd12: begin b_r[7:0]<=rx_byte;frm<=5'd13; end
                5'd13: begin b_r[15:8]<=rx_byte;frm<=5'd14; end
                5'd14: begin b_r[23:16]<=rx_byte;frm<=5'd15; end
                5'd15: begin b_r[31:24]<=rx_byte;frm<=5'd16; end
                5'd16: begin b_r[39:32]<=rx_byte;frm<=5'd17; end
                5'd17: begin b_r[47:40]<=rx_byte;frm<=5'd18; end
                5'd18: begin b_r[55:48]<=rx_byte;frm<=5'd19; end
                5'd19: begin b_r[63:56]<=rx_byte;frm<=5'd20; end
                5'd20: begin b_r[70:64]<=rx_byte;frm<=5'd21; end
                5'd21: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [70:0] a_reg,b_reg; reg comp_trigger;
    wire [70:0] fmt_a=a_reg, fmt_b=b_reg;
    wire f_sign_a = fmt_a_a[70];
    wire [9:0] f_exp_a = fmt_a_a[69:60];
    wire [59:0] f_mant_a = fmt_a_a[59:0];
    wire f_zero_a = (f_exp_a == 0) && ((f_mant_a == 0));
    wire f_inf_a = (f_exp_a == 1023) && ((f_mant_a == 0));
    wire f_nan_a = (f_exp_a == 1023) && ((f_mant_a != 0));
    wire f_sub_a = (f_exp_a == 0) && ((f_mant_a != 0));
    wire signed [19:0] f_de_a = $signed({1'b0, f_exp_a}) - 20'sd511 + 20'sd127;
    wire [7:0] f_exp32_a = (f_de_a > 20'sd254) ? 8'd254 : (f_de_a < 0) ? 8'd0 : f_de_a[7:0];
    wire [22:0] f_mant32_a = {f_mant_a, -37'b0};
    wire [22:0] f_mant32_norm_a = f_mant_a;
    reg [31:0] fp32_a;
    always @(*) begin
        if(f_zero_a) fp32_a=32'h00000000;
        else if(f_inf_a) fp32_a=f_sign_a?32'hFF800000:32'h7F800000;
        else if(f_nan_a) fp32_a=32'h7FC00000;
        else if(f_sub_a) fp32_a={f_sign_a, 8'd0, f_mant32_norm_a};
        else fp32_a={f_sign_a, f_exp32_a, f_mant32_a};
    end
    wire f_sign_b = fmt_b_b[70];
    wire [9:0] f_exp_b = fmt_b_b[69:60];
    wire [59:0] f_mant_b = fmt_b_b[59:0];
    wire f_zero_b = (f_exp_b == 0) && ((f_mant_b == 0));
    wire f_inf_b = (f_exp_b == 1023) && ((f_mant_b == 0));
    wire f_nan_b = (f_exp_b == 1023) && ((f_mant_b != 0));
    wire f_sub_b = (f_exp_b == 0) && ((f_mant_b != 0));
    wire signed [19:0] f_de_b = $signed({1'b0, f_exp_b}) - 20'sd511 + 20'sd127;
    wire [7:0] f_exp32_b = (f_de_b > 20'sd254) ? 8'd254 : (f_de_b < 0) ? 8'd0 : f_de_b[7:0];
    wire [22:0] f_mant32_b = {f_mant_b, -37'b0};
    wire [22:0] f_mant32_norm_b = f_mant_b;
    reg [31:0] fp32_b;
    always @(*) begin
        if(f_zero_b) fp32_b=32'h00000000;
        else if(f_inf_b) fp32_b=f_sign_b?32'hFF800000:32'h7F800000;
        else if(f_nan_b) fp32_b=32'h7FC00000;
        else if(f_sub_b) fp32_b={f_sign_b, 8'd0, f_mant32_norm_b};
        else fp32_b={f_sign_b, f_exp32_b, f_mant32_b};
    end
    wire comp_irdy, comp_ovld; wire [31:0] comp_result;
    gf_mul_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1)) u_comp (
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
    wire q_inf=(q_exp==8'hFF)&&(q_mant==0);
    wire signed [19:0] tgt_exp_s = $signed({1'b0, q_exp}) - 20'sd127 + 20'sd511;
    reg [70:0] q_result;
    always @(*) begin
        if(q_nan) q_result=71'd0;
        else if(q_zero) q_result=71'd0;
        else if(q_inf) q_result={q_sign, 10'd1023, 60'd0};
        else if(q_exp >= 8'd254) q_result={q_sign, 10'd1023, 60'd0};
        else if(q_exp < 8'd0) q_result={q_sign, 70'b0};
        else if(tgt_exp_s < 1) q_result={q_sign, 10'b0, q_mant[22:0]};
        else q_result={q_sign, tgt_exp_s[9:0], q_mant[22:0]};
    end
    reg [70:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=comp_ovld;
            if(comp_ovld) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [3:0] TX_LEN = 10;
    reg responding; reg [3:0] tx_cnt;
    reg [79:0] tx_shift;
    wire [79:0] tx_load = {result_reg, 8'hA5};
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    wire [7:0] cur_byte;
    always @(*) begin
        if(!responding) cur_byte=8'hFF; else cur_byte=tx_shift[7:0];
    end
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_cnt<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin tx_shift<=tx_load;tx_cnt<=0;responding<=1; end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        tsr<={1'b1,cur_byte,1'b0};
                        tx_shift<={8'h00,tx_shift[79:8]};
                        if(tx_cnt==TX_LEN-1) responding<=0; else tx_cnt<=tx_cnt+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
endmodule
`default_nettype wire
