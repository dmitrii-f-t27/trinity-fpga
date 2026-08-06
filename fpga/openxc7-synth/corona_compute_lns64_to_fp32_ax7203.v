`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_lns64_to_fp32_ax7203 — LNS64 TO_FP32 on AX7203.
module corona_compute_lns64_to_fp32_ax7203 (
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

    reg [3:0] frm; reg [7:0] fmt_r; reg [63:0] a_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                4'd0: frm<=(rx_byte==8'hAA)?4'd1:4'd0;
                4'd1: frm<=(rx_byte==8'h55)?4'd2:4'd0;
                4'd2: begin fmt_r<=rx_byte;frm<=4'd3; end
                4'd3: begin a_r[7:0]<=rx_byte;frm<=4'd4; end
                4'd4: begin a_r[15:8]<=rx_byte;frm<=4'd5; end
                4'd5: begin a_r[23:16]<=rx_byte;frm<=4'd6; end
                4'd6: begin a_r[31:24]<=rx_byte;frm<=4'd7; end
                4'd7: begin a_r[39:32]<=rx_byte;frm<=4'd8; end
                4'd8: begin a_r[47:40]<=rx_byte;frm<=4'd9; end
                4'd9: begin a_r[55:48]<=rx_byte;frm<=4'd10; end
                4'd10: begin a_r[63:56]<=rx_byte;frm<=4'd11; end
                4'd11: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [63:0] a_reg; reg conv_trigger;
    wire [63:0] fmt_a = a_reg;
    wire l64_sign_a = fmt_a[63];
    wire [62:0] l64_log_a = fmt_a[62:0];
    wire l64_zero_a = (fmt_a == 64'd0);
    wire signed [62:0] l64_slog_a = $signed(l64_log_a);
    wire signed [23:0] l64_int_a = l64_slog_a >>> 7;
    wire [6:0] l64_frac_a = l64_log_a[6:0];
    reg [22:0] l64_fm_a;
    always @(*) begin
        case(l64_frac_a)
            7'd0: l64_fm_a=23'h000000; 7'd1: l64_fm_a=23'h00b1ed;
            7'd2: l64_fm_a=23'h0164d2; 7'd3: l64_fm_a=23'h0218af;
            7'd4: l64_fm_a=23'h02cd87; 7'd5: l64_fm_a=23'h038359;
            7'd6: l64_fm_a=23'h043a4c; 7'd7: l64_fm_a=23'h04f20f;
            7'd8: l64_fm_a=23'h05aab4; 7'd9: l64_fm_a=23'h066456;
            7'd10: l64_fm_a=23'h071f5a; 7'd11: l64_fm_a=23'h07db45;
            7'd12: l64_fm_a=23'h089838; 7'd13: l64_fm_a=23'h095636;
            7'd14: l64_fm_a=23'h0a154a; 7'd15: l64_fm_a=23'h0ad576;
            7'd16: l64_fm_a=23'h0b96c1; 7'd17: l64_fm_a=23'h0c5931;
            7'd18: l64_fm_a=23'h0d1cdf; 7'd19: l64_fm_a=23'h0de1c4;
            7'd20: l64_fm_a=23'h0ea7f0; 7'd21: l64_fm_a=23'h0f6f70;
            7'd22: l64_fm_a=23'h103845; 7'd23: l64_fm_a=23'h11027f;
            7'd24: l64_fm_a=23'h11ce26; 7'd25: l64_fm_a=23'h129b3f;
            7'd26: l64_fm_a=23'h1369d3; 7'd27: l64_fm_a=23'h1439e6;
            7'd28: l64_fm_a=23'h150b7d; 7'd29: l64_fm_a=23'h15dea6;
            7'd30: l64_fm_a=23'h16b362; 7'd31: l64_fm_a=23'h1789c0;
            7'd32: l64_fm_a=23'h1861c3; 7'd33: l64_fm_a=23'h193b73;
            7'd34: l64_fm_a=23'h1a16d5; 7'd35: l64_fm_a=23'h1af3ea;
            7'd36: l64_fm_a=23'h1bd2b9; 7'd37: l64_fm_a=23'h1cb349;
            7'd38: l64_fm_a=23'h1d959f; 7'd39: l64_fm_a=23'h1e79c1;
            7'd40: l64_fm_a=23'h1f5fb6; 7'd41: l64_fm_a=23'h204789;
            7'd42: l64_fm_a=23'h213144; 7'd43: l64_fm_a=23'h221cf3;
            7'd44: l64_fm_a=23'h230aa1; 7'd45: l64_fm_a=23'h23fa57;
            7'd46: l64_fm_a=23'h24ec1f; 7'd47: l64_fm_a=23'h25e004;
            7'd48: l64_fm_a=23'h26d613; 7'd49: l64_fm_a=23'h27ce5b;
            7'd50: l64_fm_a=23'h28c8ec; 7'd51: l64_fm_a=23'h29c5c2;
            7'd52: l64_fm_a=23'h2ac4e7; 7'd53: l64_fm_a=23'h2bc657;
            7'd54: l64_fm_a=23'h2cca1c; 7'd55: l64_fm_a=23'h2dd03d;
            7'd56: l64_fm_a=23'h2ed8c0; 7'd57: l64_fm_a=23'h2fe3b6;
            7'd58: l64_fm_a=23'h30f121; 7'd59: l64_fm_a=23'h320109;
            7'd60: l64_fm_a=23'h331366; 7'd61: l64_fm_a=23'h34284a;
            7'd62: l64_fm_a=23'h353fc4; 7'd63: l64_fm_a=23'h3659e3;
            7'd64: l64_fm_a=23'h3776b2; 7'd65: l64_fm_a=23'h38963d;
            7'd66: l64_fm_a=23'h39b88b; 7'd67: l64_fm_a=23'h3adda6;
            7'd68: l64_fm_a=23'h3c059b; 7'd69: l64_fm_a=23'h3d3074;
            7'd70: l64_fm_a=23'h3e5e38; 7'd71: l64_fm_a=23'h3f8ef1;
            7'd72: l64_fm_a=23'h40c2b4; 7'd73: l64_fm_a=23'h41f983;
            7'd74: l64_fm_a=23'h433370; 7'd75: l64_fm_a=23'h44707e;
            7'd76: l64_fm_a=23'h45b0bd; 7'd77: l64_fm_a=23'h46f438;
            7'd78: l64_fm_a=23'h483b58; 7'd79: l64_fm_a=23'h49862c;
            7'd80: l64_fm_a=23'h4ad4c4; 7'd81: l64_fm_a=23'h4c2737;
            7'd82: l64_fm_a=23'h4d7da1; 7'd83: l64_fm_a=23'h4ed80a;
            7'd84: l64_fm_a=23'h503682; 7'd85: l64_fm_a=23'h519914;
            7'd86: l64_fm_a=23'h52ffd1; 7'd87: l64_fm_a=23'h546ad6;
            7'd88: l64_fm_a=23'h55da36; 7'd89: l64_fm_a=23'h574e09;
            7'd90: l64_fm_a=23'h58c662; 7'd91: l64_fm_a=23'h5a4357;
            7'd92: l64_fm_a=23'h5bc504; 7'd93: l64_fm_a=23'h5d4b73;
            7'd94: l64_fm_a=23'h5ed6cd; 7'd95: l64_fm_a=23'h60671f;
            7'd96: l64_fm_a=23'h61fc7c; 7'd97: l64_fm_a=23'h6396f4;
            7'd98: l64_fm_a=23'h6536a2; 7'd99: l64_fm_a=23'h66dbab;
            7'd100: l64_fm_a=23'h688626; 7'd101: l64_fm_a=23'h6a3624;
            7'd102: l64_fm_a=23'h6bebb9; 7'd103: l64_fm_a=23'h6da704;
            7'd104: l64_fm_a=23'h6f681a; 7'd105: l64_fm_a=23'h712f0d;
            7'd106: l64_fm_a=23'h72fbff; 7'd107: l64_fm_a=23'h74ce10;
            7'd108: l64_fm_a=23'h76a65f; 7'd109: l64_fm_a=23'h7884b4;
            7'd110: l64_fm_a=23'h7a692c; 7'd111: l64_fm_a=23'h7c53e4;
            7'd112: l64_fm_a=23'h7e4500; 7'd113: l64_fm_a=23'h3FE484;
            7'd114: l64_fm_a=23'h402AB8; 7'd115: l64_fm_a=23'h407204;
            7'd116: l64_fm_a=23'h40BC81; 7'd117: l64_fm_a=23'h410D33;
            7'd118: l64_fm_a=23'h416028; 7'd119: l64_fm_a=23'h41B56E;
            7'd120: l64_fm_a=23'h420D09; 7'd121: l64_fm_a=23'h426801;
            7'd122: l64_fm_a=23'h42C55F; 7'd123: l64_fm_a=23'h432528;
            7'd124: l64_fm_a=23'h438767; 7'd125: l64_fm_a=23'h43EC2A;
            7'd126: l64_fm_a=23'h445381; 7'd127: l64_fm_a=23'h44BE72;
            default: l64_fm_a=23'h000000;
        endcase
    end
    wire [9:0] l64_exp32_a = {1'b0, {1'b0, l64_int_a[6:0]}} + 10'd127;
    reg [31:0] fp32_a;
    always @(*) begin
        if(l64_zero_a) fp32_a={l64_sign_a, 31'b0};
        else fp32_a={l64_sign_a, l64_exp32_a[7:0], l64_fm_a};
    end
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;conv_trigger<=0; end
        else begin conv_trigger<=frame_valid;
            if(frame_valid) a_reg<=a_r;
        end
    end
    reg [31:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=conv_trigger;
            if(conv_trigger) result_reg<=fp32_a;
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
