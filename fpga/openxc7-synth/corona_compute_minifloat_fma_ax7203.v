`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_minifloat_fma_ax7203 — MINIFLOAT FMA on AX7203.
module corona_compute_minifloat_fma_ax7203 (
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

    reg [2:0] frm; reg [7:0] fmt_r; reg [7:0] a_r,b_r,c_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;c_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3'd3; end
                3'd3: begin a_r[3:0]<=rx_byte;frm<=3'd4; end
                3'd4: begin b_r[3:0]<=rx_byte;frm<=3'd5; end
                3'd5: begin c_r[3:0]<=rx_byte;frm<=3'd6; end
                3'd6: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [7:0] a_reg,b_reg,c_reg; reg comp_trigger;
    wire [7:0] mf_a=a_reg, mf_b=b_reg, mf_c=c_reg;
    wire sa_a=mf_a[7]; wire [2:0] ea_a=mf_a[6:4]; wire [3:0] ma_a=mf_a[3:0];
    wire sub_a=(ea_a==0)&&(ma_a!=0); wire nan_a=(ea_a==7)&&(ma_a!=0);
    wire [7:0] exp32_a=sub_a?8'd125:({5'd0,ea_a}+8'd124); wire [22:0] mant32_a={ma_a,19'b0};
    wire [31:0] fp32_a=(ea_a==0&&ma_a==0)?32'h0:nan_a?32'h7FC00000:{sa_a,exp32_a,mant32_a};
    wire sb_b=mf_b[7]; wire [2:0] eb_b=mf_b[6:4]; wire [3:0] mb_b=mf_b[3:0];
    wire sub_b=(eb_b==0)&&(mb_b!=0); wire nan_b=(eb_b==7)&&(mb_b!=0);
    wire [7:0] exp32_b=sub_b?8'd125:({5'd0,eb_b}+8'd124); wire [22:0] mant32_b={mb_b,19'b0};
    wire [31:0] fp32_b=(eb_b==0&&mb_b==0)?32'h0:nan_b?32'h7FC00000:{sb_b,exp32_b,mant32_b};
    wire sc_c=mf_c[7]; wire [2:0] ec_c=mf_c[6:4]; wire [3:0] mc_c=mf_c[3:0];
    wire sub_c=(ec_c==0)&&(mc_c!=0); wire nan_c=(ec_c==7)&&(mc_c!=0);
    wire [7:0] exp32_c=sub_c?8'd125:({5'd0,ec_c}+8'd124); wire [22:0] mant32_c={mc_c,19'b0};
    wire [31:0] fp32_c=(ec_c==0&&mc_c==0)?32'h0:nan_c?32'h7FC00000:{sc_c,exp32_c,mant32_c};
    wire mul_irdy,mul_ovld; wire [31:0] mul_result;
    wire add_irdy,add_ovld; wire [31:0] add_result;
    gf_mul_param #(.EXP_BITS(3),.MANT_BITS(4),.HAS_INF(1)) u_mul (
        .clk(mclk),.rst(rst),.in_valid(comp_trigger),.in_a(fp32_a),.in_b(fp32_b),
        .in_ready(mul_irdy),.out_valid(mul_ovld),.out_y(mul_result),.out_ready(1'b1));
    gf_adder_param #(.EXP_BITS(3),.MANT_BITS(4),.HAS_INF(1)) u_add (
        .clk(mclk),.rst(rst),.in_valid(mul_ovld),.in_a(mul_result),.in_b(fp32_c),
        .in_ready(add_irdy),.out_valid(add_ovld),.out_y(add_result),.out_ready(1'b1));
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;b_reg<=0;c_reg<=0;comp_trigger<=0; end
        else begin comp_trigger<=frame_valid;
            if(frame_valid) begin a_reg<=a_r;b_reg<=b_r;c_reg<=c_r; end
        end
    end
    wire cs=add_result[31]; wire [7:0] ce=add_result[30:23]; wire [22:0] cm=add_result[22:0];
    wire [8:0] mf_e={1'b0,ce}-9'd124;
    reg [7:0] mf_result;
    always @(*) begin
        if(add_result==32'h0) mf_result=8'h00;
        else if(add_result==32'h7FC00000) mf_result=8'h7F;
        else if(add_result[30:23]>=8'd131) mf_result={cs,3'd6,4'd8};
        else if(mf_e[8]) mf_result=8'h00;
        else mf_result={cs,mf_e[2:0],cm[22:19]};
    end
    reg [31:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=add_ovld;
            if(add_ovld) result_reg<={24'b0,mf_result};
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
