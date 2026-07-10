`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_mxfp4_block_fma_ax7203 — MXFP4_BLOCK FMA on AX7203.
module corona_compute_mxfp4_block_fma_ax7203 (
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

    reg [3:0] frm; reg [7:0] fmt_r; reg [15:0] a_r,b_r,c_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;c_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                4'd0: frm<=(rx_byte==8'hAA)?4'd1:4'd0;
                4'd1: frm<=(rx_byte==8'h55)?4'd2:4'd0;
                4'd2: begin fmt_r<=rx_byte;frm<=4'd3; end
                4'd3: begin a_r[7:0]<=rx_byte;frm<=4'd4; end
                4'd4: begin a_r[15:8]<=rx_byte;frm<=4'd5; end
                4'd5: begin b_r[7:0]<=rx_byte;frm<=4'd6; end
                4'd6: begin b_r[15:8]<=rx_byte;frm<=4'd7; end
                4'd7: begin c_r[7:0]<=rx_byte;frm<=4'd8; end
                4'd8: begin c_r[15:8]<=rx_byte;frm<=4'd9; end
                4'd9: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [15:0] a_reg,b_reg,c_reg; reg comp_trigger;
    wire [15:0] fmt_a=a_reg, fmt_b=b_reg, fmt_c=c_reg;
    wire [3:0] elem_a = fmt_a_a[3:0];
    wire [7:0] scale_code_a = fmt_a_a[15:8];
    wire elem_sign_a = elem_a[3];
    wire [1:0] elem_exp_a = elem_a[2:1];
    wire elem_mant_a = elem_a[0];
    wire elem_zero_a = (elem_a == 4'b0000);
    wire signed [9:0] scale_exp_a = $signed({1'b0, scale_code_a}) - 10'sd127;
    // Element decode (E2M1, BIAS=1)
    wire signed [4:0] elem_de_a = (elem_exp_a == 2'b00) ? -5'sd0 : ($signed({1'b0, elem_exp_a}) - 5'sd1);
    wire [8:0] elem_fp32_exp_raw_a = {1'b0, elem_de_a} + 9'd127 + scale_exp_a;
    // Normal: exp=01,10,11 → mantissa with hidden bit
    // Subnormal: exp=00
    wire is_elem_norm_a = (elem_exp_a != 2'b00);
    wire [8:0] sub_exp_a = 9'd127 + scale_exp_a;  // subnormal real_exp = 1-1 = 0
    reg [31:0] fp32_a;
    always @(*) begin
        if(elem_zero_a) fp32_a=32'h00000000;
        else if(is_elem_norm_a) begin
            if(elem_fp32_exp_raw_a > 9'd254) fp32_a = elem_sign_a ? 32'hFF800000 : 32'h7F800000;
            else if(elem_fp32_exp_raw_a[8]) fp32_a = 32'h00000000;
            else fp32_a = {elem_sign_a, elem_fp32_exp_raw_a[7:0], elem_mant_a, 22'b0};
        end else begin
            // Subnormal: value = elem_mant * 2^scale_exp
            if(elem_mant_a == 1'b0) fp32_a = 32'h00000000;
            else if(sub_exp_a > 9'd254) fp32_a = elem_sign_a ? 32'hFF800000 : 32'h7F800000;
            else if(sub_exp_a[8]) fp32_a = 32'h00000000;
            else fp32_a = {elem_sign_a, sub_exp_a[7:0], 23'b0};
        end
    end
    wire [3:0] elem_b = fmt_b_b[3:0];
    wire [7:0] scale_code_b = fmt_b_b[15:8];
    wire elem_sign_b = elem_b[3];
    wire [1:0] elem_exp_b = elem_b[2:1];
    wire elem_mant_b = elem_b[0];
    wire elem_zero_b = (elem_b == 4'b0000);
    wire signed [9:0] scale_exp_b = $signed({1'b0, scale_code_b}) - 10'sd127;
    // Element decode (E2M1, BIAS=1)
    wire signed [4:0] elem_de_b = (elem_exp_b == 2'b00) ? -5'sd0 : ($signed({1'b0, elem_exp_b}) - 5'sd1);
    wire [8:0] elem_fp32_exp_raw_b = {1'b0, elem_de_b} + 9'd127 + scale_exp_b;
    // Normal: exp=01,10,11 → mantissa with hidden bit
    // Subnormal: exp=00
    wire is_elem_norm_b = (elem_exp_b != 2'b00);
    wire [8:0] sub_exp_b = 9'd127 + scale_exp_b;  // subnormal real_exp = 1-1 = 0
    reg [31:0] fp32_b;
    always @(*) begin
        if(elem_zero_b) fp32_b=32'h00000000;
        else if(is_elem_norm_b) begin
            if(elem_fp32_exp_raw_b > 9'd254) fp32_b = elem_sign_b ? 32'hFF800000 : 32'h7F800000;
            else if(elem_fp32_exp_raw_b[8]) fp32_b = 32'h00000000;
            else fp32_b = {elem_sign_b, elem_fp32_exp_raw_b[7:0], elem_mant_b, 22'b0};
        end else begin
            // Subnormal: value = elem_mant * 2^scale_exp
            if(elem_mant_b == 1'b0) fp32_b = 32'h00000000;
            else if(sub_exp_b > 9'd254) fp32_b = elem_sign_b ? 32'hFF800000 : 32'h7F800000;
            else if(sub_exp_b[8]) fp32_b = 32'h00000000;
            else fp32_b = {elem_sign_b, sub_exp_b[7:0], 23'b0};
        end
    end
    wire [3:0] elem_c = fmt_c_c[3:0];
    wire [7:0] scale_code_c = fmt_c_c[15:8];
    wire elem_sign_c = elem_c[3];
    wire [1:0] elem_exp_c = elem_c[2:1];
    wire elem_mant_c = elem_c[0];
    wire elem_zero_c = (elem_c == 4'b0000);
    wire signed [9:0] scale_exp_c = $signed({1'b0, scale_code_c}) - 10'sd127;
    // Element decode (E2M1, BIAS=1)
    wire signed [4:0] elem_de_c = (elem_exp_c == 2'b00) ? -5'sd0 : ($signed({1'b0, elem_exp_c}) - 5'sd1);
    wire [8:0] elem_fp32_exp_raw_c = {1'b0, elem_de_c} + 9'd127 + scale_exp_c;
    // Normal: exp=01,10,11 → mantissa with hidden bit
    // Subnormal: exp=00
    wire is_elem_norm_c = (elem_exp_c != 2'b00);
    wire [8:0] sub_exp_c = 9'd127 + scale_exp_c;  // subnormal real_exp = 1-1 = 0
    reg [31:0] fp32_c;
    always @(*) begin
        if(elem_zero_c) fp32_c=32'h00000000;
        else if(is_elem_norm_c) begin
            if(elem_fp32_exp_raw_c > 9'd254) fp32_c = elem_sign_c ? 32'hFF800000 : 32'h7F800000;
            else if(elem_fp32_exp_raw_c[8]) fp32_c = 32'h00000000;
            else fp32_c = {elem_sign_c, elem_fp32_exp_raw_c[7:0], elem_mant_c, 22'b0};
        end else begin
            // Subnormal: value = elem_mant * 2^scale_exp
            if(elem_mant_c == 1'b0) fp32_c = 32'h00000000;
            else if(sub_exp_c > 9'd254) fp32_c = elem_sign_c ? 32'hFF800000 : 32'h7F800000;
            else if(sub_exp_c[8]) fp32_c = 32'h00000000;
            else fp32_c = {elem_sign_c, sub_exp_c[7:0], 23'b0};
        end
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
    // Extract element (E2M1) and scale (E8M0) from FP32
    // Scale = q_exp >> 1 (coarse), element exp = q_exp & 1
    wire [7:0] scale_byte = q_exp;
    wire [1:0] elem_exp = q_mant[22:21];
    wire elem_mant = q_mant[20];
    reg [15:0] q_result;
    always @(*) begin
        if(q_nan) q_result=16'h0;
        else if(q_zero) q_result=16'h0;
        else q_result={scale_byte, 4'b0, q_sign, elem_exp, elem_mant};
    end
    reg [31:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=add_ovld;
            if(add_ovld) result_reg<={16'b0,q_result};
        end
    end
    assign led[2]=|result_reg;
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
