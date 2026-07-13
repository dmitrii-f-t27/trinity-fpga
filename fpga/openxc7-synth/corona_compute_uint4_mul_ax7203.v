`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_uint4_mul_ax7203 — UINT4 MUL on AX7203.
module corona_compute_uint4_mul_ax7203 (
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

    reg [2:0] frm; reg [7:0] fmt_r; reg [3:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3'd3; end
                3'd3: begin a_r[3:0]<=rx_byte;frm<=3'd4; end
                3'd4: begin b_r[3:0]<=rx_byte;frm<=3'd5; end
                3'd5: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [3:0] a_reg,b_reg; reg comp_trigger;
    wire [3:0] fmt_a=a_reg, fmt_b=b_reg;
    wire [3:0] uval_a = fmt_a_a[3:0];
    wire u_zero_a = (uval_a == 4'd0);
    wire [2:0] u_lzd_a;
    always @(*) begin
        casez(uval_a)
            4'b1???: u_lzd_a=3'd0;
            4'b01??: u_lzd_a=3'd1;
            4'b001?: u_lzd_a=3'd2;
            default: u_lzd_a=3'd3;
        endcase
    end
    wire [7:0] u_fp32_exp_a = 8'd127 + 8'd3 - {5'b0, u_lzd_a};
    wire [3:0] u_shifted_a = uval_a << {u_lzd_a, 1'b0};
    wire [22:0] u_fp32_mant_a = {u_shifted_a[2:0], 20'b0};
    reg [31:0] fp32_a;
    always @(*) begin
        if(u_zero_a) fp32_a=32'h00000000;
        else fp32_a={1'b0, u_fp32_exp_a, u_fp32_mant_a};
    end
    wire [3:0] uval_b = fmt_b_b[3:0];
    wire u_zero_b = (uval_b == 4'd0);
    wire [2:0] u_lzd_b;
    always @(*) begin
        casez(uval_b)
            4'b1???: u_lzd_b=3'd0;
            4'b01??: u_lzd_b=3'd1;
            4'b001?: u_lzd_b=3'd2;
            default: u_lzd_b=3'd3;
        endcase
    end
    wire [7:0] u_fp32_exp_b = 8'd127 + 8'd3 - {5'b0, u_lzd_b};
    wire [3:0] u_shifted_b = uval_b << {u_lzd_b, 1'b0};
    wire [22:0] u_fp32_mant_b = {u_shifted_b[2:0], 20'b0};
    reg [31:0] fp32_b;
    always @(*) begin
        if(u_zero_b) fp32_b=32'h00000000;
        else fp32_b={1'b0, u_fp32_exp_b, u_fp32_mant_b};
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
    wire signed [9:0] q_real_exp = $signed({1'b0, q_exp}) - 10'sd127;
    wire [15:0] q_abs_mant = {1'b1, q_mant, 8'b0};
    wire [15:0] q_shifted = (q_real_exp >= 0) ? (q_abs_mant << q_real_exp[3:0]) : (q_abs_mant >> (-q_real_exp[3:0]));
    reg [3:0] q_result;
    always @(*) begin
        if(q_nan) q_result=4'd0;
        else if(q_zero) q_result=4'd0;
        else if(q_sign) q_result=4'd0;
        else if(q_shifted > 16'd15) q_result=4'hF;
        else q_result=q_shifted[3:0];
    end
    reg [31:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=comp_ovld;
            if(comp_ovld) result_reg<={28'b0,q_result};
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
