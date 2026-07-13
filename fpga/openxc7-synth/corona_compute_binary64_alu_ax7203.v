`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_binary64_alu_ax7203 — BINARY64 ALU on AX7203.
module corona_compute_binary64_alu_ax7203 (
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
    wire add_irdy,add_ovld; wire [63:0] add_res;
    wire mul_irdy,mul_ovld; wire [63:0] mul_res;
    gf_adder_param #(.EXP_BITS(11),.MANT_BITS(52),.HAS_INF(1)) u_add (
        .clk(mclk),.rst(rst),.in_valid(comp_trigger),.in_a(a_reg),.in_b(b_reg),
        .in_ready(add_irdy),.out_valid(add_ovld),.out_y(add_res),.out_ready(1'b1));
    gf_mul_param #(.EXP_BITS(11),.MANT_BITS(52),.HAS_INF(1)) u_mul (
        .clk(mclk),.rst(rst),.in_valid(comp_trigger),.in_a(a_reg),.in_b(b_reg),
        .in_ready(mul_irdy),.out_valid(mul_ovld),.out_y(mul_res),.out_ready(1'b1));
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;b_reg<=0;op_reg<=0;comp_trigger<=0; end
        else begin comp_trigger<=frame_valid;
            if(frame_valid) begin a_reg<=a_r;b_reg<=b_r;op_reg<=op_r; end
        end
    end
    wire [63:0] ar=(op_reg==8'h00)?add_res:mul_res;
    wire av=(op_reg==8'h00)?add_ovld:mul_ovld;
    reg [63:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=av;
            if(av) result_reg<=ar;
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
