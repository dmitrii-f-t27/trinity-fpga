`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_ibm_hfp64_alu_ax7203 — IBM_HFP64 ALU on AX7203.
module corona_compute_ibm_hfp64_alu_ax7203 (
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

    reg [4:0] frm; reg [7:0] fmt_r,op_r; reg [63:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;op_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                5'd0: frm<=(rx_byte==8'hAA)?5'd1:5'd0;
                5'd1: frm<=(rx_byte==8'h55)?5'd2:5'd0;
                5'd2: begin fmt_r<=rx_byte;frm<=5'd3; end
                5'd3: begin op_r<=rx_byte;frm<=5'd4; end
                5'd4: begin a_r[7:0]<=rx_byte;frm<=5'd5; end
                5'd5: begin a_r[15:8]<=rx_byte;frm<=5'd6; end
                5'd6: begin a_r[23:16]<=rx_byte;frm<=5'd7; end
                5'd7: begin a_r[31:24]<=rx_byte;frm<=5'd8; end
                5'd8: begin a_r[39:32]<=rx_byte;frm<=5'd9; end
                5'd9: begin a_r[47:40]<=rx_byte;frm<=5'd10; end
                5'd10: begin a_r[55:48]<=rx_byte;frm<=5'd11; end
                5'd11: begin a_r[63:56]<=rx_byte;frm<=5'd12; end
                5'd12: begin b_r[7:0]<=rx_byte;frm<=5'd13; end
                5'd13: begin b_r[15:8]<=rx_byte;frm<=5'd14; end
                5'd14: begin b_r[23:16]<=rx_byte;frm<=5'd15; end
                5'd15: begin b_r[31:24]<=rx_byte;frm<=5'd16; end
                5'd16: begin b_r[39:32]<=rx_byte;frm<=5'd17; end
                5'd17: begin b_r[47:40]<=rx_byte;frm<=5'd18; end
                5'd18: begin b_r[55:48]<=rx_byte;frm<=5'd19; end
                5'd19: begin b_r[63:56]<=rx_byte;frm<=5'd20; end
                5'd20: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [63:0] a_reg,b_reg; reg [7:0] op_reg; reg comp_trigger;
    wire [63:0] fmt_a=a_reg, fmt_b=b_reg;
    wire ib_sign_a = fmt_a[63];
    wire [6:0] ib_exp_a = fmt_a[62:56];
    wire [55:0] ib_frac_a = fmt_a[55:0];
    wire ib_zero_a = (ib_exp_a == 7'd0) && (ib_frac_a == 56'd0);
    reg [2:0] ib_lhd_a;
    always @(*) begin
        casez(ib_frac_a[55:52])
            4'b1???: ib_lhd_a=3'd0;
            4'b01??: ib_lhd_a=3'd1;
            4'b001?: ib_lhd_a=3'd2;
            4'b0001: ib_lhd_a=3'd3;
            default: ib_lhd_a=3'd4;
        endcase
    end
    wire [55:0] ib_shifted_a = ib_frac_a << ({ib_lhd_a, 2'b00});
    wire signed [10:0] ib_exp_s_a = $signed({1'b0, ib_exp_a, 2'b00}) - 11'sd185
        + $signed({8'b0, ib_lhd_a, 2'b00});
    wire [7:0] ib_exp32_a = ib_exp_s_a[7:0];
    wire [22:0] ib_mant32_a = ib_shifted_a[54:32];
    reg [31:0] fp32_a;
    always @(*) begin
        if(ib_zero_a) fp32_a=32'h00000000;
        else fp32_a={ib_sign_a, ib_exp32_a, ib_mant32_a};
    end
    wire ib_sign_b = fmt_b[63];
    wire [6:0] ib_exp_b = fmt_b[62:56];
    wire [55:0] ib_frac_b = fmt_b[55:0];
    wire ib_zero_b = (ib_exp_b == 7'd0) && (ib_frac_b == 56'd0);
    reg [2:0] ib_lhd_b;
    always @(*) begin
        casez(ib_frac_b[55:52])
            4'b1???: ib_lhd_b=3'd0;
            4'b01??: ib_lhd_b=3'd1;
            4'b001?: ib_lhd_b=3'd2;
            4'b0001: ib_lhd_b=3'd3;
            default: ib_lhd_b=3'd4;
        endcase
    end
    wire [55:0] ib_shifted_b = ib_frac_b << ({ib_lhd_b, 2'b00});
    wire signed [10:0] ib_exp_s_b = $signed({1'b0, ib_exp_b, 2'b00}) - 11'sd185
        + $signed({8'b0, ib_lhd_b, 2'b00});
    wire [7:0] ib_exp32_b = ib_exp_s_b[7:0];
    wire [22:0] ib_mant32_b = ib_shifted_b[54:32];
    reg [31:0] fp32_b;
    always @(*) begin
        if(ib_zero_b) fp32_b=32'h00000000;
        else fp32_b={ib_sign_b, ib_exp32_b, ib_mant32_b};
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
    wire signed [9:0] ib_raw = $signed({1'b0, q_exp}) - 10'sd126;
    wire [7:0] ib_exp = ib_raw[9] ? 8'd0 : {ib_raw[8:1] + 8'd64};
    wire [1:0] ib_sub = ib_raw[0] ? 2'd3 : 2'd0;
    reg [63:0] q_result;
    always @(*) begin
        if(q_nan) q_result=64'h0;
        else if(q_zero) q_result=64'h0;
        else q_result={q_sign, ib_exp[6:0], 4'h8, q_mant, 29'b0};
    end
    reg [63:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=ovld;
            if(ovld) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [3:0] TX_LEN = 9;
    reg responding; reg [3:0] tx_cnt;
    reg [71:0] tx_shift;
    wire [71:0] tx_load = {result_reg, 8'hA5};
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
                        tx_shift<={8'h00,tx_shift[71:8]};
                        if(tx_cnt==TX_LEN-1) responding<=0; else tx_cnt<=tx_cnt+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
endmodule
`default_nettype wire
