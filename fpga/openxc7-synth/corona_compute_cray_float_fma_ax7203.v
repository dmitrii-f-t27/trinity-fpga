`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_cray_float_fma_ax7203 — CRAY FMA on AX7203.
module corona_compute_cray_float_fma_ax7203 (
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

    reg [4:0] frm; reg [7:0] fmt_r; reg [63:0] a_r,b_r,c_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;c_r<=0;frame_valid<=0; end
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
                5'd11: begin b_r[7:0]<=rx_byte;frm<=5'd12; end
                5'd12: begin b_r[15:8]<=rx_byte;frm<=5'd13; end
                5'd13: begin b_r[23:16]<=rx_byte;frm<=5'd14; end
                5'd14: begin b_r[31:24]<=rx_byte;frm<=5'd15; end
                5'd15: begin b_r[39:32]<=rx_byte;frm<=5'd16; end
                5'd16: begin b_r[47:40]<=rx_byte;frm<=5'd17; end
                5'd17: begin b_r[55:48]<=rx_byte;frm<=5'd18; end
                5'd18: begin b_r[63:56]<=rx_byte;frm<=5'd19; end
                5'd19: begin c_r[7:0]<=rx_byte;frm<=5'd20; end
                5'd20: begin c_r[15:8]<=rx_byte;frm<=5'd21; end
                5'd21: begin c_r[23:16]<=rx_byte;frm<=5'd22; end
                5'd22: begin c_r[31:24]<=rx_byte;frm<=5'd23; end
                5'd23: begin c_r[39:32]<=rx_byte;frm<=5'd24; end
                5'd24: begin c_r[47:40]<=rx_byte;frm<=5'd25; end
                5'd25: begin c_r[55:48]<=rx_byte;frm<=5'd26; end
                5'd26: begin c_r[63:56]<=rx_byte;frm<=5'd27; end
                5'd27: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [63:0] a_reg,b_reg,c_reg; reg comp_trigger;
    wire [63:0] fmt_a=a_reg, fmt_b=b_reg, fmt_c=c_reg;
    wire cr_sign_a = fmt_a[63];
    wire [14:0] cr_exp_a = fmt_a[62:48];
    wire [47:0] cr_mant_a = fmt_a[47:0];
    wire cr_zero_a = (cr_exp_a == 15'd0) && (cr_mant_a == 48'd0);
    wire signed [15:0] cr_exp32_s_a = $signed({1'b0, cr_exp_a}) - 16'sd16384 + 16'sd127;
    wire [7:0] cr_exp32_a = cr_exp32_s_a[7:0];
    wire [22:0] cr_mant32_a = cr_mant_a[46:24];
    reg [31:0] fp32_a;
    always @(*) begin
        if(cr_zero_a) fp32_a={cr_sign_a, 31'b0};
        // Saturate instead of wrapping -- see the note in the sibling
        // wrappers. cr_exp32_s_a is a SIGNED 16-bit intermediate and cr_exp32_a is
        // its low 8 bits, so an exponent outside fp32's window used to
        // come back as some other exponent entirely. This format has no
        // Inf encoding of its own, so overflow saturates to fp32 +Inf on
        // the narrowed operand, which is what the adder downstream reads.
        else if(cr_exp32_s_a > 16'sd254) fp32_a={cr_sign_a, 8'hFF, 23'b0};
        else if(cr_exp32_s_a < 16'sd1) fp32_a={cr_sign_a, 8'd0, 23'b0};
        else fp32_a={cr_sign_a, cr_exp32_a, cr_mant32_a};
    end
    wire cr_sign_b = fmt_b[63];
    wire [14:0] cr_exp_b = fmt_b[62:48];
    wire [47:0] cr_mant_b = fmt_b[47:0];
    wire cr_zero_b = (cr_exp_b == 15'd0) && (cr_mant_b == 48'd0);
    wire signed [15:0] cr_exp32_s_b = $signed({1'b0, cr_exp_b}) - 16'sd16384 + 16'sd127;
    wire [7:0] cr_exp32_b = cr_exp32_s_b[7:0];
    wire [22:0] cr_mant32_b = cr_mant_b[46:24];
    reg [31:0] fp32_b;
    always @(*) begin
        if(cr_zero_b) fp32_b={cr_sign_b, 31'b0};
        // Saturate instead of wrapping -- see the note in the sibling
        // wrappers. cr_exp32_s_b is a SIGNED 16-bit intermediate and cr_exp32_b is
        // its low 8 bits, so an exponent outside fp32's window used to
        // come back as some other exponent entirely. This format has no
        // Inf encoding of its own, so overflow saturates to fp32 +Inf on
        // the narrowed operand, which is what the adder downstream reads.
        else if(cr_exp32_s_b > 16'sd254) fp32_b={cr_sign_b, 8'hFF, 23'b0};
        else if(cr_exp32_s_b < 16'sd1) fp32_b={cr_sign_b, 8'd0, 23'b0};
        else fp32_b={cr_sign_b, cr_exp32_b, cr_mant32_b};
    end
    wire cr_sign_c = fmt_c[63];
    wire [14:0] cr_exp_c = fmt_c[62:48];
    wire [47:0] cr_mant_c = fmt_c[47:0];
    wire cr_zero_c = (cr_exp_c == 15'd0) && (cr_mant_c == 48'd0);
    wire signed [15:0] cr_exp32_s_c = $signed({1'b0, cr_exp_c}) - 16'sd16384 + 16'sd127;
    wire [7:0] cr_exp32_c = cr_exp32_s_c[7:0];
    wire [22:0] cr_mant32_c = cr_mant_c[46:24];
    reg [31:0] fp32_c;
    always @(*) begin
        if(cr_zero_c) fp32_c={cr_sign_c, 31'b0};
        else fp32_c={cr_sign_c, cr_exp32_c, cr_mant32_c};
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
    wire signed [15:0] cr_exp = $signed({1'b0, q_exp}) - 16'sd127 + 16'sd16384;
    reg [63:0] q_result;
    always @(*) begin
        if(q_nan) q_result=64'h0;
        else if(q_zero) q_result=64'h0;
        else q_result={q_sign, cr_exp[14:0], 1'b1, q_mant, 24'b0};
    end
    reg [63:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=add_ovld;
            if(add_ovld) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [3:0] TX_LEN = 9;
    // TX: buffer+mux (no conflicting NBA — fixes tx race). 9 bytes sliced from tx_load[71:0].
    wire [71:0] tx_load = {result_reg, 8'hA5};
    reg responding; reg [3:0] tx_idx; reg [7:0] tx_buf0, tx_buf1, tx_buf2, tx_buf3, tx_buf4, tx_buf5, tx_buf6, tx_buf7, tx_buf8;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF; tx_buf1<=8'hFF; tx_buf2<=8'hFF; tx_buf3<=8'hFF; tx_buf4<=8'hFF; tx_buf5<=8'hFF; tx_buf6<=8'hFF; tx_buf7<=8'hFF; tx_buf8<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=tx_load[7:0]; tx_buf1<=tx_load[15:8]; tx_buf2<=tx_load[23:16]; tx_buf3<=tx_load[31:24]; tx_buf4<=tx_load[39:32]; tx_buf5<=tx_load[47:40]; tx_buf6<=tx_load[55:48]; tx_buf7<=tx_load[63:56]; tx_buf8<=tx_load[71:64]; responding<=1; tx_idx<=0;
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
                        endcase
                        if(tx_idx==8) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
    endmodule
`default_nettype wire
