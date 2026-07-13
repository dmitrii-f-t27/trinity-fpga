`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_binary128_add_ax7203 — BINARY128 ADD on AX7203.
module corona_compute_binary128_add_ax7203 (
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

    reg [5:0] frm; reg [7:0] fmt_r; reg [127:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
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
                6'd35: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [127:0] a_reg,b_reg; reg comp_trigger;
    wire [127:0] fmt_a=a_reg, fmt_b=b_reg;
    wire b128_sign_a = fmt_a[127];
    wire [14:0] b128_exp_a = fmt_a[126:112];
    wire [111:0] b128_mant_a = fmt_a[111:0];
    wire b128_zero_a = (b128_exp_a == 15'd0) && (b128_mant_a == 112'd0);
    wire b128_nan_a = (b128_exp_a == 15'h7FFF) && (|b128_mant_a);
    wire b128_inf_a = (b128_exp_a == 15'h7FFF) && (b128_mant_a == 112'd0);
    wire signed [15:0] b128_exp32_s_a = $signed({1'b0, b128_exp_a}) - 16'sd16383 + 16'sd127;
    wire [7:0] b128_exp32_a = b128_exp32_s_a[7:0];
    wire [22:0] b128_mant32_a = b128_mant_a[111:89];
    reg [31:0] fp32_a;
    always @(*) begin
        if(b128_zero_a) fp32_a=32'h00000000;
        else if(b128_nan_a) fp32_a=32'h7FC00000;
        else if(b128_inf_a) fp32_a={b128_sign_a, 8'hFF, 23'b0};
        else fp32_a={b128_sign_a, b128_exp32_a, b128_mant32_a};
    end
    wire b128_sign_b = fmt_b[127];
    wire [14:0] b128_exp_b = fmt_b[126:112];
    wire [111:0] b128_mant_b = fmt_b[111:0];
    wire b128_zero_b = (b128_exp_b == 15'd0) && (b128_mant_b == 112'd0);
    wire b128_nan_b = (b128_exp_b == 15'h7FFF) && (|b128_mant_b);
    wire b128_inf_b = (b128_exp_b == 15'h7FFF) && (b128_mant_b == 112'd0);
    wire signed [15:0] b128_exp32_s_b = $signed({1'b0, b128_exp_b}) - 16'sd16383 + 16'sd127;
    wire [7:0] b128_exp32_b = b128_exp32_s_b[7:0];
    wire [22:0] b128_mant32_b = b128_mant_b[111:89];
    reg [31:0] fp32_b;
    always @(*) begin
        if(b128_zero_b) fp32_b=32'h00000000;
        else if(b128_nan_b) fp32_b=32'h7FC00000;
        else if(b128_inf_b) fp32_b={b128_sign_b, 8'hFF, 23'b0};
        else fp32_b={b128_sign_b, b128_exp32_b, b128_mant32_b};
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
    wire q_inf=(q_exp==8'hFF)&&(q_mant==0);
    wire signed [15:0] b128_exp = $signed({1'b0, q_exp}) - 16'sd127 + 16'sd16383;
    reg [127:0] q_result;
    always @(*) begin
        if(q_nan) q_result={1'b0,15'h7FFF,1'b1,88'b0};
        else if(q_zero) q_result=128'h0;
        else if(q_inf) q_result={q_sign,15'h7FFF,112'b0};
        else q_result={q_sign, b128_exp[14:0], q_mant, 89'b0};
    end
    reg [127:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=comp_ovld;
            if(comp_ovld) result_reg<=q_result;
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
