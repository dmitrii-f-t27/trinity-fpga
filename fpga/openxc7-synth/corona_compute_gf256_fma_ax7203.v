`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_gf256_fma_ax7203 — GoldenFloat256 FMA (y=a*b+c) on AX7203.
// GF256: [S:1][E:97][M:158] = 256 bits, BIAS=79228162514264337593543950335, HAS_INF=1.
// Pipelined: gf_mul_param -> gf_adder_param. Latency: 2 cycles.
module corona_compute_gf256_fma_ax7203 (
    input  wire rst_n, input wire uart_rx, output reg uart_tx, output wire [3:0] led
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

    // ---- UART RX ----
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


    // ---- Frame FSM ----
    reg [6:0] frm; reg [7:0] fmt_r; reg [255:0] a_r, b_r, c_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;b_r<=0;c_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                7'd0: frm<=(rx_byte==8'hAA)?7'd1:7'd0;
                7'd1: frm<=(rx_byte==8'h55)?7'd2:7'd0;
                7'd2: begin fmt_r<=rx_byte;frm<=7'd3; end
                7'd3: begin a_r[7:0]<=rx_byte;frm<=7'd4; end
                7'd4: begin a_r[15:8]<=rx_byte;frm<=7'd5; end
                7'd5: begin a_r[23:16]<=rx_byte;frm<=7'd6; end
                7'd6: begin a_r[31:24]<=rx_byte;frm<=7'd7; end
                7'd7: begin a_r[39:32]<=rx_byte;frm<=7'd8; end
                7'd8: begin a_r[47:40]<=rx_byte;frm<=7'd9; end
                7'd9: begin a_r[55:48]<=rx_byte;frm<=7'd10; end
                7'd10: begin a_r[63:56]<=rx_byte;frm<=7'd11; end
                7'd11: begin a_r[71:64]<=rx_byte;frm<=7'd12; end
                7'd12: begin a_r[79:72]<=rx_byte;frm<=7'd13; end
                7'd13: begin a_r[87:80]<=rx_byte;frm<=7'd14; end
                7'd14: begin a_r[95:88]<=rx_byte;frm<=7'd15; end
                7'd15: begin a_r[103:96]<=rx_byte;frm<=7'd16; end
                7'd16: begin a_r[111:104]<=rx_byte;frm<=7'd17; end
                7'd17: begin a_r[119:112]<=rx_byte;frm<=7'd18; end
                7'd18: begin a_r[127:120]<=rx_byte;frm<=7'd19; end
                7'd19: begin a_r[135:128]<=rx_byte;frm<=7'd20; end
                7'd20: begin a_r[143:136]<=rx_byte;frm<=7'd21; end
                7'd21: begin a_r[151:144]<=rx_byte;frm<=7'd22; end
                7'd22: begin a_r[159:152]<=rx_byte;frm<=7'd23; end
                7'd23: begin a_r[167:160]<=rx_byte;frm<=7'd24; end
                7'd24: begin a_r[175:168]<=rx_byte;frm<=7'd25; end
                7'd25: begin a_r[183:176]<=rx_byte;frm<=7'd26; end
                7'd26: begin a_r[191:184]<=rx_byte;frm<=7'd27; end
                7'd27: begin a_r[199:192]<=rx_byte;frm<=7'd28; end
                7'd28: begin a_r[207:200]<=rx_byte;frm<=7'd29; end
                7'd29: begin a_r[215:208]<=rx_byte;frm<=7'd30; end
                7'd30: begin a_r[223:216]<=rx_byte;frm<=7'd31; end
                7'd31: begin a_r[231:224]<=rx_byte;frm<=7'd32; end
                7'd32: begin a_r[239:232]<=rx_byte;frm<=7'd33; end
                7'd33: begin a_r[247:240]<=rx_byte;frm<=7'd34; end
                7'd34: begin a_r[255:248]<=rx_byte;frm<=7'd35; end
                7'd35: begin b_r[7:0]<=rx_byte;frm<=7'd36; end
                7'd36: begin b_r[15:8]<=rx_byte;frm<=7'd37; end
                7'd37: begin b_r[23:16]<=rx_byte;frm<=7'd38; end
                7'd38: begin b_r[31:24]<=rx_byte;frm<=7'd39; end
                7'd39: begin b_r[39:32]<=rx_byte;frm<=7'd40; end
                7'd40: begin b_r[47:40]<=rx_byte;frm<=7'd41; end
                7'd41: begin b_r[55:48]<=rx_byte;frm<=7'd42; end
                7'd42: begin b_r[63:56]<=rx_byte;frm<=7'd43; end
                7'd43: begin b_r[71:64]<=rx_byte;frm<=7'd44; end
                7'd44: begin b_r[79:72]<=rx_byte;frm<=7'd45; end
                7'd45: begin b_r[87:80]<=rx_byte;frm<=7'd46; end
                7'd46: begin b_r[95:88]<=rx_byte;frm<=7'd47; end
                7'd47: begin b_r[103:96]<=rx_byte;frm<=7'd48; end
                7'd48: begin b_r[111:104]<=rx_byte;frm<=7'd49; end
                7'd49: begin b_r[119:112]<=rx_byte;frm<=7'd50; end
                7'd50: begin b_r[127:120]<=rx_byte;frm<=7'd51; end
                7'd51: begin b_r[135:128]<=rx_byte;frm<=7'd52; end
                7'd52: begin b_r[143:136]<=rx_byte;frm<=7'd53; end
                7'd53: begin b_r[151:144]<=rx_byte;frm<=7'd54; end
                7'd54: begin b_r[159:152]<=rx_byte;frm<=7'd55; end
                7'd55: begin b_r[167:160]<=rx_byte;frm<=7'd56; end
                7'd56: begin b_r[175:168]<=rx_byte;frm<=7'd57; end
                7'd57: begin b_r[183:176]<=rx_byte;frm<=7'd58; end
                7'd58: begin b_r[191:184]<=rx_byte;frm<=7'd59; end
                7'd59: begin b_r[199:192]<=rx_byte;frm<=7'd60; end
                7'd60: begin b_r[207:200]<=rx_byte;frm<=7'd61; end
                7'd61: begin b_r[215:208]<=rx_byte;frm<=7'd62; end
                7'd62: begin b_r[223:216]<=rx_byte;frm<=7'd63; end
                7'd63: begin b_r[231:224]<=rx_byte;frm<=7'd64; end
                7'd64: begin b_r[239:232]<=rx_byte;frm<=7'd65; end
                7'd65: begin b_r[247:240]<=rx_byte;frm<=7'd66; end
                7'd66: begin b_r[255:248]<=rx_byte;frm<=7'd67; end
                7'd67: begin c_r[7:0]<=rx_byte;frm<=7'd68; end
                7'd68: begin c_r[15:8]<=rx_byte;frm<=7'd69; end
                7'd69: begin c_r[23:16]<=rx_byte;frm<=7'd70; end
                7'd70: begin c_r[31:24]<=rx_byte;frm<=7'd71; end
                7'd71: begin c_r[39:32]<=rx_byte;frm<=7'd72; end
                7'd72: begin c_r[47:40]<=rx_byte;frm<=7'd73; end
                7'd73: begin c_r[55:48]<=rx_byte;frm<=7'd74; end
                7'd74: begin c_r[63:56]<=rx_byte;frm<=7'd75; end
                7'd75: begin c_r[71:64]<=rx_byte;frm<=7'd76; end
                7'd76: begin c_r[79:72]<=rx_byte;frm<=7'd77; end
                7'd77: begin c_r[87:80]<=rx_byte;frm<=7'd78; end
                7'd78: begin c_r[95:88]<=rx_byte;frm<=7'd79; end
                7'd79: begin c_r[103:96]<=rx_byte;frm<=7'd80; end
                7'd80: begin c_r[111:104]<=rx_byte;frm<=7'd81; end
                7'd81: begin c_r[119:112]<=rx_byte;frm<=7'd82; end
                7'd82: begin c_r[127:120]<=rx_byte;frm<=7'd83; end
                7'd83: begin c_r[135:128]<=rx_byte;frm<=7'd84; end
                7'd84: begin c_r[143:136]<=rx_byte;frm<=7'd85; end
                7'd85: begin c_r[151:144]<=rx_byte;frm<=7'd86; end
                7'd86: begin c_r[159:152]<=rx_byte;frm<=7'd87; end
                7'd87: begin c_r[167:160]<=rx_byte;frm<=7'd88; end
                7'd88: begin c_r[175:168]<=rx_byte;frm<=7'd89; end
                7'd89: begin c_r[183:176]<=rx_byte;frm<=7'd90; end
                7'd90: begin c_r[191:184]<=rx_byte;frm<=7'd91; end
                7'd91: begin c_r[199:192]<=rx_byte;frm<=7'd92; end
                7'd92: begin c_r[207:200]<=rx_byte;frm<=7'd93; end
                7'd93: begin c_r[215:208]<=rx_byte;frm<=7'd94; end
                7'd94: begin c_r[223:216]<=rx_byte;frm<=7'd95; end
                7'd95: begin c_r[231:224]<=rx_byte;frm<=7'd96; end
                7'd96: begin c_r[239:232]<=rx_byte;frm<=7'd97; end
                7'd97: begin c_r[247:240]<=rx_byte;frm<=7'd98; end
                7'd98: begin c_r[255:248]<=rx_byte;frm<=7'd99; end
                7'd99: begin frame_valid<=1;frm<=0; end
                default: frm<=0;
            endcase end
        end
    end
    assign led[1]=frame_valid;

    // Stage 1: MUL
    reg [255:0] a_reg, b_reg; reg mul_trigger;
    wire mul_in_ready, mul_out_valid; wire [255:0] mul_result;
    gf_mul_param #(.EXP_BITS(97), .MANT_BITS(158), .HAS_INF(1)) u_mul (
        .clk(mclk), .rst(rst),
        .in_valid(mul_trigger), .in_a(a_reg), .in_b(b_reg), .in_ready(mul_in_ready),
        .out_valid(mul_out_valid), .out_y(mul_result), .out_ready(1'b1)
    );
    // Stage 2: ADD
    reg [255:0] c_reg; reg add_trigger;
    wire add_in_ready, add_out_valid; wire [255:0] add_result;
    gf_adder_param #(.EXP_BITS(97), .MANT_BITS(158), .HAS_INF(1)) u_add (
        .clk(mclk), .rst(rst),
        .in_valid(add_trigger), .in_a(mul_result), .in_b(c_reg), .in_ready(add_in_ready),
        .out_valid(add_out_valid), .out_y(add_result), .out_ready(1'b1)
    );
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;b_reg<=0;c_reg<=0;mul_trigger<=0;add_trigger<=0; end
        else begin mul_trigger<=frame_valid; if(frame_valid) begin a_reg<=a_r;b_reg<=b_r;c_reg<=c_r; end
            add_trigger<=mul_out_valid; end
    end
    reg [255:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0; result_ready<=0; end
        else begin result_ready <= add_out_valid; if(add_out_valid) result_reg <= add_result; end
    end
    assign led[2] = |result_reg;

    // ---- UART TX (shift-register, 33 bytes) ----
    localparam [5:0] TX_LEN = 33;
    reg responding; reg [5:0] tx_cnt;
    reg [263:0] tx_shift;
    // Wide result: {result, A5}
    wire [263:0] tx_load = {result_reg, 8'hA5};
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    wire [7:0] cur_byte;
    always @(*) begin
        if(!responding) cur_byte = 8'hFF;
        else cur_byte = tx_shift[7:0];
    end
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_cnt<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_shift<=tx_load;
                tx_cnt<=0;
                responding<=1;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        tsr<={1'b1,cur_byte,1'b0};
                        tx_shift<={8'h00,tx_shift[263:8]};
                        if(tx_cnt==TX_LEN-1) responding<=0; else tx_cnt<=tx_cnt+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
endmodule
`default_nettype wire
