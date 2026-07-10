`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_fp32_to_posit64_ax7203 — POSIT64 FP32_TO on AX7203.
module corona_compute_fp32_to_posit64_ax7203 (
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

    reg [2:0] frm; reg [7:0] fmt_r; reg [31:0] a_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3'd3; end
                3'd3: begin a_r[7:0]<=rx_byte;frm<=3'd4; end
                3'd4: begin a_r[15:8]<=rx_byte;frm<=3'd5; end
                3'd5: begin a_r[23:16]<=rx_byte;frm<=3'd6; end
                3'd6: begin a_r[31:24]<=rx_byte;frm<=0; frame_valid<=1; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [31:0] a_reg; reg conv_trigger;
    wire [31:0] q_in = a_reg;
    wire q_sign=q_in[31]; wire [7:0] q_exp=q_in[30:23]; wire [22:0] q_mant=q_in[22:0];
    wire q_nan=(q_in==32'h7FC00000); wire q_zero=(q_in==32'h00000000);
    wire signed [8:0] q_k2 = $signed({1'b0,q_exp}) - 9'sd127;
    wire signed [6:0] q_k = q_k2[8:2] + (|q_k2[1:0] ? 7'sd1 : 7'sd0);
    wire [1:0] q_es = q_k2[1:0];
    reg [62:0] q_abspos;
    reg [63:0] q_result;
    always @(*) begin
        if(q_nan) q_result=64'h8000000000000000;
        else if(q_zero) q_result=64'h0;
        else if(q_k >= 7'sd50) q_abspos=63'h7FFFFFFFFFFFFFFF;
        else if(q_k <= -7'sd50) q_abspos=63'h1;
        else if(q_k[6]) begin
            case(-q_k[5:0])
                6'd1: q_abspos={3'b001,q_es,q_mant,38'b0};
                6'd2: q_abspos={4'b0001,q_es,q_mant,37'b0};
                6'd3: q_abspos={5'b00001,q_es,q_mant,36'b0};
                6'd4: q_abspos={6'b000001,q_es,q_mant,35'b0};
                6'd5: q_abspos={7'b0000001,q_es,q_mant,34'b0};
                6'd6: q_abspos={8'b00000001,q_es,q_mant,33'b0};
                6'd7: q_abspos={9'b000000001,q_es,q_mant,32'b0};
                6'd8: q_abspos={10'b0000000001,q_es,q_mant,31'b0};
                6'd9: q_abspos={11'b00000000001,q_es,q_mant,30'b0};
                6'd10: q_abspos={12'b000000000001,q_es,q_mant,29'b0};
                6'd11: q_abspos={13'b0000000000001,q_es,q_mant,28'b0};
                6'd12: q_abspos={14'b00000000000001,q_es,q_mant,27'b0};
                6'd13: q_abspos={15'b000000000000001,q_es,q_mant,26'b0};
                6'd14: q_abspos={16'b0000000000000001,q_es,q_mant,25'b0};
                6'd15: q_abspos={17'b00000000000000001,q_es,q_mant,24'b0};
                6'd16: q_abspos={18'b000000000000000001,q_es,q_mant,23'b0};
                6'd17: q_abspos={19'b0000000000000000001,q_es,q_mant,22'b0};
                6'd18: q_abspos={20'b00000000000000000001,q_es,q_mant,21'b0};
                6'd19: q_abspos={21'b000000000000000000001,q_es,q_mant,20'b0};
                6'd20: q_abspos={22'b0000000000000000000001,q_es,q_mant,19'b0};
                6'd21: q_abspos={23'b00000000000000000000001,q_es,q_mant,18'b0};
                6'd22: q_abspos={24'b000000000000000000000001,q_es,q_mant,17'b0};
                6'd23: q_abspos={25'b0000000000000000000000001,q_es,q_mant,16'b0};
                6'd24: q_abspos={26'b00000000000000000000000001,q_es,q_mant,15'b0};
                6'd25: q_abspos={27'b000000000000000000000000001,q_es,q_mant,14'b0};
                6'd26: q_abspos={28'b0000000000000000000000000001,q_es,q_mant,13'b0};
                6'd27: q_abspos={29'b00000000000000000000000000001,q_es,q_mant,12'b0};
                6'd28: q_abspos={30'b000000000000000000000000000001,q_es,q_mant,11'b0};
                6'd29: q_abspos={31'b0000000000000000000000000000001,q_es,q_mant,10'b0};
                6'd30: q_abspos={32'b00000000000000000000000000000001,q_es,q_mant,9'b0};
                6'd31: q_abspos={33'b000000000000000000000000000000001,q_es,q_mant,8'b0};
                6'd32: q_abspos={34'b0000000000000000000000000000000001,q_es,q_mant,7'b0};
                6'd33: q_abspos={35'b00000000000000000000000000000000001,q_es,q_mant,6'b0};
                6'd34: q_abspos={36'b000000000000000000000000000000000001,q_es,q_mant,5'b0};
                6'd35: q_abspos={37'b0000000000000000000000000000000000001,q_es,q_mant,4'b0};
                6'd36: q_abspos={38'b00000000000000000000000000000000000001,q_es,q_mant,3'b0};
                6'd37: q_abspos={39'b000000000000000000000000000000000000001,q_es,q_mant,2'b0};
                6'd38: q_abspos={40'b0000000000000000000000000000000000000001,q_es,q_mant,1'b0};
                6'd39: q_abspos={41'b00000000000000000000000000000000000000001,q_es,q_mant};
                6'd40: q_abspos={42'b000000000000000000000000000000000000000001,q_es,q_mant[22:1]};
                6'd41: q_abspos={43'b0000000000000000000000000000000000000000001,q_es,q_mant[22:2]};
                6'd42: q_abspos={44'b00000000000000000000000000000000000000000001,q_es,q_mant[22:3]};
                6'd43: q_abspos={45'b000000000000000000000000000000000000000000001,q_es,q_mant[22:4]};
                6'd44: q_abspos={46'b0000000000000000000000000000000000000000000001,q_es,q_mant[22:5]};
                6'd45: q_abspos={47'b00000000000000000000000000000000000000000000001,q_es,q_mant[22:6]};
                6'd46: q_abspos={48'b000000000000000000000000000000000000000000000001,q_es,q_mant[22:7]};
                6'd47: q_abspos={49'b0000000000000000000000000000000000000000000000001,q_es,q_mant[22:8]};
                6'd48: q_abspos={50'b00000000000000000000000000000000000000000000000001,q_es,q_mant[22:9]};
                6'd49: q_abspos={51'b000000000000000000000000000000000000000000000000001,q_es,q_mant[22:10]};
                default: q_abspos=63'h1;
            endcase
        end else begin
            case(q_k[5:0])
                6'd0: q_abspos={1'b0,q_es,q_mant,38'b0};
                6'd1: q_abspos={3'b110,q_es,q_mant,37'b0};
                6'd2: q_abspos={4'b1110,q_es,q_mant,36'b0};
                6'd3: q_abspos={5'b11110,q_es,q_mant,35'b0};
                6'd4: q_abspos={6'b111110,q_es,q_mant,34'b0};
                6'd5: q_abspos={7'b1111110,q_es,q_mant,33'b0};
                6'd6: q_abspos={8'b11111110,q_es,q_mant,32'b0};
                6'd7: q_abspos={9'b111111110,q_es,q_mant,31'b0};
                6'd8: q_abspos={10'b1111111110,q_es,q_mant,30'b0};
                6'd9: q_abspos={11'b11111111110,q_es,q_mant,29'b0};
                6'd10: q_abspos={12'b111111111110,q_es,q_mant,28'b0};
                6'd11: q_abspos={13'b1111111111110,q_es,q_mant,27'b0};
                6'd12: q_abspos={14'b11111111111110,q_es,q_mant,26'b0};
                6'd13: q_abspos={15'b111111111111110,q_es,q_mant,25'b0};
                default: q_abspos=63'h7FFFFFFFFFFFFFFF;
            endcase
        end
        if(q_sign) q_result={1'b1,~(q_abspos-63'd1)+63'd1};
        else q_result={1'b0,q_abspos};
    end
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;conv_trigger<=0; end
        else begin conv_trigger<=frame_valid;
            if(frame_valid) a_reg<=a_r;
        end
    end
    reg [63:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=conv_trigger;
            if(conv_trigger) result_reg<=q_result;
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
