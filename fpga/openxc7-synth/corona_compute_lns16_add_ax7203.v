`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_lns16_add_ax7203 — LNS16 ADD on AX7203.
module corona_compute_lns16_add_ax7203 (
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
                3'd4: begin b_r[7:0]<=rx_byte;frm<=3'd5; end
                3'd5: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [15:0] a_reg,b_reg; reg [7:0] op_reg; reg comp_trigger;
    wire [15:0] fmt_a=a_reg, fmt_b=b_reg;
    wire [15:0] lns_val_a = fmt_a;
    wire lns_sign_a = lns_val_a[15];
    wire [14:0] lns_log_a = lns_val_a[14:0];
    wire lns_zero_a = (lns_val_a==16'h0000);
    wire signed [14:0] lns_slog_a = $signed(lns_log_a);
    wire signed [7:0] lns_int_a = lns_slog_a >>> 7;
    wire [6:0] lns_frac_a = lns_log_a[6:0];
    reg [22:0] lns_fm_a;
    always @(*) begin
        case(lns_frac_a)
            7'd0: lns_fm_a=23'h000000; 7'd1: lns_fm_a=23'h00b1ed;
            7'd2: lns_fm_a=23'h0164d2; 7'd3: lns_fm_a=23'h0218af;
            7'd4: lns_fm_a=23'h02cd87; 7'd5: lns_fm_a=23'h038359;
            7'd6: lns_fm_a=23'h043a4c; 7'd7: lns_fm_a=23'h04f20f;
            7'd8: lns_fm_a=23'h05aab4; 7'd9: lns_fm_a=23'h066456;
            7'd10: lns_fm_a=23'h071f5a; 7'd11: lns_fm_a=23'h07db45;
            7'd12: lns_fm_a=23'h089838; 7'd13: lns_fm_a=23'h095636;
            7'd14: lns_fm_a=23'h0a154a; 7'd15: lns_fm_a=23'h0ad576;
            7'd16: lns_fm_a=23'h0b96c1; 7'd17: lns_fm_a=23'h0c5931;
            7'd18: lns_fm_a=23'h0d1cdf; 7'd19: lns_fm_a=23'h0de1c4;
            7'd20: lns_fm_a=23'h0ea7f0; 7'd21: lns_fm_a=23'h0f6f70;
            7'd22: lns_fm_a=23'h103845; 7'd23: lns_fm_a=23'h11027f;
            7'd24: lns_fm_a=23'h11ce26; 7'd25: lns_fm_a=23'h129b3f;
            7'd26: lns_fm_a=23'h1369d3; 7'd27: lns_fm_a=23'h1439e6;
            7'd28: lns_fm_a=23'h150b7d; 7'd29: lns_fm_a=23'h15dea6;
            7'd30: lns_fm_a=23'h16b362; 7'd31: lns_fm_a=23'h1789c0;
            7'd32: lns_fm_a=23'h1861c3; 7'd33: lns_fm_a=23'h193b73;
            7'd34: lns_fm_a=23'h1a16d5; 7'd35: lns_fm_a=23'h1af3ea;
            7'd36: lns_fm_a=23'h1bd2b9; 7'd37: lns_fm_a=23'h1cb349;
            7'd38: lns_fm_a=23'h1d959f; 7'd39: lns_fm_a=23'h1e79c1;
            7'd40: lns_fm_a=23'h1f5fb6; 7'd41: lns_fm_a=23'h204789;
            7'd42: lns_fm_a=23'h213144; 7'd43: lns_fm_a=23'h221cf3;
            7'd44: lns_fm_a=23'h230aa1; 7'd45: lns_fm_a=23'h23fa57;
            7'd46: lns_fm_a=23'h24ec1f; 7'd47: lns_fm_a=23'h25e004;
            7'd48: lns_fm_a=23'h26d613; 7'd49: lns_fm_a=23'h27ce5b;
            7'd50: lns_fm_a=23'h28c8ec; 7'd51: lns_fm_a=23'h29c5c2;
            7'd52: lns_fm_a=23'h2ac4e7; 7'd53: lns_fm_a=23'h2bc657;
            7'd54: lns_fm_a=23'h2cca1c; 7'd55: lns_fm_a=23'h2dd03d;
            7'd56: lns_fm_a=23'h2ed8c0; 7'd57: lns_fm_a=23'h2fe3b6;
            7'd58: lns_fm_a=23'h30f121; 7'd59: lns_fm_a=23'h320109;
            7'd60: lns_fm_a=23'h331366; 7'd61: lns_fm_a=23'h34284a;
            7'd62: lns_fm_a=23'h353fc4; 7'd63: lns_fm_a=23'h3659e3;
            7'd64: lns_fm_a=23'h3776b2; 7'd65: lns_fm_a=23'h38963d;
            7'd66: lns_fm_a=23'h39b88b; 7'd67: lns_fm_a=23'h3adda6;
            7'd68: lns_fm_a=23'h3c059b; 7'd69: lns_fm_a=23'h3d3074;
            7'd70: lns_fm_a=23'h3e5e38; 7'd71: lns_fm_a=23'h3f8ef1;
            7'd72: lns_fm_a=23'h40c2b4; 7'd73: lns_fm_a=23'h41f983;
            7'd74: lns_fm_a=23'h433370; 7'd75: lns_fm_a=23'h44707e;
            7'd76: lns_fm_a=23'h45b0bd; 7'd77: lns_fm_a=23'h46f438;
            7'd78: lns_fm_a=23'h483b58; 7'd79: lns_fm_a=23'h49862c;
            7'd80: lns_fm_a=23'h4ad4c4; 7'd81: lns_fm_a=23'h4c2737;
            7'd82: lns_fm_a=23'h4d7da1; 7'd83: lns_fm_a=23'h4ed80a;
            7'd84: lns_fm_a=23'h503682; 7'd85: lns_fm_a=23'h519914;
            7'd86: lns_fm_a=23'h52ffd1; 7'd87: lns_fm_a=23'h546ad6;
            7'd88: lns_fm_a=23'h55da36; 7'd89: lns_fm_a=23'h574e09;
            7'd90: lns_fm_a=23'h58c662; 7'd91: lns_fm_a=23'h5a4357;
            7'd92: lns_fm_a=23'h5bc504; 7'd93: lns_fm_a=23'h5d4b73;
            7'd94: lns_fm_a=23'h5ed6cd; 7'd95: lns_fm_a=23'h60671f;
            7'd96: lns_fm_a=23'h61fc7c; 7'd97: lns_fm_a=23'h6396f4;
            7'd98: lns_fm_a=23'h6536a2; 7'd99: lns_fm_a=23'h66dbab;
            7'd100: lns_fm_a=23'h688626; 7'd101: lns_fm_a=23'h6a3624;
            7'd102: lns_fm_a=23'h6bebb9; 7'd103: lns_fm_a=23'h6da704;
            7'd104: lns_fm_a=23'h6f681a; 7'd105: lns_fm_a=23'h712f0d;
            7'd106: lns_fm_a=23'h72fbff; 7'd107: lns_fm_a=23'h74ce10;
            7'd108: lns_fm_a=23'h76a65f; 7'd109: lns_fm_a=23'h7884b4;
            7'd110: lns_fm_a=23'h7a692c; 7'd111: lns_fm_a=23'h7c53e4;
            7'd112: lns_fm_a=23'h7e4500; 7'd113: lns_fm_a=23'h3FE484;
            7'd114: lns_fm_a=23'h402AB8; 7'd115: lns_fm_a=23'h407204;
            7'd116: lns_fm_a=23'h40BC81; 7'd117: lns_fm_a=23'h410D33;
            7'd118: lns_fm_a=23'h416028; 7'd119: lns_fm_a=23'h41B56E;
            7'd120: lns_fm_a=23'h420D09; 7'd121: lns_fm_a=23'h426801;
            7'd122: lns_fm_a=23'h42C55F; 7'd123: lns_fm_a=23'h432528;
            7'd124: lns_fm_a=23'h438767; 7'd125: lns_fm_a=23'h43EC2A;
            7'd126: lns_fm_a=23'h445381; 7'd127: lns_fm_a=23'h44BE72;
            default: lns_fm_a=23'h000000;
        endcase
    end
    wire [8:0] lns_exp32_a = {1'b0, {1'b0,lns_int_a[6:0]}} + 9'd127;
    reg [31:0] fp32_a;
    always @(*) begin
        if(lns_zero_a) fp32_a=32'h00000000;
        else fp32_a={lns_sign_a,lns_exp32_a[7:0],lns_fm_a};
    end
    wire [15:0] lns_val_b = fmt_b;
    wire lns_sign_b = lns_val_b[15];
    wire [14:0] lns_log_b = lns_val_b[14:0];
    wire lns_zero_b = (lns_val_b==16'h0000);
    wire signed [14:0] lns_slog_b = $signed(lns_log_b);
    wire signed [7:0] lns_int_b = lns_slog_b >>> 7;
    wire [6:0] lns_frac_b = lns_log_b[6:0];
    reg [22:0] lns_fm_b;
    always @(*) begin
        case(lns_frac_b)
            7'd0: lns_fm_b=23'h000000; 7'd1: lns_fm_b=23'h00b1ed;
            7'd2: lns_fm_b=23'h0164d2; 7'd3: lns_fm_b=23'h0218af;
            7'd4: lns_fm_b=23'h02cd87; 7'd5: lns_fm_b=23'h038359;
            7'd6: lns_fm_b=23'h043a4c; 7'd7: lns_fm_b=23'h04f20f;
            7'd8: lns_fm_b=23'h05aab4; 7'd9: lns_fm_b=23'h066456;
            7'd10: lns_fm_b=23'h071f5a; 7'd11: lns_fm_b=23'h07db45;
            7'd12: lns_fm_b=23'h089838; 7'd13: lns_fm_b=23'h095636;
            7'd14: lns_fm_b=23'h0a154a; 7'd15: lns_fm_b=23'h0ad576;
            7'd16: lns_fm_b=23'h0b96c1; 7'd17: lns_fm_b=23'h0c5931;
            7'd18: lns_fm_b=23'h0d1cdf; 7'd19: lns_fm_b=23'h0de1c4;
            7'd20: lns_fm_b=23'h0ea7f0; 7'd21: lns_fm_b=23'h0f6f70;
            7'd22: lns_fm_b=23'h103845; 7'd23: lns_fm_b=23'h11027f;
            7'd24: lns_fm_b=23'h11ce26; 7'd25: lns_fm_b=23'h129b3f;
            7'd26: lns_fm_b=23'h1369d3; 7'd27: lns_fm_b=23'h1439e6;
            7'd28: lns_fm_b=23'h150b7d; 7'd29: lns_fm_b=23'h15dea6;
            7'd30: lns_fm_b=23'h16b362; 7'd31: lns_fm_b=23'h1789c0;
            7'd32: lns_fm_b=23'h1861c3; 7'd33: lns_fm_b=23'h193b73;
            7'd34: lns_fm_b=23'h1a16d5; 7'd35: lns_fm_b=23'h1af3ea;
            7'd36: lns_fm_b=23'h1bd2b9; 7'd37: lns_fm_b=23'h1cb349;
            7'd38: lns_fm_b=23'h1d959f; 7'd39: lns_fm_b=23'h1e79c1;
            7'd40: lns_fm_b=23'h1f5fb6; 7'd41: lns_fm_b=23'h204789;
            7'd42: lns_fm_b=23'h213144; 7'd43: lns_fm_b=23'h221cf3;
            7'd44: lns_fm_b=23'h230aa1; 7'd45: lns_fm_b=23'h23fa57;
            7'd46: lns_fm_b=23'h24ec1f; 7'd47: lns_fm_b=23'h25e004;
            7'd48: lns_fm_b=23'h26d613; 7'd49: lns_fm_b=23'h27ce5b;
            7'd50: lns_fm_b=23'h28c8ec; 7'd51: lns_fm_b=23'h29c5c2;
            7'd52: lns_fm_b=23'h2ac4e7; 7'd53: lns_fm_b=23'h2bc657;
            7'd54: lns_fm_b=23'h2cca1c; 7'd55: lns_fm_b=23'h2dd03d;
            7'd56: lns_fm_b=23'h2ed8c0; 7'd57: lns_fm_b=23'h2fe3b6;
            7'd58: lns_fm_b=23'h30f121; 7'd59: lns_fm_b=23'h320109;
            7'd60: lns_fm_b=23'h331366; 7'd61: lns_fm_b=23'h34284a;
            7'd62: lns_fm_b=23'h353fc4; 7'd63: lns_fm_b=23'h3659e3;
            7'd64: lns_fm_b=23'h3776b2; 7'd65: lns_fm_b=23'h38963d;
            7'd66: lns_fm_b=23'h39b88b; 7'd67: lns_fm_b=23'h3adda6;
            7'd68: lns_fm_b=23'h3c059b; 7'd69: lns_fm_b=23'h3d3074;
            7'd70: lns_fm_b=23'h3e5e38; 7'd71: lns_fm_b=23'h3f8ef1;
            7'd72: lns_fm_b=23'h40c2b4; 7'd73: lns_fm_b=23'h41f983;
            7'd74: lns_fm_b=23'h433370; 7'd75: lns_fm_b=23'h44707e;
            7'd76: lns_fm_b=23'h45b0bd; 7'd77: lns_fm_b=23'h46f438;
            7'd78: lns_fm_b=23'h483b58; 7'd79: lns_fm_b=23'h49862c;
            7'd80: lns_fm_b=23'h4ad4c4; 7'd81: lns_fm_b=23'h4c2737;
            7'd82: lns_fm_b=23'h4d7da1; 7'd83: lns_fm_b=23'h4ed80a;
            7'd84: lns_fm_b=23'h503682; 7'd85: lns_fm_b=23'h519914;
            7'd86: lns_fm_b=23'h52ffd1; 7'd87: lns_fm_b=23'h546ad6;
            7'd88: lns_fm_b=23'h55da36; 7'd89: lns_fm_b=23'h574e09;
            7'd90: lns_fm_b=23'h58c662; 7'd91: lns_fm_b=23'h5a4357;
            7'd92: lns_fm_b=23'h5bc504; 7'd93: lns_fm_b=23'h5d4b73;
            7'd94: lns_fm_b=23'h5ed6cd; 7'd95: lns_fm_b=23'h60671f;
            7'd96: lns_fm_b=23'h61fc7c; 7'd97: lns_fm_b=23'h6396f4;
            7'd98: lns_fm_b=23'h6536a2; 7'd99: lns_fm_b=23'h66dbab;
            7'd100: lns_fm_b=23'h688626; 7'd101: lns_fm_b=23'h6a3624;
            7'd102: lns_fm_b=23'h6bebb9; 7'd103: lns_fm_b=23'h6da704;
            7'd104: lns_fm_b=23'h6f681a; 7'd105: lns_fm_b=23'h712f0d;
            7'd106: lns_fm_b=23'h72fbff; 7'd107: lns_fm_b=23'h74ce10;
            7'd108: lns_fm_b=23'h76a65f; 7'd109: lns_fm_b=23'h7884b4;
            7'd110: lns_fm_b=23'h7a692c; 7'd111: lns_fm_b=23'h7c53e4;
            7'd112: lns_fm_b=23'h7e4500; 7'd113: lns_fm_b=23'h3FE484;
            7'd114: lns_fm_b=23'h402AB8; 7'd115: lns_fm_b=23'h407204;
            7'd116: lns_fm_b=23'h40BC81; 7'd117: lns_fm_b=23'h410D33;
            7'd118: lns_fm_b=23'h416028; 7'd119: lns_fm_b=23'h41B56E;
            7'd120: lns_fm_b=23'h420D09; 7'd121: lns_fm_b=23'h426801;
            7'd122: lns_fm_b=23'h42C55F; 7'd123: lns_fm_b=23'h432528;
            7'd124: lns_fm_b=23'h438767; 7'd125: lns_fm_b=23'h43EC2A;
            7'd126: lns_fm_b=23'h445381; 7'd127: lns_fm_b=23'h44BE72;
            default: lns_fm_b=23'h000000;
        endcase
    end
    wire [8:0] lns_exp32_b = {1'b0, {1'b0,lns_int_b[6:0]}} + 9'd127;
    reg [31:0] fp32_b;
    always @(*) begin
        if(lns_zero_b) fp32_b=32'h00000000;
        else fp32_b={lns_sign_b,lns_exp32_b[7:0],lns_fm_b};
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
    // LNS16: sign + signed 15-bit log (scale 128)
    // int part = exp - 127, frac = top 7 bits of mantissa
    wire signed [7:0] q_logint = $signed({1'b0,q_exp}) - 8'sd127;
    wire [14:0] q_logval = {q_logint[6:0], q_mant[22:16]};
    reg [15:0] q_result;
    always @(*) begin
        if(q_nan) q_result=16'h0000;
        else if(q_zero) q_result=16'h0000;
        else q_result={q_sign,q_logval};
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
