`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_gf128_cmp_ax7203 — GoldenFloat128 comparison on AX7203.
// GF128: [S:1][E:49][M:78] = 128 bits, HAS_INF=0.
// op: 0x00=EQ, 0x01=LT, 0x02=LE
module corona_compute_gf128_cmp_ax7203 (
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
    reg [5:0] frm; reg [7:0] fmt_r, op_r; reg [127:0] a_r, b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;op_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                6'd0: frm<=(rx_byte==8'hAA)?6'd1:6'd0;
                6'd1: frm<=(rx_byte==8'h55)?6'd2:6'd0;
                6'd2: begin fmt_r<=rx_byte;frm<=6'd3; end
                6'd3: begin op_r<=rx_byte;frm<=6'd4; end
                6'd4: begin a_r[7:0]<=rx_byte;frm<=6'd5; end
                6'd5: begin a_r[15:8]<=rx_byte;frm<=6'd6; end
                6'd6: begin a_r[23:16]<=rx_byte;frm<=6'd7; end
                6'd7: begin a_r[31:24]<=rx_byte;frm<=6'd8; end
                6'd8: begin a_r[39:32]<=rx_byte;frm<=6'd9; end
                6'd9: begin a_r[47:40]<=rx_byte;frm<=6'd10; end
                6'd10: begin a_r[55:48]<=rx_byte;frm<=6'd11; end
                6'd11: begin a_r[63:56]<=rx_byte;frm<=6'd12; end
                6'd12: begin a_r[71:64]<=rx_byte;frm<=6'd13; end
                6'd13: begin a_r[79:72]<=rx_byte;frm<=6'd14; end
                6'd14: begin a_r[87:80]<=rx_byte;frm<=6'd15; end
                6'd15: begin a_r[95:88]<=rx_byte;frm<=6'd16; end
                6'd16: begin a_r[103:96]<=rx_byte;frm<=6'd17; end
                6'd17: begin a_r[111:104]<=rx_byte;frm<=6'd18; end
                6'd18: begin a_r[119:112]<=rx_byte;frm<=6'd19; end
                6'd19: begin a_r[127:120]<=rx_byte;frm<=6'd20; end
                6'd20: begin b_r[7:0]<=rx_byte;frm<=6'd21; end
                6'd21: begin b_r[15:8]<=rx_byte;frm<=6'd22; end
                6'd22: begin b_r[23:16]<=rx_byte;frm<=6'd23; end
                6'd23: begin b_r[31:24]<=rx_byte;frm<=6'd24; end
                6'd24: begin b_r[39:32]<=rx_byte;frm<=6'd25; end
                6'd25: begin b_r[47:40]<=rx_byte;frm<=6'd26; end
                6'd26: begin b_r[55:48]<=rx_byte;frm<=6'd27; end
                6'd27: begin b_r[63:56]<=rx_byte;frm<=6'd28; end
                6'd28: begin b_r[71:64]<=rx_byte;frm<=6'd29; end
                6'd29: begin b_r[79:72]<=rx_byte;frm<=6'd30; end
                6'd30: begin b_r[87:80]<=rx_byte;frm<=6'd31; end
                6'd31: begin b_r[95:88]<=rx_byte;frm<=6'd32; end
                6'd32: begin b_r[103:96]<=rx_byte;frm<=6'd33; end
                6'd33: begin b_r[111:104]<=rx_byte;frm<=6'd34; end
                6'd34: begin b_r[119:112]<=rx_byte;frm<=6'd35; end
                6'd35: begin b_r[127:120]<=rx_byte;frm<=6'd36; end
                6'd36: begin frame_valid<=1;frm<=0; end
                default: frm<=0;
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [127:0] a_reg, b_reg; reg [7:0] op_reg; reg comp_trigger;
    wire sa = a_reg[127];
    wire [48:0] ea = a_reg[126:78];
    wire [77:0] ma = a_reg[77:0];
    wire sb = b_reg[127];
    wire [48:0] eb = b_reg[126:78];
    wire [77:0] mb = b_reg[77:0];
    wire a_zero = (ea == 0) && (ma == 0);
    wire b_zero = (eb == 0) && (mb == 0);
    wire a_nan = (ea == {49{1'b1}}) && (ma != 0);
    wire b_nan = (eb == {49{1'b1}}) && (mb != 0);
    wire [126:0] abs_a = {ea, ma};
    wire [126:0] abs_b = {eb, mb};
    wire mag_lt = (abs_a < abs_b); wire mag_eq = (abs_a == abs_b);
    wire cmp_eq = (a_zero && b_zero) || ((sa == sb) && ((a_zero && b_zero) || mag_eq));
    wire both_neg = sa && sb && ~(a_zero && b_zero);
    wire cmp_lt = (a_nan | b_nan) ? 1'b0 :
                  (a_zero && b_zero) ? 1'b0 :
                  (sa && ~sb) ? 1'b1 :
                  (~sa && sb) ? 1'b0 :
                  both_neg ? (abs_a > abs_b) : mag_lt;
    wire cmp_le = cmp_lt | cmp_eq;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;b_reg<=0;op_reg<=0;comp_trigger<=0; end
        else begin comp_trigger<=frame_valid; if(frame_valid) begin a_reg<=a_r;b_reg<=b_r;op_reg<=op_r; end end
    end
    wire cmp_result = (op_reg==8'h00) ? cmp_eq : (op_reg==8'h01) ? cmp_lt : (op_reg==8'h02) ? cmp_le : 1'b0;
    reg [7:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0; result_ready<=0; end
        else begin result_ready <= comp_trigger; if(comp_trigger) result_reg <= cmp_result ? 8'h01 : 8'h00; end
    end
    assign led[2] = result_reg[0];

    // ---- UART TX (shift-register, 5 bytes) ----
    localparam [2:0] TX_LEN = 5;
    reg responding; reg [2:0] tx_cnt;
    reg [135:0] tx_shift;
    // CMP result: {padding, result, A5}
    wire [135:0] tx_load = {result_reg, 8'hA5};
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
                        tx_shift<={8'h00,tx_shift[135:8]};
                        if(tx_cnt==TX_LEN-1) responding<=0; else tx_cnt<=tx_cnt+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
endmodule
`default_nettype wire
