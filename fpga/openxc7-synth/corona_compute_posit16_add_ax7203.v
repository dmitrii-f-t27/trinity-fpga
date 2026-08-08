`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_posit16_add_ax7203 — POSIT16 ADD on AX7203.
module corona_compute_posit16_add_ax7203 (
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

    reg [2:0] frm; reg [7:0] fmt_r; reg [15:0] a_r,b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3'd3; end
                3'd3: begin a_r[7:0]<=rx_byte;frm<=3'd4; end
                3'd4: begin b_r[7:0]<=rx_byte;frm<=3'd5; end
                3'd5: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [15:0] a_reg,b_reg; reg [7:0] op_reg; reg comp_trigger;
    wire [15:0] fmt_a=a_reg, fmt_b=b_reg;
    wire [15:0] pos_val_a = fmt_a;
    wire pos_zero_a = (pos_val_a==16'h0000);
    wire pos_nar_a = (pos_val_a==16'h8000);
    wire pos_sign_a = pos_val_a[15];
    wire [14:0] pos_abs_a = pos_sign_a ? (~pos_val_a[14:0]+15'd1) : pos_val_a[14:0];
    wire pos_rs_a = pos_abs_a[14];
    wire [14:0] pos_rb_a = pos_rs_a ? ~pos_abs_a : pos_abs_a;
    reg [3:0] pos_lzc_a;
    always @(*) begin
        casez(pos_rb_a)
            15'b1??????????????: pos_lzc_a=4'd0;
            15'b01?????????????: pos_lzc_a=4'd1;
            15'b001????????????: pos_lzc_a=4'd2;
            15'b0001???????????: pos_lzc_a=4'd3;
            15'b00001??????????: pos_lzc_a=4'd4;
            15'b000001?????????: pos_lzc_a=4'd5;
            15'b0000001????????: pos_lzc_a=4'd6;
            15'b00000001???????: pos_lzc_a=4'd7;
            15'b000000001??????: pos_lzc_a=4'd8;
            15'b0000000001?????: pos_lzc_a=4'd9;
            15'b00000000001????: pos_lzc_a=4'd10;
            15'b000000000001???: pos_lzc_a=4'd11;
            15'b0000000000001??: pos_lzc_a=4'd12;
            15'b00000000000001?: pos_lzc_a=4'd13;
            default: pos_lzc_a=4'd14;
        endcase
    end
    wire signed [4:0] pos_k_a = pos_rs_a ? $signed({1'b0,pos_lzc_a})-5'sd1 : -$signed({1'b0,pos_lzc_a});
    wire [3:0] pos_rt_a = (pos_lzc_a<4'd14) ? pos_lzc_a+4'd1 : pos_lzc_a;
    wire [14:0] pos_shifted_a = pos_abs_a << pos_rt_a;
    wire [1:0] pos_es_a = pos_shifted_a[14:13];
    wire [12:0] pos_frac_a = pos_shifted_a[12:0];
    wire signed [6:0] pos_exp2_a = {{2{pos_k_a[4]}},pos_k_a} + {5'd0,pos_es_a};
    wire [8:0] pos_fp32_exp_a = {1'b0,8'd127} + {{1{pos_exp2_a[6]}},pos_exp2_a};
    reg [31:0] fp32_a;
    always @(*) begin
        if(pos_zero_a) fp32_a={pos_sign_a, 31'b0};
        else if(pos_nar_a) fp32_a=32'h7FC00000;
        else fp32_a={pos_sign_a,pos_fp32_exp_a[7:0],pos_frac_a,10'b0};
    end
    wire [15:0] pos_val_b = fmt_b;
    wire pos_zero_b = (pos_val_b==16'h0000);
    wire pos_nar_b = (pos_val_b==16'h8000);
    wire pos_sign_b = pos_val_b[15];
    wire [14:0] pos_abs_b = pos_sign_b ? (~pos_val_b[14:0]+15'd1) : pos_val_b[14:0];
    wire pos_rs_b = pos_abs_b[14];
    wire [14:0] pos_rb_b = pos_rs_b ? ~pos_abs_b : pos_abs_b;
    reg [3:0] pos_lzc_b;
    always @(*) begin
        casez(pos_rb_b)
            15'b1??????????????: pos_lzc_b=4'd0;
            15'b01?????????????: pos_lzc_b=4'd1;
            15'b001????????????: pos_lzc_b=4'd2;
            15'b0001???????????: pos_lzc_b=4'd3;
            15'b00001??????????: pos_lzc_b=4'd4;
            15'b000001?????????: pos_lzc_b=4'd5;
            15'b0000001????????: pos_lzc_b=4'd6;
            15'b00000001???????: pos_lzc_b=4'd7;
            15'b000000001??????: pos_lzc_b=4'd8;
            15'b0000000001?????: pos_lzc_b=4'd9;
            15'b00000000001????: pos_lzc_b=4'd10;
            15'b000000000001???: pos_lzc_b=4'd11;
            15'b0000000000001??: pos_lzc_b=4'd12;
            15'b00000000000001?: pos_lzc_b=4'd13;
            default: pos_lzc_b=4'd14;
        endcase
    end
    wire signed [4:0] pos_k_b = pos_rs_b ? $signed({1'b0,pos_lzc_b})-5'sd1 : -$signed({1'b0,pos_lzc_b});
    wire [3:0] pos_rt_b = (pos_lzc_b<4'd14) ? pos_lzc_b+4'd1 : pos_lzc_b;
    wire [14:0] pos_shifted_b = pos_abs_b << pos_rt_b;
    wire [1:0] pos_es_b = pos_shifted_b[14:13];
    wire [12:0] pos_frac_b = pos_shifted_b[12:0];
    wire signed [6:0] pos_exp2_b = {{2{pos_k_b[4]}},pos_k_b} + {5'd0,pos_es_b};
    wire [8:0] pos_fp32_exp_b = {1'b0,8'd127} + {{1{pos_exp2_b[6]}},pos_exp2_b};
    reg [31:0] fp32_b;
    always @(*) begin
        if(pos_zero_b) fp32_b={pos_sign_b, 31'b0};
        else if(pos_nar_b) fp32_b=32'h7FC00000;
        else fp32_b={pos_sign_b,pos_fp32_exp_b[7:0],pos_frac_b,10'b0};
    end
    wire comp_irdy, comp_ovld; wire [31:0] comp_result;
    gf_adder_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1)) u_comp (
        .clk(mclk),.rst(rst),.in_valid(comp_trigger),.in_a(fp32_a),.in_b(fp32_b),
        .in_ready(comp_irdy),.out_valid(comp_ovld),.out_y(comp_result),.out_ready(1'b1));
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;b_reg<=0;op_reg<=0;comp_trigger<=0; end
        else begin comp_trigger<=frame_valid;
            if(frame_valid) begin a_reg<=a_r;b_reg<=b_r; end
        end
    end
    wire [31:0] q_in=comp_result;
    wire q_sign=q_in[31]; wire [7:0] q_exp=q_in[30:23]; wire [22:0] q_mant=q_in[22:0];
    wire q_nan=(q_in==32'h7FC00000); wire q_zero=(q_in==32'h00000000);
    wire signed [8:0] q_k2 = $signed({1'b0,q_exp}) - 9'sd127;
    // es=2, so useed=16. regime k = q_k2 >> 2
    wire signed [4:0] q_k = q_k2[8:4] + (|q_k2[3:2] ? 5'sd1 : 5'sd0);
    wire [1:0] q_es = q_k2[3:2];
    reg [14:0] q_abspos;
    always @(*) begin
        if(q_nan) q_result=16'h8000;
        else if(q_zero) q_result=16'h0000;
        else if(q_k >= 5'sd13) q_abspos=15'h7FFF;
        else if(q_k <= -5'sd13) q_abspos=15'h0001;
        else if(q_k[4]) begin
            // Negative k
            case(-q_k[3:0])
                4'd1: q_abspos={3'b001,q_es,q_mant[22:12]};
                4'd2: q_abspos={4'b0001,q_es,q_mant[22:13]};
                4'd3: q_abspos={5'b00001,q_es,q_mant[22:14]};
                4'd4: q_abspos={6'b000001,q_es,q_mant[22:15]};
                4'd5: q_abspos={7'b0000001,q_es,q_mant[22:16]};
                4'd6: q_abspos={8'b00000001,q_es,q_mant[22:17]};
                4'd7: q_abspos={9'b000000001,q_es,q_mant[22:18]};
                default: q_abspos=15'b000000000000001;
            endcase
        end else begin
            // Positive k: (k+1) ones, then 0, then es, then frac
            case(q_k[3:0])
                4'd0: q_abspos={1'b0,q_es,q_mant[22:11]};
                4'd1: q_abspos={3'b110,q_es,q_mant[22:12]};
                4'd2: q_abspos={4'b1110,q_es,q_mant[22:13]};
                4'd3: q_abspos={5'b11110,q_es,q_mant[22:14]};
                4'd4: q_abspos={6'b111110,q_es,q_mant[22:15]};
                4'd5: q_abspos={7'b1111110,q_es,q_mant[22:16]};
                default: q_abspos=15'h7FFF;
            endcase
        end
        if(q_sign) q_result={1'b1,~(q_abspos-15'd1)+15'd1};
        else q_result={1'b0,q_abspos};
    end
    reg [15:0] q_result;
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
