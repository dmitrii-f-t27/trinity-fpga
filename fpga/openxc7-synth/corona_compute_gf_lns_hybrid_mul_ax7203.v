`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_gf_lns_hybrid_mul_ax7203 — GF_LNS_HYBRID MUL on AX7203.
module corona_compute_gf_lns_hybrid_mul_ax7203 (
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

    reg [2:0] frm; reg [7:0] fmt_r; reg [15:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3'd3; end
                3'd3: begin a_r[7:0]<=rx_byte;frm<=3'd4; end
                3'd4: begin a_r[15:8]<=rx_byte;frm<=3'd5; end
                3'd5: begin b_r[7:0]<=rx_byte;frm<=3'd6; end
                3'd6: begin b_r[15:8]<=rx_byte;frm<=3'd7; end
                3'd7: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [15:0] a_reg,b_reg; reg comp_trigger;
    wire [15:0] fmt_a=a_reg, fmt_b=b_reg;
    wire gl_sign_a = fmt_a[15];
    wire [5:0] gl_exp_a = fmt_a[14:9];
    wire [8:0] gl_mant_a = fmt_a[8:0];
    wire gl_zero_a = (gl_exp_a == 6'd0) && (gl_mant_a == 9'd0);
    wire gl_nan_a = (gl_exp_a == 6'd63) && (gl_mant_a != 0);
    wire gl_inf_a = (gl_exp_a == 6'd63) && (gl_mant_a == 0);
    wire gl_sub_a = (gl_exp_a == 6'd0) && (gl_mant_a != 0);
    wire [7:0] gl_exp32_a = gl_sub_a ? 8'd96 : ({2'b0, gl_exp_a} + 8'd96);
    wire [22:0] gl_mant32_a = {gl_mant_a, 14'b0};
    reg [31:0] fp32_a;
    always @(*) begin
        if(gl_zero_a) fp32_a=32'h00000000;
        else if(gl_nan_a) fp32_a=32'h7FC00000;
        else if(gl_inf_a) fp32_a={gl_sign_a, 8'hFF, 23'b0};
        else fp32_a={gl_sign_a, gl_exp32_a, gl_mant32_a};
    end
    wire gl_sign_b = fmt_b[15];
    wire [5:0] gl_exp_b = fmt_b[14:9];
    wire [8:0] gl_mant_b = fmt_b[8:0];
    wire gl_zero_b = (gl_exp_b == 6'd0) && (gl_mant_b == 9'd0);
    wire gl_nan_b = (gl_exp_b == 6'd63) && (gl_mant_b != 0);
    wire gl_inf_b = (gl_exp_b == 6'd63) && (gl_mant_b == 0);
    wire gl_sub_b = (gl_exp_b == 6'd0) && (gl_mant_b != 0);
    wire [7:0] gl_exp32_b = gl_sub_b ? 8'd96 : ({2'b0, gl_exp_b} + 8'd96);
    wire [22:0] gl_mant32_b = {gl_mant_b, 14'b0};
    reg [31:0] fp32_b;
    always @(*) begin
        if(gl_zero_b) fp32_b=32'h00000000;
        else if(gl_nan_b) fp32_b=32'h7FC00000;
        else if(gl_inf_b) fp32_b={gl_sign_b, 8'hFF, 23'b0};
        else fp32_b={gl_sign_b, gl_exp32_b, gl_mant32_b};
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
    wire [8:0] q_gl_exp = q_exp - 8'd96;
    reg [15:0] q_result;
    always @(*) begin
        if(q_nan) q_result={1'b0,6'd63,9'd1};
        else if(q_zero) q_result=16'h0000;
        else if(q_inf) q_result={q_sign,6'd63,9'b0};
        else if(q_exp<8'd97) q_result={q_sign,6'd0,9'd0};
        else if(q_exp>=8'd158) q_result={q_sign,6'd62,{q_mant[22:14]}};
        else q_result={q_sign,q_gl_exp[5:0],q_mant[22:14]};
    end
    reg [31:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=comp_ovld;
            if(comp_ovld) result_reg<={16'b0,q_result};
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
