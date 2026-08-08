`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_double_double_alu_ax7203 — DOUBLE_DOUBLE ALU on AX7203.
module corona_compute_double_double_alu_ax7203 (
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

    reg [5:0] frm; reg [7:0] fmt_r,op_r; reg [127:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;op_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                6'd0: frm<=(rx_byte==8'hAA)?6'd1:6'd0;
                6'd1: frm<=(rx_byte==8'h55)?6'd2:6'd0;
                6'd2: begin fmt_r<=rx_byte;frm<=6'd3; end
                6'd3: begin op_r<=rx_byte;frm<=6'd4; end
                6'd4: begin a_r[7:0]<=rx_byte;frm<=6'd5; end
                6'd5: begin a_r[15:8]<=rx_byte;frm<=6'd6; end
                6'd6: begin a_r[23:16]<=rx_byte;frm<=6'd7; end
                6'd7: begin a_r[31:24]<=rx_byte;frm<=6'd8; end
                6'd8: begin a_r[39:32]<=rx_byte;frm<=6'd9; end
                6'd9: begin a_r[47:40]<=rx_byte;frm<=6'd10; end
                6'd10: begin a_r[55:48]<=rx_byte;frm<=6'd11; end
                6'd11: begin a_r[63:56]<=rx_byte;frm<=6'd12; end
                6'd12: begin a_r[71:64]<=rx_byte;frm<=6'd13; end
                6'd13: begin a_r[79:72]<=rx_byte;frm<=6'd14; end
                6'd14: begin a_r[87:80]<=rx_byte;frm<=6'd15; end
                6'd15: begin a_r[95:88]<=rx_byte;frm<=6'd16; end
                6'd16: begin a_r[103:96]<=rx_byte;frm<=6'd17; end
                6'd17: begin a_r[111:104]<=rx_byte;frm<=6'd18; end
                6'd18: begin a_r[119:112]<=rx_byte;frm<=6'd19; end
                6'd19: begin a_r[127:120]<=rx_byte;frm<=6'd20; end
                6'd20: begin b_r[7:0]<=rx_byte;frm<=6'd21; end
                6'd21: begin b_r[15:8]<=rx_byte;frm<=6'd22; end
                6'd22: begin b_r[23:16]<=rx_byte;frm<=6'd23; end
                6'd23: begin b_r[31:24]<=rx_byte;frm<=6'd24; end
                6'd24: begin b_r[39:32]<=rx_byte;frm<=6'd25; end
                6'd25: begin b_r[47:40]<=rx_byte;frm<=6'd26; end
                6'd26: begin b_r[55:48]<=rx_byte;frm<=6'd27; end
                6'd27: begin b_r[63:56]<=rx_byte;frm<=6'd28; end
                6'd28: begin b_r[71:64]<=rx_byte;frm<=6'd29; end
                6'd29: begin b_r[79:72]<=rx_byte;frm<=6'd30; end
                6'd30: begin b_r[87:80]<=rx_byte;frm<=6'd31; end
                6'd31: begin b_r[95:88]<=rx_byte;frm<=6'd32; end
                6'd32: begin b_r[103:96]<=rx_byte;frm<=6'd33; end
                6'd33: begin b_r[111:104]<=rx_byte;frm<=6'd34; end
                6'd34: begin b_r[119:112]<=rx_byte;frm<=6'd35; end
                6'd35: begin b_r[127:120]<=rx_byte;frm<=6'd36; end
                6'd36: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [127:0] a_reg,b_reg; reg [7:0] op_reg; reg comp_trigger;
    wire [127:0] fmt_a=a_reg, fmt_b=b_reg;
    wire dd_sign_a = fmt_a[63];
    wire [10:0] dd_exp_a = fmt_a[62:52];
    wire [51:0] dd_mant_a = fmt_a[51:0];
    wire dd_zero_a = (fmt_a[63:0] == 64'd0);
    wire dd_nan_a = (dd_exp_a == 11'h7FF) && (|dd_mant_a);
    wire dd_inf_a = (dd_exp_a == 11'h7FF) && (dd_mant_a == 52'd0);
    wire signed [11:0] dd_exp32_s_a = $signed({1'b0, dd_exp_a}) - 12'sd896;
    wire [7:0] dd_exp32_a = dd_exp32_s_a[7:0];
    wire [22:0] dd_mant32_a = dd_mant_a[51:29];
    reg [31:0] fp32_a;
    always @(*) begin
        if(dd_zero_a) fp32_a={dd_sign_a, 31'b0};
        else if(dd_nan_a) fp32_a=32'h7FC00000;
        else if(dd_inf_a) fp32_a={dd_sign_a, 8'hFF, 23'b0};
        // Saturate instead of wrapping. dd_exp32_a is dd_exp32_s_a truncated to 8
        // bits, and dd_exp32_s_a is a SIGNED 16-bit intermediate, so an exponent
        // outside fp32's window used to come back as some other exponent
        // entirely -- a value far above fp32's maximum arrived as an
        // ordinary finite number instead of +Inf. Pass 240 counted 32,510
        // of binary128's own exponents landing outside that window.
        else if(dd_exp32_s_a > 16'sd254) fp32_a={dd_sign_a, 8'hFF, 23'b0};
        else if(dd_exp32_s_a < 16'sd1) fp32_a={dd_sign_a, 8'd0, 23'b0};
        else fp32_a={dd_sign_a, dd_exp32_a, dd_mant32_a};
    end
    wire dd_sign_b = fmt_b[63];
    wire [10:0] dd_exp_b = fmt_b[62:52];
    wire [51:0] dd_mant_b = fmt_b[51:0];
    wire dd_zero_b = (fmt_b[63:0] == 64'd0);
    wire dd_nan_b = (dd_exp_b == 11'h7FF) && (|dd_mant_b);
    wire dd_inf_b = (dd_exp_b == 11'h7FF) && (dd_mant_b == 52'd0);
    wire signed [11:0] dd_exp32_s_b = $signed({1'b0, dd_exp_b}) - 12'sd896;
    wire [7:0] dd_exp32_b = dd_exp32_s_b[7:0];
    wire [22:0] dd_mant32_b = dd_mant_b[51:29];
    reg [31:0] fp32_b;
    always @(*) begin
        if(dd_zero_b) fp32_b={dd_sign_b, 31'b0};
        else if(dd_nan_b) fp32_b=32'h7FC00000;
        else if(dd_inf_b) fp32_b={dd_sign_b, 8'hFF, 23'b0};
        // Saturate instead of wrapping. dd_exp32_b is dd_exp32_s_b truncated to 8
        // bits, and dd_exp32_s_b is a SIGNED 16-bit intermediate, so an exponent
        // outside fp32's window used to come back as some other exponent
        // entirely -- a value far above fp32's maximum arrived as an
        // ordinary finite number instead of +Inf. Pass 240 counted 32,510
        // of binary128's own exponents landing outside that window.
        else if(dd_exp32_s_b > 16'sd254) fp32_b={dd_sign_b, 8'hFF, 23'b0};
        else if(dd_exp32_s_b < 16'sd1) fp32_b={dd_sign_b, 8'd0, 23'b0};
        else fp32_b={dd_sign_b, dd_exp32_b, dd_mant32_b};
    end
    wire add_irdy,add_ovld; wire [31:0] add_res;
    wire mul_irdy,mul_ovld; wire [31:0] mul_res;
    gf_adder_param #(.EXP_BITS(8),.MANT_BITS(23),.HAS_INF(1)) u_add (
        .clk(mclk),.rst(rst),.in_valid(comp_trigger),.in_a(fp32_a),.in_b(fp32_b),
        .in_ready(add_irdy),.out_valid(add_ovld),.out_y(add_res),.out_ready(1'b1));
    gf_mul_param #(.EXP_BITS(8),.MANT_BITS(23),.HAS_INF(1)) u_mul (
        .clk(mclk),.rst(rst),.in_valid(comp_trigger),.in_a(fp32_a),.in_b(fp32_b),
        .in_ready(mul_irdy),.out_valid(mul_ovld),.out_y(mul_res),.out_ready(1'b1));
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;b_reg<=0;op_reg<=0;comp_trigger<=0; end
        else begin comp_trigger<=frame_valid;
            if(frame_valid) begin a_reg<=a_r;b_reg<=b_r;op_reg<=op_r; end
        end
    end
    wire [31:0] fp32_result=(op_reg==8'h00)?add_res:mul_res;
    wire ovld=(op_reg==8'h00)?add_ovld:mul_ovld;
    wire [31:0] q_in=fp32_result;
    wire q_sign=q_in[31]; wire [7:0] q_exp=q_in[30:23]; wire [22:0] q_mant=q_in[22:0];
    wire q_nan=(q_in==32'h7FC00000); wire q_zero=(q_in==32'h00000000);
    wire q_inf=(q_exp==8'hFF)&&(q_mant==0);
    wire signed [11:0] dd_exp = $signed({1'b0, q_exp}) - 12'sd127 + 12'sd896;
    reg [127:0] q_result;
    always @(*) begin
        if(q_nan) q_result={64'h7FF8000000000000, 64'h0};
        else if(q_zero) q_result=128'h0;
        else if(q_inf) q_result={{q_sign,11'h7FF,52'b0}, 64'h0};
        else q_result={{q_sign, dd_exp[10:0], q_mant, 29'b0}, 64'h0};
    end
    reg [127:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=ovld;
            if(ovld) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [3:0] TX_LEN = 17;
    // TX: buffer+mux (no conflicting NBA — fixes tx race). 17 bytes sliced from tx_load[135:0].
    wire [135:0] tx_load = {result_reg, 8'hA5};
    reg responding; reg [4:0] tx_idx; reg [7:0] tx_buf0, tx_buf1, tx_buf2, tx_buf3, tx_buf4, tx_buf5, tx_buf6, tx_buf7, tx_buf8, tx_buf9, tx_buf10, tx_buf11, tx_buf12, tx_buf13, tx_buf14, tx_buf15, tx_buf16;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF; tx_buf1<=8'hFF; tx_buf2<=8'hFF; tx_buf3<=8'hFF; tx_buf4<=8'hFF; tx_buf5<=8'hFF; tx_buf6<=8'hFF; tx_buf7<=8'hFF; tx_buf8<=8'hFF; tx_buf9<=8'hFF; tx_buf10<=8'hFF; tx_buf11<=8'hFF; tx_buf12<=8'hFF; tx_buf13<=8'hFF; tx_buf14<=8'hFF; tx_buf15<=8'hFF; tx_buf16<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=tx_load[7:0]; tx_buf1<=tx_load[15:8]; tx_buf2<=tx_load[23:16]; tx_buf3<=tx_load[31:24]; tx_buf4<=tx_load[39:32]; tx_buf5<=tx_load[47:40]; tx_buf6<=tx_load[55:48]; tx_buf7<=tx_load[63:56]; tx_buf8<=tx_load[71:64]; tx_buf9<=tx_load[79:72]; tx_buf10<=tx_load[87:80]; tx_buf11<=tx_load[95:88]; tx_buf12<=tx_load[103:96]; tx_buf13<=tx_load[111:104]; tx_buf14<=tx_load[119:112]; tx_buf15<=tx_load[127:120]; tx_buf16<=tx_load[135:128]; responding<=1; tx_idx<=0;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        case(tx_idx)
                            5'd0: tsr<={1'b1,tx_buf0,1'b0};
                            5'd1: tsr<={1'b1,tx_buf1,1'b0};
                            5'd2: tsr<={1'b1,tx_buf2,1'b0};
                            5'd3: tsr<={1'b1,tx_buf3,1'b0};
                            5'd4: tsr<={1'b1,tx_buf4,1'b0};
                            5'd5: tsr<={1'b1,tx_buf5,1'b0};
                            5'd6: tsr<={1'b1,tx_buf6,1'b0};
                            5'd7: tsr<={1'b1,tx_buf7,1'b0};
                            5'd8: tsr<={1'b1,tx_buf8,1'b0};
                            5'd9: tsr<={1'b1,tx_buf9,1'b0};
                            5'd10: tsr<={1'b1,tx_buf10,1'b0};
                            5'd11: tsr<={1'b1,tx_buf11,1'b0};
                            5'd12: tsr<={1'b1,tx_buf12,1'b0};
                            5'd13: tsr<={1'b1,tx_buf13,1'b0};
                            5'd14: tsr<={1'b1,tx_buf14,1'b0};
                            5'd15: tsr<={1'b1,tx_buf15,1'b0};
                            5'd16: tsr<={1'b1,tx_buf16,1'b0};
                        endcase
                        if(tx_idx==16) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
    endmodule
`default_nettype wire
