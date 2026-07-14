`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_fp32_to_posit128_ax7203 — POSIT128 FP32_TO on AX7203.
module corona_compute_fp32_to_posit128_ax7203 (
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
    wire signed [9:0] q_k2 = $signed({1'b0,q_exp}) - 10'sd127;
    wire signed [7:0] q_k = q_k2[9:4] + (|q_k2[3:0] ? 8'sd1 : 8'sd0);
    wire [3:0] q_es = q_k2[3:0];
    reg [126:0] q_abspos;
    reg [127:0] q_result;
    always @(*) begin
        if(q_nan) q_result=128'h80000000000000000000000000000000;
        else if(q_zero) q_result=128'h0;
        else if(q_k >= 8'sd120) q_abspos=127'h7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF;
        else if(q_k <= -8'sd120) q_abspos=127'h1;
        else if(q_k[7]) begin
            case(-q_k[6:0])
                7'd1: q_abspos={5'b00001,q_es,q_mant,95'b0};
                7'd2: q_abspos={6'b000001,q_es,q_mant,94'b0};
                7'd3: q_abspos={7'b0000001,q_es,q_mant,93'b0};
                7'd4: q_abspos={8'b00000001,q_es,q_mant,92'b0};
                7'd5: q_abspos={9'b000000001,q_es,q_mant,91'b0};
                7'd6: q_abspos={10'b0000000001,q_es,q_mant,90'b0};
                7'd7: q_abspos={11'b00000000001,q_es,q_mant,89'b0};
                7'd8: q_abspos={12'b000000000001,q_es,q_mant,88'b0};
                7'd9: q_abspos={13'b0000000000001,q_es,q_mant,87'b0};
                7'd10: q_abspos={14'b00000000000001,q_es,q_mant,86'b0};
                7'd11: q_abspos={15'b000000000000001,q_es,q_mant,85'b0};
                7'd12: q_abspos={16'b0000000000000001,q_es,q_mant,84'b0};
                7'd13: q_abspos={17'b00000000000000001,q_es,q_mant,83'b0};
                7'd14: q_abspos={18'b000000000000000001,q_es,q_mant,82'b0};
                7'd15: q_abspos={19'b0000000000000000001,q_es,q_mant,81'b0};
                7'd16: q_abspos={20'b00000000000000000001,q_es,q_mant,80'b0};
                7'd17: q_abspos={21'b000000000000000000001,q_es,q_mant,79'b0};
                7'd18: q_abspos={22'b0000000000000000000001,q_es,q_mant,78'b0};
                7'd19: q_abspos={23'b00000000000000000000001,q_es,q_mant,77'b0};
                7'd20: q_abspos={24'b000000000000000000000001,q_es,q_mant,76'b0};
                7'd21: q_abspos={25'b0000000000000000000000001,q_es,q_mant,75'b0};
                7'd22: q_abspos={26'b00000000000000000000000001,q_es,q_mant,74'b0};
                7'd23: q_abspos={27'b000000000000000000000000001,q_es,q_mant,73'b0};
                7'd24: q_abspos={28'b0000000000000000000000000001,q_es,q_mant,72'b0};
                7'd25: q_abspos={29'b00000000000000000000000000001,q_es,q_mant,71'b0};
                7'd26: q_abspos={30'b000000000000000000000000000001,q_es,q_mant,70'b0};
                7'd27: q_abspos={31'b0000000000000000000000000000001,q_es,q_mant,69'b0};
                7'd28: q_abspos={32'b00000000000000000000000000000001,q_es,q_mant,68'b0};
                7'd29: q_abspos={33'b000000000000000000000000000000001,q_es,q_mant,67'b0};
                7'd30: q_abspos={34'b0000000000000000000000000000000001,q_es,q_mant,66'b0};
                7'd31: q_abspos={35'b00000000000000000000000000000000001,q_es,q_mant,65'b0};
                7'd32: q_abspos={36'b000000000000000000000000000000000001,q_es,q_mant,64'b0};
                7'd33: q_abspos={37'b0000000000000000000000000000000000001,q_es,q_mant,63'b0};
                7'd34: q_abspos={38'b00000000000000000000000000000000000001,q_es,q_mant,62'b0};
                7'd35: q_abspos={39'b000000000000000000000000000000000000001,q_es,q_mant,61'b0};
                7'd36: q_abspos={40'b0000000000000000000000000000000000000001,q_es,q_mant,60'b0};
                7'd37: q_abspos={41'b00000000000000000000000000000000000000001,q_es,q_mant,59'b0};
                7'd38: q_abspos={42'b000000000000000000000000000000000000000001,q_es,q_mant,58'b0};
                7'd39: q_abspos={43'b0000000000000000000000000000000000000000001,q_es,q_mant,57'b0};
                7'd40: q_abspos={44'b00000000000000000000000000000000000000000001,q_es,q_mant,56'b0};
                7'd41: q_abspos={45'b000000000000000000000000000000000000000000001,q_es,q_mant,55'b0};
                7'd42: q_abspos={46'b0000000000000000000000000000000000000000000001,q_es,q_mant,54'b0};
                7'd43: q_abspos={47'b00000000000000000000000000000000000000000000001,q_es,q_mant,53'b0};
                7'd44: q_abspos={48'b000000000000000000000000000000000000000000000001,q_es,q_mant,52'b0};
                7'd45: q_abspos={49'b0000000000000000000000000000000000000000000000001,q_es,q_mant,51'b0};
                7'd46: q_abspos={50'b00000000000000000000000000000000000000000000000001,q_es,q_mant,50'b0};
                7'd47: q_abspos={51'b000000000000000000000000000000000000000000000000001,q_es,q_mant,49'b0};
                7'd48: q_abspos={52'b0000000000000000000000000000000000000000000000000001,q_es,q_mant,48'b0};
                7'd49: q_abspos={53'b00000000000000000000000000000000000000000000000000001,q_es,q_mant,47'b0};
                7'd50: q_abspos={54'b000000000000000000000000000000000000000000000000000001,q_es,q_mant,46'b0};
                7'd51: q_abspos={55'b0000000000000000000000000000000000000000000000000000001,q_es,q_mant,45'b0};
                7'd52: q_abspos={56'b00000000000000000000000000000000000000000000000000000001,q_es,q_mant,44'b0};
                7'd53: q_abspos={57'b000000000000000000000000000000000000000000000000000000001,q_es,q_mant,43'b0};
                7'd54: q_abspos={58'b0000000000000000000000000000000000000000000000000000000001,q_es,q_mant,42'b0};
                7'd55: q_abspos={59'b00000000000000000000000000000000000000000000000000000000001,q_es,q_mant,41'b0};
                7'd56: q_abspos={60'b000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,40'b0};
                7'd57: q_abspos={61'b0000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,39'b0};
                7'd58: q_abspos={62'b00000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,38'b0};
                7'd59: q_abspos={63'b000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,37'b0};
                7'd60: q_abspos={64'b0000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,36'b0};
                7'd61: q_abspos={65'b00000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,35'b0};
                7'd62: q_abspos={66'b000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,34'b0};
                7'd63: q_abspos={67'b0000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,33'b0};
                7'd64: q_abspos={68'b00000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,32'b0};
                7'd65: q_abspos={69'b000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,31'b0};
                7'd66: q_abspos={70'b0000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,30'b0};
                7'd67: q_abspos={71'b00000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,29'b0};
                7'd68: q_abspos={72'b000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,28'b0};
                7'd69: q_abspos={73'b0000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,27'b0};
                7'd70: q_abspos={74'b00000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,26'b0};
                7'd71: q_abspos={75'b000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,25'b0};
                7'd72: q_abspos={76'b0000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,24'b0};
                7'd73: q_abspos={77'b00000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,23'b0};
                7'd74: q_abspos={78'b000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,22'b0};
                7'd75: q_abspos={79'b0000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,21'b0};
                7'd76: q_abspos={80'b00000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,20'b0};
                7'd77: q_abspos={81'b000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,19'b0};
                7'd78: q_abspos={82'b0000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,18'b0};
                7'd79: q_abspos={83'b00000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,17'b0};
                7'd80: q_abspos={84'b000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,16'b0};
                7'd81: q_abspos={85'b0000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,15'b0};
                7'd82: q_abspos={86'b00000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,14'b0};
                7'd83: q_abspos={87'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,13'b0};
                7'd84: q_abspos={88'b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,12'b0};
                7'd85: q_abspos={89'b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,11'b0};
                7'd86: q_abspos={90'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,10'b0};
                7'd87: q_abspos={91'b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,9'b0};
                7'd88: q_abspos={92'b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,8'b0};
                7'd89: q_abspos={93'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,7'b0};
                7'd90: q_abspos={94'b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,6'b0};
                7'd91: q_abspos={95'b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,5'b0};
                7'd92: q_abspos={96'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,4'b0};
                7'd93: q_abspos={97'b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,3'b0};
                7'd94: q_abspos={98'b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,2'b0};
                7'd95: q_abspos={99'b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant,1'b0};
                7'd96: q_abspos={100'b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001,q_es,q_mant};
                default: q_abspos=127'h1;
            endcase
        end else begin
            case(q_k[6:0])
                7'd0: q_abspos={1'b0,q_es,q_mant,100'b0};
                7'd1: q_abspos={3'b110,q_es,q_mant,99'b0};
                7'd2: q_abspos={4'b1110,q_es,q_mant,98'b0};
                7'd3: q_abspos={5'b11110,q_es,q_mant,97'b0};
                7'd4: q_abspos={6'b111110,q_es,q_mant,96'b0};
                7'd5: q_abspos={7'b1111110,q_es,q_mant,95'b0};
                7'd6: q_abspos={8'b11111110,q_es,q_mant,94'b0};
                7'd7: q_abspos={9'b111111110,q_es,q_mant,93'b0};
                7'd8: q_abspos={10'b1111111110,q_es,q_mant,92'b0};
                7'd9: q_abspos={11'b11111111110,q_es,q_mant,91'b0};
                7'd10: q_abspos={12'b111111111110,q_es,q_mant,90'b0};
                7'd11: q_abspos={13'b1111111111110,q_es,q_mant,89'b0};
                7'd12: q_abspos={14'b11111111111110,q_es,q_mant,88'b0};
                7'd13: q_abspos={15'b111111111111110,q_es,q_mant,87'b0};
                7'd14: q_abspos={16'b1111111111111110,q_es,q_mant,86'b0};
                7'd15: q_abspos={17'b11111111111111110,q_es,q_mant,85'b0};
                7'd16: q_abspos={18'b111111111111111110,q_es,q_mant,84'b0};
                7'd17: q_abspos={19'b1111111111111111110,q_es,q_mant,83'b0};
                7'd18: q_abspos={20'b11111111111111111110,q_es,q_mant,82'b0};
                7'd19: q_abspos={21'b111111111111111111110,q_es,q_mant,81'b0};
                7'd20: q_abspos={22'b1111111111111111111110,q_es,q_mant,80'b0};
                7'd21: q_abspos={23'b11111111111111111111110,q_es,q_mant,79'b0};
                7'd22: q_abspos={24'b111111111111111111111110,q_es,q_mant,78'b0};
                7'd23: q_abspos={25'b1111111111111111111111110,q_es,q_mant,77'b0};
                7'd24: q_abspos={26'b11111111111111111111111110,q_es,q_mant,76'b0};
                7'd25: q_abspos={27'b111111111111111111111111110,q_es,q_mant,75'b0};
                7'd26: q_abspos={28'b1111111111111111111111111110,q_es,q_mant,74'b0};
                7'd27: q_abspos={29'b11111111111111111111111111110,q_es,q_mant,73'b0};
                7'd28: q_abspos={30'b111111111111111111111111111110,q_es,q_mant,72'b0};
                7'd29: q_abspos={31'b1111111111111111111111111111110,q_es,q_mant,71'b0};
                7'd30: q_abspos={32'b11111111111111111111111111111110,q_es,q_mant,70'b0};
                7'd31: q_abspos={33'b111111111111111111111111111111110,q_es,q_mant,69'b0};
                7'd32: q_abspos={34'b1111111111111111111111111111111110,q_es,q_mant,68'b0};
                7'd33: q_abspos={35'b11111111111111111111111111111111110,q_es,q_mant,67'b0};
                7'd34: q_abspos={36'b111111111111111111111111111111111110,q_es,q_mant,66'b0};
                7'd35: q_abspos={37'b1111111111111111111111111111111111110,q_es,q_mant,65'b0};
                7'd36: q_abspos={38'b11111111111111111111111111111111111110,q_es,q_mant,64'b0};
                7'd37: q_abspos={39'b111111111111111111111111111111111111110,q_es,q_mant,63'b0};
                7'd38: q_abspos={40'b1111111111111111111111111111111111111110,q_es,q_mant,62'b0};
                7'd39: q_abspos={41'b11111111111111111111111111111111111111110,q_es,q_mant,61'b0};
                7'd40: q_abspos={42'b111111111111111111111111111111111111111110,q_es,q_mant,60'b0};
                7'd41: q_abspos={43'b1111111111111111111111111111111111111111110,q_es,q_mant,59'b0};
                7'd42: q_abspos={44'b11111111111111111111111111111111111111111110,q_es,q_mant,58'b0};
                7'd43: q_abspos={45'b111111111111111111111111111111111111111111110,q_es,q_mant,57'b0};
                7'd44: q_abspos={46'b1111111111111111111111111111111111111111111110,q_es,q_mant,56'b0};
                7'd45: q_abspos={47'b11111111111111111111111111111111111111111111110,q_es,q_mant,55'b0};
                7'd46: q_abspos={48'b111111111111111111111111111111111111111111111110,q_es,q_mant,54'b0};
                7'd47: q_abspos={49'b1111111111111111111111111111111111111111111111110,q_es,q_mant,53'b0};
                7'd48: q_abspos={50'b11111111111111111111111111111111111111111111111110,q_es,q_mant,52'b0};
                7'd49: q_abspos={51'b111111111111111111111111111111111111111111111111110,q_es,q_mant,51'b0};
                7'd50: q_abspos={52'b1111111111111111111111111111111111111111111111111110,q_es,q_mant,50'b0};
                7'd51: q_abspos={53'b11111111111111111111111111111111111111111111111111110,q_es,q_mant,49'b0};
                7'd52: q_abspos={54'b111111111111111111111111111111111111111111111111111110,q_es,q_mant,48'b0};
                7'd53: q_abspos={55'b1111111111111111111111111111111111111111111111111111110,q_es,q_mant,47'b0};
                7'd54: q_abspos={56'b11111111111111111111111111111111111111111111111111111110,q_es,q_mant,46'b0};
                7'd55: q_abspos={57'b111111111111111111111111111111111111111111111111111111110,q_es,q_mant,45'b0};
                7'd56: q_abspos={58'b1111111111111111111111111111111111111111111111111111111110,q_es,q_mant,44'b0};
                7'd57: q_abspos={59'b11111111111111111111111111111111111111111111111111111111110,q_es,q_mant,43'b0};
                7'd58: q_abspos={60'b111111111111111111111111111111111111111111111111111111111110,q_es,q_mant,42'b0};
                7'd59: q_abspos={61'b1111111111111111111111111111111111111111111111111111111111110,q_es,q_mant,41'b0};
                7'd60: q_abspos={62'b11111111111111111111111111111111111111111111111111111111111110,q_es,q_mant,40'b0};
                7'd61: q_abspos={63'b111111111111111111111111111111111111111111111111111111111111110,q_es,q_mant,39'b0};
                7'd62: q_abspos={64'b1111111111111111111111111111111111111111111111111111111111111110,q_es,q_mant,38'b0};
                7'd63: q_abspos={65'b11111111111111111111111111111111111111111111111111111111111111110,q_es,q_mant,37'b0};
                default: q_abspos=127'h7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF;
            endcase
        end
        if(q_sign) q_result={1'b1,~(q_abspos-127'd1)+127'd1};
        else q_result={1'b0,q_abspos};
    end
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;conv_trigger<=0; end
        else begin conv_trigger<=frame_valid;
            if(frame_valid) a_reg<=a_r;
        end
    end
    reg [127:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=conv_trigger;
            if(conv_trigger) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [3:0] TX_LEN = 17;
    // TX: buffer+mux (no conflicting NBA — fixes tx race). 17 bytes sliced from tx_load[135:0].
    wire [135:0] tx_load = {result_reg, 8'hA5};
    reg responding; reg [4:0] tx_idx; reg [7:0] tx_buf0, tx_buf1, tx_buf2, tx_buf3, tx_buf4, tx_buf5, tx_buf6, tx_buf7, tx_buf8, tx_buf9, tx_buf10, tx_buf11, tx_buf12, tx_buf13, tx_buf14, tx_buf15, tx_buf16;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF; tx_buf1<=8'hFF; tx_buf2<=8'hFF; tx_buf3<=8'hFF; tx_buf4<=8'hFF; tx_buf5<=8'hFF; tx_buf6<=8'hFF; tx_buf7<=8'hFF; tx_buf8<=8'hFF; tx_buf9<=8'hFF; tx_buf10<=8'hFF; tx_buf11<=8'hFF; tx_buf12<=8'hFF; tx_buf13<=8'hFF; tx_buf14<=8'hFF; tx_buf15<=8'hFF; tx_buf16<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=tx_load[7:0]; tx_buf1<=tx_load[15:8]; tx_buf2<=tx_load[23:16]; tx_buf3<=tx_load[31:24]; tx_buf4<=tx_load[39:32]; tx_buf5<=tx_load[47:40]; tx_buf6<=tx_load[55:48]; tx_buf7<=tx_load[63:56]; tx_buf8<=tx_load[71:64]; tx_buf9<=tx_load[79:72]; tx_buf10<=tx_load[87:80]; tx_buf11<=tx_load[95:88]; tx_buf12<=tx_load[103:96]; tx_buf13<=tx_load[111:104]; tx_buf14<=tx_load[119:112]; tx_buf15<=tx_load[127:120]; tx_buf16<=tx_load[135:128]; responding<=1; tx_idx<=0;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        case(tx_idx)
                            5'd0: tsr<={1'b1,tx_buf0,1'b0};
                            5'd1: tsr<={1'b1,tx_buf1,1'b0};
                            5'd2: tsr<={1'b1,tx_buf2,1'b0};
                            5'd3: tsr<={1'b1,tx_buf3,1'b0};
                            5'd4: tsr<={1'b1,tx_buf4,1'b0};
                            5'd5: tsr<={1'b1,tx_buf5,1'b0};
                            5'd6: tsr<={1'b1,tx_buf6,1'b0};
                            5'd7: tsr<={1'b1,tx_buf7,1'b0};
                            5'd8: tsr<={1'b1,tx_buf8,1'b0};
                            5'd9: tsr<={1'b1,tx_buf9,1'b0};
                            5'd10: tsr<={1'b1,tx_buf10,1'b0};
                            5'd11: tsr<={1'b1,tx_buf11,1'b0};
                            5'd12: tsr<={1'b1,tx_buf12,1'b0};
                            5'd13: tsr<={1'b1,tx_buf13,1'b0};
                            5'd14: tsr<={1'b1,tx_buf14,1'b0};
                            5'd15: tsr<={1'b1,tx_buf15,1'b0};
                            5'd16: tsr<={1'b1,tx_buf16,1'b0};
                        endcase
                        if(tx_idx==16) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
    endmodule
`default_nettype wire
