`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_decimal128_fma_ax7203 — DECIMAL128 FMA on AX7203.
module corona_compute_decimal128_fma_ax7203 (
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
    reg [1:0] rxs; reg [8:0] rxcnt; reg [3:0] rbi; reg [7:0] rxsr; reg [7:0] rx_byte; reg rx_new;
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

    reg [5:0] frm; reg [7:0] fmt_r; reg [127:0] a_r,b_r,c_r; reg frame_valid;
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
                6'd14: begin a_r[95:88]<=rx_byte;frm<=6'd15; end
                6'd15: begin a_r[103:96]<=rx_byte;frm<=6'd16; end
                6'd16: begin a_r[111:104]<=rx_byte;frm<=6'd17; end
                6'd17: begin a_r[119:112]<=rx_byte;frm<=6'd18; end
                6'd18: begin a_r[127:120]<=rx_byte;frm<=6'd19; end
                6'd19: begin b_r[7:0]<=rx_byte;frm<=6'd20; end
                6'd20: begin b_r[15:8]<=rx_byte;frm<=6'd21; end
                6'd21: begin b_r[23:16]<=rx_byte;frm<=6'd22; end
                6'd22: begin b_r[31:24]<=rx_byte;frm<=6'd23; end
                6'd23: begin b_r[39:32]<=rx_byte;frm<=6'd24; end
                6'd24: begin b_r[47:40]<=rx_byte;frm<=6'd25; end
                6'd25: begin b_r[55:48]<=rx_byte;frm<=6'd26; end
                6'd26: begin b_r[63:56]<=rx_byte;frm<=6'd27; end
                6'd27: begin b_r[71:64]<=rx_byte;frm<=6'd28; end
                6'd28: begin b_r[79:72]<=rx_byte;frm<=6'd29; end
                6'd29: begin b_r[87:80]<=rx_byte;frm<=6'd30; end
                6'd30: begin b_r[95:88]<=rx_byte;frm<=6'd31; end
                6'd31: begin b_r[103:96]<=rx_byte;frm<=6'd32; end
                6'd32: begin b_r[111:104]<=rx_byte;frm<=6'd33; end
                6'd33: begin b_r[119:112]<=rx_byte;frm<=6'd34; end
                6'd34: begin b_r[127:120]<=rx_byte;frm<=6'd35; end
                6'd35: begin c_r[7:0]<=rx_byte;frm<=6'd36; end
                6'd36: begin c_r[15:8]<=rx_byte;frm<=6'd37; end
                6'd37: begin c_r[23:16]<=rx_byte;frm<=6'd38; end
                6'd38: begin c_r[31:24]<=rx_byte;frm<=6'd39; end
                6'd39: begin c_r[39:32]<=rx_byte;frm<=6'd40; end
                6'd40: begin c_r[47:40]<=rx_byte;frm<=6'd41; end
                6'd41: begin c_r[55:48]<=rx_byte;frm<=6'd42; end
                6'd42: begin c_r[63:56]<=rx_byte;frm<=6'd43; end
                6'd43: begin c_r[71:64]<=rx_byte;frm<=6'd44; end
                6'd44: begin c_r[79:72]<=rx_byte;frm<=6'd45; end
                6'd45: begin c_r[87:80]<=rx_byte;frm<=6'd46; end
                6'd46: begin c_r[95:88]<=rx_byte;frm<=6'd47; end
                6'd47: begin c_r[103:96]<=rx_byte;frm<=6'd48; end
                6'd48: begin c_r[111:104]<=rx_byte;frm<=6'd49; end
                6'd49: begin c_r[119:112]<=rx_byte;frm<=6'd50; end
                6'd50: begin c_r[127:120]<=rx_byte;frm<=6'd51; end
                6'd51: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [127:0] a_reg,b_reg,c_reg; reg comp_trigger;
    wire [127:0] fmt_a=a_reg, fmt_b=b_reg, fmt_c=c_reg;
    wire d128_sign_a = fmt_a[127];
    wire d128_case_b_a = (fmt_a[126:125] == 2'b11);
    wire [13:0] d128_exp_a_a = fmt_a[126:113];
    wire [13:0] d128_exp_b_a = fmt_a[124:111];
    wire [112:0] d128_coeff_a_a = fmt_a[112:0];
    wire [113:0] d128_coeff_b_a = {3'b100, fmt_a[110:0]};
    wire [13:0] d128_exp_a = d128_case_b_a ? d128_exp_b_a : d128_exp_a_a;
    wire d128_zero_a = (d128_exp_a == 0) && (fmt_a[112:0] == 113'd0);
    wire d128_special_a = (fmt_a[126:123] == 4'b1111);
    wire signed [15:0] d128_de_a = $signed({2'b0, d128_exp_a}) - 16'sd6176;
    wire [15:0] d128_exp32_raw_a = d128_de_a[15] ?
        (16'd127 - (~d128_de_a[14:0] + 15'd1)) :
        ({1'b0, d128_de_a[14:0]} + 16'd127);
    wire [7:0] d128_exp32_a = d128_exp32_raw_a[7:0];
    wire [22:0] d128_mant32_a = fmt_a[112:90];
    reg [31:0] fp32_a;
    always @(*) begin
        if(d128_zero_a || d128_special_a) fp32_a=32'h00000000;
        else fp32_a={d128_sign_a, d128_exp32_a, d128_mant32_a};
    end
    wire d128_sign_b = fmt_b[127];
    wire d128_case_b_b = (fmt_b[126:125] == 2'b11);
    wire [13:0] d128_exp_a_b = fmt_b[126:113];
    wire [13:0] d128_exp_b_b = fmt_b[124:111];
    wire [112:0] d128_coeff_a_b = fmt_b[112:0];
    wire [113:0] d128_coeff_b_b = {3'b100, fmt_b[110:0]};
    wire [13:0] d128_exp_b = d128_case_b_b ? d128_exp_b_b : d128_exp_a_b;
    wire d128_zero_b = (d128_exp_b == 0) && (fmt_b[112:0] == 113'd0);
    wire d128_special_b = (fmt_b[126:123] == 4'b1111);
    wire signed [15:0] d128_de_b = $signed({2'b0, d128_exp_b}) - 16'sd6176;
    wire [15:0] d128_exp32_raw_b = d128_de_b[15] ?
        (16'd127 - (~d128_de_b[14:0] + 15'd1)) :
        ({1'b0, d128_de_b[14:0]} + 16'd127);
    wire [7:0] d128_exp32_b = d128_exp32_raw_b[7:0];
    wire [22:0] d128_mant32_b = fmt_b[112:90];
    reg [31:0] fp32_b;
    always @(*) begin
        if(d128_zero_b || d128_special_b) fp32_b=32'h00000000;
        else fp32_b={d128_sign_b, d128_exp32_b, d128_mant32_b};
    end
    wire d128_sign_c = fmt_c[127];
    wire d128_case_b_c = (fmt_c[126:125] == 2'b11);
    wire [13:0] d128_exp_a_c = fmt_c[126:113];
    wire [13:0] d128_exp_b_c = fmt_c[124:111];
    wire [112:0] d128_coeff_a_c = fmt_c[112:0];
    wire [113:0] d128_coeff_b_c = {3'b100, fmt_c[110:0]};
    wire [13:0] d128_exp_c = d128_case_b_c ? d128_exp_b_c : d128_exp_a_c;
    wire d128_zero_c = (d128_exp_c == 0) && (fmt_c[112:0] == 113'd0);
    wire d128_special_c = (fmt_c[126:123] == 4'b1111);
    wire signed [15:0] d128_de_c = $signed({2'b0, d128_exp_c}) - 16'sd6176;
    wire [15:0] d128_exp32_raw_c = d128_de_c[15] ?
        (16'd127 - (~d128_de_c[14:0] + 15'd1)) :
        ({1'b0, d128_de_c[14:0]} + 16'd127);
    wire [7:0] d128_exp32_c = d128_exp32_raw_c[7:0];
    wire [22:0] d128_mant32_c = fmt_c[112:90];
    reg [31:0] fp32_c;
    always @(*) begin
        if(d128_zero_c || d128_special_c) fp32_c=32'h00000000;
        else fp32_c={d128_sign_c, d128_exp32_c, d128_mant32_c};
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
    wire signed [8:0] q_de = $signed({1'b0, q_exp}) - 9'sd127;
    wire [13:0] q_d128_exp = q_de[8] ? 14'd0 : ({5'b0, q_de[7:0]} + 14'd6176);
    reg [127:0] q_result;
    always @(*) begin
        if(q_nan) q_result=128'h0;
        else if(q_zero) q_result=128'h0;
        else q_result={q_sign, q_d128_exp, {90'b0, q_mant}};
    end
    reg [127:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=add_ovld;
            if(add_ovld) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [3:0] TX_LEN = 17;
    reg responding; reg [3:0] tx_cnt;
    reg [135:0] tx_shift;
    wire [135:0] tx_load = {result_reg, 8'hA5};
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
                        tx_shift<={8'h00,tx_shift[135:8]};
                        if(tx_cnt==TX_LEN-1) responding<=0; else tx_cnt<=tx_cnt+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
endmodule
`default_nettype wire
