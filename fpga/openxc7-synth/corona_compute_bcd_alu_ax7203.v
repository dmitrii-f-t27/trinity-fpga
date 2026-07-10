`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_bcd_alu_ax7203 — BCD ALU on AX7203.
module corona_compute_bcd_alu_ax7203 (
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

    reg [2:0] frm; reg [7:0] fmt_r,op_r; reg [7:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;op_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3'd3; end
                3'd3: begin op_r<=rx_byte;frm<=3'd4; end
                3'd4: begin a_r[7:0]<=rx_byte;frm<=3'd5; end
                3'd5: begin b_r[7:0]<=rx_byte;frm<=3'd6; end
                3'd6: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [7:0] a_reg,b_reg; reg [7:0] op_reg; reg comp_trigger;
    wire [7:0] fmt_a=a_reg, fmt_b=b_reg;
    wire [3:0] bcd_t_a = fmt_a[7:4];
    wire [3:0] bcd_o_a = fmt_a[3:0];
    wire [6:0] bcd_int_a = bcd_t_a * 5'd10 + {3'b0, bcd_o_a};
    wire bcd_zero_a = (bcd_int_a == 7'd0);
    reg [2:0] bcd_lop_a;
    always @(*) begin
        casez(bcd_int_a)
            7'b1??????: bcd_lop_a=3'd6;
            7'b01?????: bcd_lop_a=3'd5;
            7'b001????: bcd_lop_a=3'd4;
            7'b0001???: bcd_lop_a=3'd3;
            7'b00001??: bcd_lop_a=3'd2;
            7'b000001?: bcd_lop_a=3'd1;
            default: bcd_lop_a=3'd0;
        endcase
    end
    wire [7:0] bcd_exp_a = 8'd127 + {5'b0, bcd_lop_a};
    reg [22:0] bcd_mant_a;
    always @(*) begin
        case(bcd_lop_a)
            3'd6: bcd_mant_a={bcd_int_a[5:0],17'b0};
            3'd5: bcd_mant_a={bcd_int_a[4:0],18'b0};
            3'd4: bcd_mant_a={bcd_int_a[3:0],19'b0};
            3'd3: bcd_mant_a={bcd_int_a[2:0],20'b0};
            3'd2: bcd_mant_a={bcd_int_a[1:0],21'b0};
            3'd1: bcd_mant_a={bcd_int_a[0],22'b0};
            default: bcd_mant_a=23'b0;
        endcase
    end
    reg [31:0] fp32_a;
    always @(*) begin
        if(bcd_zero_a) fp32_a=32'h00000000;
        else fp32_a={1'b0, bcd_exp_a, bcd_mant_a};
    end
    wire [3:0] bcd_t_b = fmt_b[7:4];
    wire [3:0] bcd_o_b = fmt_b[3:0];
    wire [6:0] bcd_int_b = bcd_t_b * 5'd10 + {3'b0, bcd_o_b};
    wire bcd_zero_b = (bcd_int_b == 7'd0);
    reg [2:0] bcd_lop_b;
    always @(*) begin
        casez(bcd_int_b)
            7'b1??????: bcd_lop_b=3'd6;
            7'b01?????: bcd_lop_b=3'd5;
            7'b001????: bcd_lop_b=3'd4;
            7'b0001???: bcd_lop_b=3'd3;
            7'b00001??: bcd_lop_b=3'd2;
            7'b000001?: bcd_lop_b=3'd1;
            default: bcd_lop_b=3'd0;
        endcase
    end
    wire [7:0] bcd_exp_b = 8'd127 + {5'b0, bcd_lop_b};
    reg [22:0] bcd_mant_b;
    always @(*) begin
        case(bcd_lop_b)
            3'd6: bcd_mant_b={bcd_int_b[5:0],17'b0};
            3'd5: bcd_mant_b={bcd_int_b[4:0],18'b0};
            3'd4: bcd_mant_b={bcd_int_b[3:0],19'b0};
            3'd3: bcd_mant_b={bcd_int_b[2:0],20'b0};
            3'd2: bcd_mant_b={bcd_int_b[1:0],21'b0};
            3'd1: bcd_mant_b={bcd_int_b[0],22'b0};
            default: bcd_mant_b=23'b0;
        endcase
    end
    reg [31:0] fp32_b;
    always @(*) begin
        if(bcd_zero_b) fp32_b=32'h00000000;
        else fp32_b={1'b0, bcd_exp_b, bcd_mant_b};
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
    wire [7:0] q_exp=q_in[30:23]; wire [22:0] q_mant=q_in[22:0];
    wire q_nan=(q_in==32'h7FC00000); wire q_zero=(q_in==32'h00000000);
    wire [8:0] q_lop = {1'b0,q_exp} - 9'd127;
    reg [6:0] q_int;
    reg [7:0] q_result;
    always @(*) begin
        if(q_nan) q_result=8'h00;
        else if(q_zero) q_result=8'h00;
        else begin
            case(q_lop[2:0])
                3'd6: q_int={1'b1,q_mant[22:17]};
                3'd5: q_int={2'b01,q_mant[22:18]};
                3'd4: q_int={3'b001,q_mant[22:19]};
                3'd3: q_int={4'b0001,q_mant[22:20]};
                3'd2: q_int={5'b00001,q_mant[22:21]};
                3'd1: q_int={6'b000001,q_mant[22]};
                default: q_int=7'd1;
            endcase
            if(q_int > 7'd99) q_int = 7'd99;
            // BCD encode: tens = int/10, ones = int%10
            case(q_int)
                7'd0: q_result=8'h00; 7'd1: q_result=8'h01;  7'd2: q_result=8'h02;
                7'd3: q_result=8'h03; 7'd4: q_result=8'h04;  7'd5: q_result=8'h05;
                7'd6: q_result=8'h06; 7'd7: q_result=8'h07;  7'd8: q_result=8'h08;
                7'd9: q_result=8'h09; 7'd10: q_result=8'h10; 7'd11: q_result=8'h11;
                7'd12: q_result=8'h12; 7'd13: q_result=8'h13; 7'd14: q_result=8'h14;
                7'd15: q_result=8'h15; 7'd16: q_result=8'h16; 7'd17: q_result=8'h17;
                7'd18: q_result=8'h18; 7'd19: q_result=8'h19; 7'd20: q_result=8'h20;
                7'd21: q_result=8'h21; 7'd22: q_result=8'h22; 7'd23: q_result=8'h23;
                7'd24: q_result=8'h24; 7'd25: q_result=8'h25; 7'd26: q_result=8'h26;
                7'd27: q_result=8'h27; 7'd28: q_result=8'h28; 7'd29: q_result=8'h29;
                7'd30: q_result=8'h30; 7'd31: q_result=8'h31; 7'd32: q_result=8'h32;
                7'd33: q_result=8'h33; 7'd34: q_result=8'h34; 7'd35: q_result=8'h35;
                7'd36: q_result=8'h36; 7'd37: q_result=8'h37; 7'd38: q_result=8'h38;
                7'd39: q_result=8'h39; 7'd40: q_result=8'h40; 7'd41: q_result=8'h41;
                7'd42: q_result=8'h42; 7'd43: q_result=8'h43; 7'd44: q_result=8'h44;
                7'd45: q_result=8'h45; 7'd46: q_result=8'h46; 7'd47: q_result=8'h47;
                7'd48: q_result=8'h48; 7'd49: q_result=8'h49; 7'd50: q_result=8'h50;
                7'd51: q_result=8'h51; 7'd52: q_result=8'h52; 7'd53: q_result=8'h53;
                7'd54: q_result=8'h54; 7'd55: q_result=8'h55; 7'd56: q_result=8'h56;
                7'd57: q_result=8'h57; 7'd58: q_result=8'h58; 7'd59: q_result=8'h59;
                7'd60: q_result=8'h60; 7'd61: q_result=8'h61; 7'd62: q_result=8'h62;
                7'd63: q_result=8'h63; 7'd64: q_result=8'h64; 7'd65: q_result=8'h65;
                7'd66: q_result=8'h66; 7'd67: q_result=8'h67; 7'd68: q_result=8'h68;
                7'd69: q_result=8'h69; 7'd70: q_result=8'h70; 7'd71: q_result=8'h71;
                7'd72: q_result=8'h72; 7'd73: q_result=8'h73; 7'd74: q_result=8'h74;
                7'd75: q_result=8'h75; 7'd76: q_result=8'h76; 7'd77: q_result=8'h77;
                7'd78: q_result=8'h78; 7'd79: q_result=8'h79; 7'd80: q_result=8'h80;
                7'd81: q_result=8'h81; 7'd82: q_result=8'h82; 7'd83: q_result=8'h83;
                7'd84: q_result=8'h84; 7'd85: q_result=8'h85; 7'd86: q_result=8'h86;
                7'd87: q_result=8'h87; 7'd88: q_result=8'h88; 7'd89: q_result=8'h89;
                7'd90: q_result=8'h90; 7'd91: q_result=8'h91; 7'd92: q_result=8'h92;
                7'd93: q_result=8'h93; 7'd94: q_result=8'h94; 7'd95: q_result=8'h95;
                7'd96: q_result=8'h96; 7'd97: q_result=8'h97; 7'd98: q_result=8'h98;
                default: q_result=8'h99;
            endcase
        end
    end
    reg [31:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=ovld;
            if(ovld) result_reg<={24'b0,q_result};
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
