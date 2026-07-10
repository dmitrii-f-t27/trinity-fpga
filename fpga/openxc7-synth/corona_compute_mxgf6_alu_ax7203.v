`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_mxgf6_alu_ax7203 — MXGF6 ALU on AX7203.
module corona_compute_mxgf6_alu_ax7203 (
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

    reg [2:0] frm; reg [7:0] fmt_r,op_r; reg [5:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;op_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3'd3; end
                3'd3: begin op_r<=rx_byte;frm<=3'd4; end
                3'd4: begin a_r[5:0]<=rx_byte;frm<=3'd5; end
                3'd5: begin b_r[5:0]<=rx_byte;frm<=3'd6; end
                3'd6: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [5:0] a_reg,b_reg; reg [7:0] op_reg; reg comp_trigger;
    wire [5:0] fmt_a=a_reg, fmt_b=b_reg;
    reg [31:0] fp32_a;
    always @(*) begin
        case(fmt_a[5:0])
            6'd0: fp32_a=32'h00000000;
            6'd1: fp32_a=32'h3e000000;
            6'd2: fp32_a=32'h3e800000;
            6'd3: fp32_a=32'h3ec00000;
            6'd4: fp32_a=32'h3f000000;
            6'd5: fp32_a=32'h3f200000;
            6'd6: fp32_a=32'h3f400000;
            6'd7: fp32_a=32'h3f600000;
            6'd8: fp32_a=32'h3f800000;
            6'd9: fp32_a=32'h3f900000;
            6'd10: fp32_a=32'h3fa00000;
            6'd11: fp32_a=32'h3fb00000;
            6'd12: fp32_a=32'h3fc00000;
            6'd13: fp32_a=32'h3fd00000;
            6'd14: fp32_a=32'h3fe00000;
            6'd15: fp32_a=32'h3ff00000;
            6'd16: fp32_a=32'h40000000;
            6'd17: fp32_a=32'h40100000;
            6'd18: fp32_a=32'h40200000;
            6'd19: fp32_a=32'h40300000;
            6'd20: fp32_a=32'h40400000;
            6'd21: fp32_a=32'h40500000;
            6'd22: fp32_a=32'h40600000;
            6'd23: fp32_a=32'h40700000;
            6'd24: fp32_a=32'h40800000;
            6'd25: fp32_a=32'h40900000;
            6'd26: fp32_a=32'h40a00000;
            6'd27: fp32_a=32'h40b00000;
            6'd28: fp32_a=32'h40c00000;
            6'd29: fp32_a=32'h40d00000;
            6'd30: fp32_a=32'h40e00000;
            6'd31: fp32_a=32'h40f00000;
            6'd32: fp32_a=32'h80000000;
            6'd33: fp32_a=32'hbe000000;
            6'd34: fp32_a=32'hbe800000;
            6'd35: fp32_a=32'hbec00000;
            6'd36: fp32_a=32'hbf000000;
            6'd37: fp32_a=32'hbf200000;
            6'd38: fp32_a=32'hbf400000;
            6'd39: fp32_a=32'hbf600000;
            6'd40: fp32_a=32'hbf800000;
            6'd41: fp32_a=32'hbf900000;
            6'd42: fp32_a=32'hbfa00000;
            6'd43: fp32_a=32'hbfb00000;
            6'd44: fp32_a=32'hbfc00000;
            6'd45: fp32_a=32'hbfd00000;
            6'd46: fp32_a=32'hbfe00000;
            6'd47: fp32_a=32'hbff00000;
            6'd48: fp32_a=32'hc0000000;
            6'd49: fp32_a=32'hc0100000;
            6'd50: fp32_a=32'hc0200000;
            6'd51: fp32_a=32'hc0300000;
            6'd52: fp32_a=32'hc0400000;
            6'd53: fp32_a=32'hc0500000;
            6'd54: fp32_a=32'hc0600000;
            6'd55: fp32_a=32'hc0700000;
            6'd56: fp32_a=32'hc0800000;
            6'd57: fp32_a=32'hc0900000;
            6'd58: fp32_a=32'hc0a00000;
            6'd59: fp32_a=32'hc0b00000;
            6'd60: fp32_a=32'hc0c00000;
            6'd61: fp32_a=32'hc0d00000;
            6'd62: fp32_a=32'hc0e00000;
            6'd63: fp32_a=32'hc0f00000;
            default: fp32_a=32'h00000000;
        endcase
    end
    reg [31:0] fp32_b;
    always @(*) begin
        case(fmt_b[5:0])
            6'd0: fp32_b=32'h00000000;
            6'd1: fp32_b=32'h3e000000;
            6'd2: fp32_b=32'h3e800000;
            6'd3: fp32_b=32'h3ec00000;
            6'd4: fp32_b=32'h3f000000;
            6'd5: fp32_b=32'h3f200000;
            6'd6: fp32_b=32'h3f400000;
            6'd7: fp32_b=32'h3f600000;
            6'd8: fp32_b=32'h3f800000;
            6'd9: fp32_b=32'h3f900000;
            6'd10: fp32_b=32'h3fa00000;
            6'd11: fp32_b=32'h3fb00000;
            6'd12: fp32_b=32'h3fc00000;
            6'd13: fp32_b=32'h3fd00000;
            6'd14: fp32_b=32'h3fe00000;
            6'd15: fp32_b=32'h3ff00000;
            6'd16: fp32_b=32'h40000000;
            6'd17: fp32_b=32'h40100000;
            6'd18: fp32_b=32'h40200000;
            6'd19: fp32_b=32'h40300000;
            6'd20: fp32_b=32'h40400000;
            6'd21: fp32_b=32'h40500000;
            6'd22: fp32_b=32'h40600000;
            6'd23: fp32_b=32'h40700000;
            6'd24: fp32_b=32'h40800000;
            6'd25: fp32_b=32'h40900000;
            6'd26: fp32_b=32'h40a00000;
            6'd27: fp32_b=32'h40b00000;
            6'd28: fp32_b=32'h40c00000;
            6'd29: fp32_b=32'h40d00000;
            6'd30: fp32_b=32'h40e00000;
            6'd31: fp32_b=32'h40f00000;
            6'd32: fp32_b=32'h80000000;
            6'd33: fp32_b=32'hbe000000;
            6'd34: fp32_b=32'hbe800000;
            6'd35: fp32_b=32'hbec00000;
            6'd36: fp32_b=32'hbf000000;
            6'd37: fp32_b=32'hbf200000;
            6'd38: fp32_b=32'hbf400000;
            6'd39: fp32_b=32'hbf600000;
            6'd40: fp32_b=32'hbf800000;
            6'd41: fp32_b=32'hbf900000;
            6'd42: fp32_b=32'hbfa00000;
            6'd43: fp32_b=32'hbfb00000;
            6'd44: fp32_b=32'hbfc00000;
            6'd45: fp32_b=32'hbfd00000;
            6'd46: fp32_b=32'hbfe00000;
            6'd47: fp32_b=32'hbff00000;
            6'd48: fp32_b=32'hc0000000;
            6'd49: fp32_b=32'hc0100000;
            6'd50: fp32_b=32'hc0200000;
            6'd51: fp32_b=32'hc0300000;
            6'd52: fp32_b=32'hc0400000;
            6'd53: fp32_b=32'hc0500000;
            6'd54: fp32_b=32'hc0600000;
            6'd55: fp32_b=32'hc0700000;
            6'd56: fp32_b=32'hc0800000;
            6'd57: fp32_b=32'hc0900000;
            6'd58: fp32_b=32'hc0a00000;
            6'd59: fp32_b=32'hc0b00000;
            6'd60: fp32_b=32'hc0c00000;
            6'd61: fp32_b=32'hc0d00000;
            6'd62: fp32_b=32'hc0e00000;
            6'd63: fp32_b=32'hc0f00000;
            default: fp32_b=32'h00000000;
        endcase
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
    reg [5:0] q_result;
    wire signed [9:0] tgt_exp_s = $signed({1'b0, q_exp}) - 10'sd127 + 10'sd1;
    always @(*) begin
        if(q_nan) q_result=6'd0;
        else if(q_zero) q_result=6'd0;
        else if(q_exp >= 8'd130) q_result={q_sign, 5'd31};
        else if(q_exp < 8'd127) q_result={q_sign, 5'd0};
        else if(tgt_exp_s < 1) q_result={q_sign, 2'b0, q_mant[22:20]};
        else q_result={q_sign, tgt_exp_s[1:0], q_mant[22:20]};
    end
    reg [31:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=ovld;
            if(ovld) result_reg<={26'b0,q_result};
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
