`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_takum64_alu_ax7203 — TAKUM64 ALU on AX7203.
module corona_compute_takum64_alu_ax7203 (
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
    wire [63:0] fmt_a=a_reg, fmt_b=b_reg;
    wire [7:0] tk_idx_a = fmt_a_a[63:56];
    reg [31:0] fp32_a;
    always @(*) begin
        case(tk_idx_a)
            8'd0: fp32_a=32'h00000000;
            8'd1: fp32_a=32'h00000000;
            8'd2: fp32_a=32'h00000000;
            8'd3: fp32_a=32'h00000000;
            8'd4: fp32_a=32'h00000000;
            8'd5: fp32_a=32'h00000000;
            8'd6: fp32_a=32'h00000000;
            8'd7: fp32_a=32'h00000000;
            8'd8: fp32_a=32'h148efa42;
            8'd9: fp32_a=32'h14ebbaec;
            8'd10: fp32_a=32'h154253a1;
            8'd11: fp32_a=32'h15a031fc;
            8'd12: fp32_a=32'h16040f05;
            8'd13: fp32_a=32'h1659ba5a;
            8'd14: fp32_a=32'h16b37c80;
            8'd15: fp32_a=32'h1713f623;
            8'd16: fp32_a=32'h2e88ded2;
            8'd17: fp32_a=32'h2ee1a93f;
            8'd18: fp32_a=32'h2f3a06b1;
            8'd19: fp32_a=32'h2f995a46;
            8'd20: fp32_a=32'h2ffcd5f3;
            8'd21: fp32_a=32'h30506d87;
            8'd22: fp32_a=32'h30abd1d8;
            8'd23: fp32_a=32'h310da433;
            8'd24: fp32_a=32'h3729f46c;
            8'd25: fp32_a=32'h378c1aa1;
            8'd26: fp32_a=32'h37e6fe13;
            8'd27: fp32_a=32'h383e6bce;
            8'd28: fp32_a=32'h389cf9c5;
            8'd29: fp32_a=32'h39016791;
            8'd30: fp32_a=32'h39555a20;
            8'd31: fp32_a=32'h39afe108;
            8'd32: fp32_a=32'h3a10fcdd;
            8'd33: fp32_a=32'h3a6f0b5d;
            8'd34: fp32_a=32'h3ac50f0c;
            8'd35: fp32_a=32'h3b227290;
            8'd36: fp32_a=32'h3b85ea53;
            8'd37: fp32_a=32'h3bdcc9ff;
            8'd38: fp32_a=32'h3c360282;
            8'd39: fp32_a=32'h3c960aae;
            8'd40: fp32_a=32'h3cf76081;
            8'd41: fp32_a=32'h3d1ed1b4;
            8'd42: fp32_a=32'h3d4bed86;
            8'd43: fp32_a=32'h3d82ec9c;
            8'd44: fp32_a=32'h3da81c2e;
            8'd45: fp32_a=32'h3dd7db8c;
            8'd46: fp32_a=32'h3e0a9555;
            8'd47: fp32_a=32'h3e31f1cc;
            8'd48: fp32_a=32'h3e647c3c;
            8'd49: fp32_a=32'h3e817431;
            8'd50: fp32_a=32'h3e92b0c2;
            8'd51: fp32_a=32'h3ea638d9;
            8'd52: fp32_a=32'h3ebc5ab2;
            8'd53: fp32_a=32'h3ed56ef0;
            8'd54: fp32_a=32'h3ef1da07;
            8'd55: fp32_a=32'h3f0906e5;
            8'd56: fp32_a=32'h3f1b4598;
            8'd57: fp32_a=32'h3f254939;
            8'd58: fp32_a=32'h3f2ff231;
            8'd59: fp32_a=32'h3f3b4b29;
            8'd60: fp32_a=32'h3f475f7d;
            8'd61: fp32_a=32'h3f543b41;
            8'd62: fp32_a=32'h3f61eb51;
            8'd63: fp32_a=32'h3f707d60;
            8'd64: fp32_a=32'h3f800000;
            8'd65: fp32_a=32'h3f88415b;
            8'd66: fp32_a=32'h3f910b02;
            8'd67: fp32_a=32'h3f9a65c1;
            8'd68: fp32_a=32'h3fa45af2;
            8'd69: fp32_a=32'h3faef48c;
            8'd70: fp32_a=32'h3fba3d29;
            8'd71: fp32_a=32'h3fc64012;
            8'd72: fp32_a=32'h3fd3094c;
            8'd73: fp32_a=32'h3fef22af;
            8'd74: fp32_a=32'h40077cee;
            8'd75: fp32_a=32'h4019872c;
            8'd76: fp32_a=32'h402df854;
            8'd77: fp32_a=32'h40452246;
            8'd78: fp32_a=32'h405f61c7;
            8'd79: fp32_a=32'h407d1ffa;
            8'd80: fp32_a=32'h408f69ff;
            8'd81: fp32_a=32'h40b825b5;
            8'd82: fp32_a=32'h40ec7326;
            8'd83: fp32_a=32'h4117cdc4;
            8'd84: fp32_a=32'h4142eb7f;
            8'd85: fp32_a=32'h417a4838;
            8'd86: fp32_a=32'h41a0af2e;
            8'd87: fp32_a=32'h41ce529e;
            8'd88: fp32_a=32'h42047639;
            8'd89: fp32_a=32'h425a6481;
            8'd90: fp32_a=32'h42b408c5;
            8'd91: fp32_a=32'h431469c5;
            8'd92: fp32_a=32'h4374b122;
            8'd93: fp32_a=32'h43c9b6e3;
            8'd94: fp32_a=32'h44264911;
            8'd95: fp32_a=32'h44891443;
            8'd96: fp32_a=32'h44e2015b;
            8'd97: fp32_a=32'h453a4f54;
            8'd98: fp32_a=32'h45999627;
            8'd99: fp32_a=32'h45fd38ac;
            8'd100: fp32_a=32'h4650bee8;
            8'd101: fp32_a=32'h46ac14ee;
            8'd102: fp32_a=32'h470ddb81;
            8'd103: fp32_a=32'h4769e224;
            8'd104: fp32_a=32'h4d8c5155;
            8'd105: fp32_a=32'h4de75844;
            8'd106: fp32_a=32'h4e3eb628;
            8'd107: fp32_a=32'h4e9d3710;
            8'd108: fp32_a=32'h4f019a18;
            8'd109: fp32_a=32'h4f55ad6e;
            8'd110: fp32_a=32'h4fb025b4;
            8'd111: fp32_a=32'h5011357a;
            8'd112: fp32_a=32'h678652fb;
            8'd113: fp32_a=32'h67dd768b;
            8'd114: fp32_a=32'h683690c0;
            8'd115: fp32_a=32'h68967ff0;
            8'd116: fp32_a=32'h68f821d4;
            8'd117: fp32_a=32'h694c8ce5;
            8'd118: fp32_a=32'h69a89f8f;
            8'd119: fp32_a=32'h6a0b01a3;
            8'd120: fp32_a=32'h7f800000;
            8'd121: fp32_a=32'h7f800000;
            8'd122: fp32_a=32'h7f800000;
            8'd123: fp32_a=32'h7f800000;
            8'd124: fp32_a=32'h7f800000;
            8'd125: fp32_a=32'h7f800000;
            8'd126: fp32_a=32'h7f800000;
            8'd127: fp32_a=32'h7f800000;
            8'd128: fp32_a=32'h7fc00000;
            8'd129: fp32_a=32'hff800000;
            8'd130: fp32_a=32'hff800000;
            8'd131: fp32_a=32'hff800000;
            8'd132: fp32_a=32'hff800000;
            8'd133: fp32_a=32'hff800000;
            8'd134: fp32_a=32'hff800000;
            8'd135: fp32_a=32'hff800000;
            8'd136: fp32_a=32'hea652ecc;
            8'd137: fp32_a=32'hea0b01a3;
            8'd138: fp32_a=32'he9a89f8f;
            8'd139: fp32_a=32'he94c8ce5;
            8'd140: fp32_a=32'he8f821d4;
            8'd141: fp32_a=32'he8967ff0;
            8'd142: fp32_a=32'he83690c0;
            8'd143: fp32_a=32'he7dd768b;
            8'd144: fp32_a=32'hd06f68b3;
            8'd145: fp32_a=32'hd011357a;
            8'd146: fp32_a=32'hcfb025b4;
            8'd147: fp32_a=32'hcf55ad6e;
            8'd148: fp32_a=32'hcf019a18;
            8'd149: fp32_a=32'hce9d3710;
            8'd150: fp32_a=32'hce3eb628;
            8'd151: fp32_a=32'hcde75844;
            8'd152: fp32_a=32'hc7c0cde3;
            8'd153: fp32_a=32'hc769e224;
            8'd154: fp32_a=32'hc70ddb81;
            8'd155: fp32_a=32'hc6ac14ee;
            8'd156: fp32_a=32'hc650bee8;
            8'd157: fp32_a=32'hc5fd38ac;
            8'd158: fp32_a=32'hc5999627;
            8'd159: fp32_a=32'hc53a4f54;
            8'd160: fp32_a=32'hc4e2015b;
            8'd161: fp32_a=32'hc4891443;
            8'd162: fp32_a=32'hc4264911;
            8'd163: fp32_a=32'hc3c9b6e3;
            8'd164: fp32_a=32'hc374b122;
            8'd165: fp32_a=32'hc31469c5;
            8'd166: fp32_a=32'hc2b408c5;
            8'd167: fp32_a=32'hc25a6481;
            8'd168: fp32_a=32'hc2047639;
            8'd169: fp32_a=32'hc1ce529e;
            8'd170: fp32_a=32'hc1a0af2e;
            8'd171: fp32_a=32'hc17a4838;
            8'd172: fp32_a=32'hc142eb7f;
            8'd173: fp32_a=32'hc117cdc4;
            8'd174: fp32_a=32'hc0ec7326;
            8'd175: fp32_a=32'hc0b825b5;
            8'd176: fp32_a=32'hc08f69ff;
            8'd177: fp32_a=32'hc07d1ffa;
            8'd178: fp32_a=32'hc05f61c7;
            8'd179: fp32_a=32'hc0452246;
            8'd180: fp32_a=32'hc02df854;
            8'd181: fp32_a=32'hc019872c;
            8'd182: fp32_a=32'hc0077cee;
            8'd183: fp32_a=32'hbfef22af;
            8'd184: fp32_a=32'hbfd3094c;
            8'd185: fp32_a=32'hbfc64012;
            8'd186: fp32_a=32'hbfba3d29;
            8'd187: fp32_a=32'hbfaef48c;
            8'd188: fp32_a=32'hbfa45af2;
            8'd189: fp32_a=32'hbf9a65c1;
            8'd190: fp32_a=32'hbf910b02;
            8'd191: fp32_a=32'hbf88415b;
            8'd192: fp32_a=32'hbf800000;
            8'd193: fp32_a=32'hbf707d60;
            8'd194: fp32_a=32'hbf61eb51;
            8'd195: fp32_a=32'hbf543b41;
            8'd196: fp32_a=32'hbf475f7d;
            8'd197: fp32_a=32'hbf3b4b29;
            8'd198: fp32_a=32'hbf2ff231;
            8'd199: fp32_a=32'hbf254939;
            8'd200: fp32_a=32'hbf1b4598;
            8'd201: fp32_a=32'hbf0906e5;
            8'd202: fp32_a=32'hbef1da07;
            8'd203: fp32_a=32'hbed56ef0;
            8'd204: fp32_a=32'hbebc5ab2;
            8'd205: fp32_a=32'hbea638d9;
            8'd206: fp32_a=32'hbe92b0c2;
            8'd207: fp32_a=32'hbe817431;
            8'd208: fp32_a=32'hbe647c3c;
            8'd209: fp32_a=32'hbe31f1cc;
            8'd210: fp32_a=32'hbe0a9555;
            8'd211: fp32_a=32'hbdd7db8c;
            8'd212: fp32_a=32'hbda81c2e;
            8'd213: fp32_a=32'hbd82ec9c;
            8'd214: fp32_a=32'hbd4bed86;
            8'd215: fp32_a=32'hbd1ed1b4;
            8'd216: fp32_a=32'hbcf76081;
            8'd217: fp32_a=32'hbc960aae;
            8'd218: fp32_a=32'hbc360282;
            8'd219: fp32_a=32'hbbdcc9ff;
            8'd220: fp32_a=32'hbb85ea53;
            8'd221: fp32_a=32'hbb227290;
            8'd222: fp32_a=32'hbac50f0c;
            8'd223: fp32_a=32'hba6f0b5d;
            8'd224: fp32_a=32'hba10fcdd;
            8'd225: fp32_a=32'hb9afe108;
            8'd226: fp32_a=32'hb9555a20;
            8'd227: fp32_a=32'hb9016791;
            8'd228: fp32_a=32'hb89cf9c5;
            8'd229: fp32_a=32'hb83e6bce;
            8'd230: fp32_a=32'hb7e6fe13;
            8'd231: fp32_a=32'hb78c1aa1;
            8'd232: fp32_a=32'hb16986f6;
            8'd233: fp32_a=32'hb10da433;
            8'd234: fp32_a=32'hb0abd1d8;
            8'd235: fp32_a=32'hb0506d87;
            8'd236: fp32_a=32'haffcd5f3;
            8'd237: fp32_a=32'haf995a46;
            8'd238: fp32_a=32'haf3a06b1;
            8'd239: fp32_a=32'haee1a93f;
            8'd240: fp32_a=32'h9773f27d;
            8'd241: fp32_a=32'h9713f623;
            8'd242: fp32_a=32'h96b37c80;
            8'd243: fp32_a=32'h9659ba5a;
            8'd244: fp32_a=32'h96040f05;
            8'd245: fp32_a=32'h95a031fc;
            8'd246: fp32_a=32'h954253a1;
            8'd247: fp32_a=32'h94ebbaec;
            8'd248: fp32_a=32'h80000000;
            8'd249: fp32_a=32'h80000000;
            8'd250: fp32_a=32'h80000000;
            8'd251: fp32_a=32'h80000000;
            8'd252: fp32_a=32'h80000000;
            8'd253: fp32_a=32'h80000000;
            8'd254: fp32_a=32'h80000000;
            8'd255: fp32_a=32'h80000000;
            default: fp32_a=32'h00000000;
        endcase
    end
    wire [7:0] tk_idx_b = fmt_b_b[63:56];
    reg [31:0] fp32_b;
    always @(*) begin
        case(tk_idx_b)
            8'd0: fp32_b=32'h00000000;
            8'd1: fp32_b=32'h00000000;
            8'd2: fp32_b=32'h00000000;
            8'd3: fp32_b=32'h00000000;
            8'd4: fp32_b=32'h00000000;
            8'd5: fp32_b=32'h00000000;
            8'd6: fp32_b=32'h00000000;
            8'd7: fp32_b=32'h00000000;
            8'd8: fp32_b=32'h148efa42;
            8'd9: fp32_b=32'h14ebbaec;
            8'd10: fp32_b=32'h154253a1;
            8'd11: fp32_b=32'h15a031fc;
            8'd12: fp32_b=32'h16040f05;
            8'd13: fp32_b=32'h1659ba5a;
            8'd14: fp32_b=32'h16b37c80;
            8'd15: fp32_b=32'h1713f623;
            8'd16: fp32_b=32'h2e88ded2;
            8'd17: fp32_b=32'h2ee1a93f;
            8'd18: fp32_b=32'h2f3a06b1;
            8'd19: fp32_b=32'h2f995a46;
            8'd20: fp32_b=32'h2ffcd5f3;
            8'd21: fp32_b=32'h30506d87;
            8'd22: fp32_b=32'h30abd1d8;
            8'd23: fp32_b=32'h310da433;
            8'd24: fp32_b=32'h3729f46c;
            8'd25: fp32_b=32'h378c1aa1;
            8'd26: fp32_b=32'h37e6fe13;
            8'd27: fp32_b=32'h383e6bce;
            8'd28: fp32_b=32'h389cf9c5;
            8'd29: fp32_b=32'h39016791;
            8'd30: fp32_b=32'h39555a20;
            8'd31: fp32_b=32'h39afe108;
            8'd32: fp32_b=32'h3a10fcdd;
            8'd33: fp32_b=32'h3a6f0b5d;
            8'd34: fp32_b=32'h3ac50f0c;
            8'd35: fp32_b=32'h3b227290;
            8'd36: fp32_b=32'h3b85ea53;
            8'd37: fp32_b=32'h3bdcc9ff;
            8'd38: fp32_b=32'h3c360282;
            8'd39: fp32_b=32'h3c960aae;
            8'd40: fp32_b=32'h3cf76081;
            8'd41: fp32_b=32'h3d1ed1b4;
            8'd42: fp32_b=32'h3d4bed86;
            8'd43: fp32_b=32'h3d82ec9c;
            8'd44: fp32_b=32'h3da81c2e;
            8'd45: fp32_b=32'h3dd7db8c;
            8'd46: fp32_b=32'h3e0a9555;
            8'd47: fp32_b=32'h3e31f1cc;
            8'd48: fp32_b=32'h3e647c3c;
            8'd49: fp32_b=32'h3e817431;
            8'd50: fp32_b=32'h3e92b0c2;
            8'd51: fp32_b=32'h3ea638d9;
            8'd52: fp32_b=32'h3ebc5ab2;
            8'd53: fp32_b=32'h3ed56ef0;
            8'd54: fp32_b=32'h3ef1da07;
            8'd55: fp32_b=32'h3f0906e5;
            8'd56: fp32_b=32'h3f1b4598;
            8'd57: fp32_b=32'h3f254939;
            8'd58: fp32_b=32'h3f2ff231;
            8'd59: fp32_b=32'h3f3b4b29;
            8'd60: fp32_b=32'h3f475f7d;
            8'd61: fp32_b=32'h3f543b41;
            8'd62: fp32_b=32'h3f61eb51;
            8'd63: fp32_b=32'h3f707d60;
            8'd64: fp32_b=32'h3f800000;
            8'd65: fp32_b=32'h3f88415b;
            8'd66: fp32_b=32'h3f910b02;
            8'd67: fp32_b=32'h3f9a65c1;
            8'd68: fp32_b=32'h3fa45af2;
            8'd69: fp32_b=32'h3faef48c;
            8'd70: fp32_b=32'h3fba3d29;
            8'd71: fp32_b=32'h3fc64012;
            8'd72: fp32_b=32'h3fd3094c;
            8'd73: fp32_b=32'h3fef22af;
            8'd74: fp32_b=32'h40077cee;
            8'd75: fp32_b=32'h4019872c;
            8'd76: fp32_b=32'h402df854;
            8'd77: fp32_b=32'h40452246;
            8'd78: fp32_b=32'h405f61c7;
            8'd79: fp32_b=32'h407d1ffa;
            8'd80: fp32_b=32'h408f69ff;
            8'd81: fp32_b=32'h40b825b5;
            8'd82: fp32_b=32'h40ec7326;
            8'd83: fp32_b=32'h4117cdc4;
            8'd84: fp32_b=32'h4142eb7f;
            8'd85: fp32_b=32'h417a4838;
            8'd86: fp32_b=32'h41a0af2e;
            8'd87: fp32_b=32'h41ce529e;
            8'd88: fp32_b=32'h42047639;
            8'd89: fp32_b=32'h425a6481;
            8'd90: fp32_b=32'h42b408c5;
            8'd91: fp32_b=32'h431469c5;
            8'd92: fp32_b=32'h4374b122;
            8'd93: fp32_b=32'h43c9b6e3;
            8'd94: fp32_b=32'h44264911;
            8'd95: fp32_b=32'h44891443;
            8'd96: fp32_b=32'h44e2015b;
            8'd97: fp32_b=32'h453a4f54;
            8'd98: fp32_b=32'h45999627;
            8'd99: fp32_b=32'h45fd38ac;
            8'd100: fp32_b=32'h4650bee8;
            8'd101: fp32_b=32'h46ac14ee;
            8'd102: fp32_b=32'h470ddb81;
            8'd103: fp32_b=32'h4769e224;
            8'd104: fp32_b=32'h4d8c5155;
            8'd105: fp32_b=32'h4de75844;
            8'd106: fp32_b=32'h4e3eb628;
            8'd107: fp32_b=32'h4e9d3710;
            8'd108: fp32_b=32'h4f019a18;
            8'd109: fp32_b=32'h4f55ad6e;
            8'd110: fp32_b=32'h4fb025b4;
            8'd111: fp32_b=32'h5011357a;
            8'd112: fp32_b=32'h678652fb;
            8'd113: fp32_b=32'h67dd768b;
            8'd114: fp32_b=32'h683690c0;
            8'd115: fp32_b=32'h68967ff0;
            8'd116: fp32_b=32'h68f821d4;
            8'd117: fp32_b=32'h694c8ce5;
            8'd118: fp32_b=32'h69a89f8f;
            8'd119: fp32_b=32'h6a0b01a3;
            8'd120: fp32_b=32'h7f800000;
            8'd121: fp32_b=32'h7f800000;
            8'd122: fp32_b=32'h7f800000;
            8'd123: fp32_b=32'h7f800000;
            8'd124: fp32_b=32'h7f800000;
            8'd125: fp32_b=32'h7f800000;
            8'd126: fp32_b=32'h7f800000;
            8'd127: fp32_b=32'h7f800000;
            8'd128: fp32_b=32'h7fc00000;
            8'd129: fp32_b=32'hff800000;
            8'd130: fp32_b=32'hff800000;
            8'd131: fp32_b=32'hff800000;
            8'd132: fp32_b=32'hff800000;
            8'd133: fp32_b=32'hff800000;
            8'd134: fp32_b=32'hff800000;
            8'd135: fp32_b=32'hff800000;
            8'd136: fp32_b=32'hea652ecc;
            8'd137: fp32_b=32'hea0b01a3;
            8'd138: fp32_b=32'he9a89f8f;
            8'd139: fp32_b=32'he94c8ce5;
            8'd140: fp32_b=32'he8f821d4;
            8'd141: fp32_b=32'he8967ff0;
            8'd142: fp32_b=32'he83690c0;
            8'd143: fp32_b=32'he7dd768b;
            8'd144: fp32_b=32'hd06f68b3;
            8'd145: fp32_b=32'hd011357a;
            8'd146: fp32_b=32'hcfb025b4;
            8'd147: fp32_b=32'hcf55ad6e;
            8'd148: fp32_b=32'hcf019a18;
            8'd149: fp32_b=32'hce9d3710;
            8'd150: fp32_b=32'hce3eb628;
            8'd151: fp32_b=32'hcde75844;
            8'd152: fp32_b=32'hc7c0cde3;
            8'd153: fp32_b=32'hc769e224;
            8'd154: fp32_b=32'hc70ddb81;
            8'd155: fp32_b=32'hc6ac14ee;
            8'd156: fp32_b=32'hc650bee8;
            8'd157: fp32_b=32'hc5fd38ac;
            8'd158: fp32_b=32'hc5999627;
            8'd159: fp32_b=32'hc53a4f54;
            8'd160: fp32_b=32'hc4e2015b;
            8'd161: fp32_b=32'hc4891443;
            8'd162: fp32_b=32'hc4264911;
            8'd163: fp32_b=32'hc3c9b6e3;
            8'd164: fp32_b=32'hc374b122;
            8'd165: fp32_b=32'hc31469c5;
            8'd166: fp32_b=32'hc2b408c5;
            8'd167: fp32_b=32'hc25a6481;
            8'd168: fp32_b=32'hc2047639;
            8'd169: fp32_b=32'hc1ce529e;
            8'd170: fp32_b=32'hc1a0af2e;
            8'd171: fp32_b=32'hc17a4838;
            8'd172: fp32_b=32'hc142eb7f;
            8'd173: fp32_b=32'hc117cdc4;
            8'd174: fp32_b=32'hc0ec7326;
            8'd175: fp32_b=32'hc0b825b5;
            8'd176: fp32_b=32'hc08f69ff;
            8'd177: fp32_b=32'hc07d1ffa;
            8'd178: fp32_b=32'hc05f61c7;
            8'd179: fp32_b=32'hc0452246;
            8'd180: fp32_b=32'hc02df854;
            8'd181: fp32_b=32'hc019872c;
            8'd182: fp32_b=32'hc0077cee;
            8'd183: fp32_b=32'hbfef22af;
            8'd184: fp32_b=32'hbfd3094c;
            8'd185: fp32_b=32'hbfc64012;
            8'd186: fp32_b=32'hbfba3d29;
            8'd187: fp32_b=32'hbfaef48c;
            8'd188: fp32_b=32'hbfa45af2;
            8'd189: fp32_b=32'hbf9a65c1;
            8'd190: fp32_b=32'hbf910b02;
            8'd191: fp32_b=32'hbf88415b;
            8'd192: fp32_b=32'hbf800000;
            8'd193: fp32_b=32'hbf707d60;
            8'd194: fp32_b=32'hbf61eb51;
            8'd195: fp32_b=32'hbf543b41;
            8'd196: fp32_b=32'hbf475f7d;
            8'd197: fp32_b=32'hbf3b4b29;
            8'd198: fp32_b=32'hbf2ff231;
            8'd199: fp32_b=32'hbf254939;
            8'd200: fp32_b=32'hbf1b4598;
            8'd201: fp32_b=32'hbf0906e5;
            8'd202: fp32_b=32'hbef1da07;
            8'd203: fp32_b=32'hbed56ef0;
            8'd204: fp32_b=32'hbebc5ab2;
            8'd205: fp32_b=32'hbea638d9;
            8'd206: fp32_b=32'hbe92b0c2;
            8'd207: fp32_b=32'hbe817431;
            8'd208: fp32_b=32'hbe647c3c;
            8'd209: fp32_b=32'hbe31f1cc;
            8'd210: fp32_b=32'hbe0a9555;
            8'd211: fp32_b=32'hbdd7db8c;
            8'd212: fp32_b=32'hbda81c2e;
            8'd213: fp32_b=32'hbd82ec9c;
            8'd214: fp32_b=32'hbd4bed86;
            8'd215: fp32_b=32'hbd1ed1b4;
            8'd216: fp32_b=32'hbcf76081;
            8'd217: fp32_b=32'hbc960aae;
            8'd218: fp32_b=32'hbc360282;
            8'd219: fp32_b=32'hbbdcc9ff;
            8'd220: fp32_b=32'hbb85ea53;
            8'd221: fp32_b=32'hbb227290;
            8'd222: fp32_b=32'hbac50f0c;
            8'd223: fp32_b=32'hba6f0b5d;
            8'd224: fp32_b=32'hba10fcdd;
            8'd225: fp32_b=32'hb9afe108;
            8'd226: fp32_b=32'hb9555a20;
            8'd227: fp32_b=32'hb9016791;
            8'd228: fp32_b=32'hb89cf9c5;
            8'd229: fp32_b=32'hb83e6bce;
            8'd230: fp32_b=32'hb7e6fe13;
            8'd231: fp32_b=32'hb78c1aa1;
            8'd232: fp32_b=32'hb16986f6;
            8'd233: fp32_b=32'hb10da433;
            8'd234: fp32_b=32'hb0abd1d8;
            8'd235: fp32_b=32'hb0506d87;
            8'd236: fp32_b=32'haffcd5f3;
            8'd237: fp32_b=32'haf995a46;
            8'd238: fp32_b=32'haf3a06b1;
            8'd239: fp32_b=32'haee1a93f;
            8'd240: fp32_b=32'h9773f27d;
            8'd241: fp32_b=32'h9713f623;
            8'd242: fp32_b=32'h96b37c80;
            8'd243: fp32_b=32'h9659ba5a;
            8'd244: fp32_b=32'h96040f05;
            8'd245: fp32_b=32'h95a031fc;
            8'd246: fp32_b=32'h954253a1;
            8'd247: fp32_b=32'h94ebbaec;
            8'd248: fp32_b=32'h80000000;
            8'd249: fp32_b=32'h80000000;
            8'd250: fp32_b=32'h80000000;
            8'd251: fp32_b=32'h80000000;
            8'd252: fp32_b=32'h80000000;
            8'd253: fp32_b=32'h80000000;
            8'd254: fp32_b=32'h80000000;
            8'd255: fp32_b=32'h80000000;
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
    wire q_inf=(q_exp==8'hFF)&&(q_mant==0);
    reg [7:0] q_tk8;
    always @(*) begin
        if(q_nan) q_tk8=8'd80;
        else if(q_zero) q_tk8=8'd0;
        else if(q_inf) q_tk8=q_sign?8'd129:8'd120;
        else if(q_sign) begin
            if(q_exp<=8'd40) q_tk8=8'd247;
            else if(q_exp>=8'd212) q_tk8=8'd136;
            else q_tk8=8'd248-(q_exp-8'd40);
        end else begin
            if(q_exp<=8'd40) q_tk8=8'd0;
            else if(q_exp>=8'd250) q_tk8=8'd120;
            else q_tk8=(q_exp-8'd40)+8'd8;
        end
    end
    reg [63:0] q_result;
    always @(*) q_result={q_tk8, 56'h0};
    reg [63:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=ovld;
            if(ovld) result_reg<=q_result;
        end
    end
    assign led[2]=|result_reg;
    localparam [3:0] TX_LEN = 9;
    // TX: buffer+mux (no conflicting NBA — fixes tx race). 9 bytes sliced from tx_load[71:0].
    wire [71:0] tx_load = {result_reg, 8'hA5};
    reg responding; reg [3:0] tx_idx; reg [7:0] tx_buf0, tx_buf1, tx_buf2, tx_buf3, tx_buf4, tx_buf5, tx_buf6, tx_buf7, tx_buf8;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF; tx_buf1<=8'hFF; tx_buf2<=8'hFF; tx_buf3<=8'hFF; tx_buf4<=8'hFF; tx_buf5<=8'hFF; tx_buf6<=8'hFF; tx_buf7<=8'hFF; tx_buf8<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=tx_load[7:0]; tx_buf1<=tx_load[15:8]; tx_buf2<=tx_load[23:16]; tx_buf3<=tx_load[31:24]; tx_buf4<=tx_load[39:32]; tx_buf5<=tx_load[47:40]; tx_buf6<=tx_load[55:48]; tx_buf7<=tx_load[63:56]; tx_buf8<=tx_load[71:64]; responding<=1; tx_idx<=0;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        case(tx_idx)
                            4'd0: tsr<={1'b1,tx_buf0,1'b0};
                            4'd1: tsr<={1'b1,tx_buf1,1'b0};
                            4'd2: tsr<={1'b1,tx_buf2,1'b0};
                            4'd3: tsr<={1'b1,tx_buf3,1'b0};
                            4'd4: tsr<={1'b1,tx_buf4,1'b0};
                            4'd5: tsr<={1'b1,tx_buf5,1'b0};
                            4'd6: tsr<={1'b1,tx_buf6,1'b0};
                            4'd7: tsr<={1'b1,tx_buf7,1'b0};
                            4'd8: tsr<={1'b1,tx_buf8,1'b0};
                        endcase
                        if(tx_idx==8) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
    endmodule
`default_nettype wire
