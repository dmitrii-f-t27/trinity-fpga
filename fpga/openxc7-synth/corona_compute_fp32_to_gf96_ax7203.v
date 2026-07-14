`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_fp32_to_gf96_ax7203 — IEEE binary32 to GF96 converter.
// Output: GF96 [S:1][E:36][M:59]
module corona_compute_fp32_to_gf96_ax7203 (
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


    // ---- Frame FSM: AA 55 fmt a0 a1 a2 a3 trig ----
    reg [3:0] frm; reg [7:0] fmt_r; reg [31:0] a_r; reg frame_valid;
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
                4'd7: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [31:0] a_reg; reg conv_trigger;
    wire fp_sign = a_reg[31];
    wire [7:0] fp_exp = a_reg[30:23];
    wire [22:0] fp_mant = a_reg[22:0];
    wire fp_zero = (fp_exp==0) && (fp_mant==0);
    wire fp_inf = (fp_exp==8'b11111111) && (fp_mant==0);
    wire fp_nan = (fp_exp==8'b11111111) && (fp_mant!=0);
    wire fp_denorm = (fp_exp==0) && (fp_mant!=0);
    wire signed [37:0] gf_exp_calc = $signed({2'b0, fp_exp}) + 38'sd34359738240;
    wire overflow = (gf_exp_calc > 38'sd68719476734);
    wire underflow = (gf_exp_calc < 38'sd1);
    wire [58:0] gf_mant_trunc = fp_mant[22:-36];
    reg [95:0] gf_result;
    always @(*) begin
        if(fp_nan) gf_result = {1'b0, {36{1'b1}}, {58{1'b0}}, 1'b1};
        else if(fp_inf || overflow) gf_result = {fp_sign, {36{1'b1}}, {59{1'b0}}};
        else if(fp_zero || fp_denorm || underflow) gf_result = {fp_sign, {36{1'b0}}, {59{1'b0}}};
        else gf_result = {fp_sign, gf_exp_calc[35:0], gf_mant_trunc};
    end
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;conv_trigger<=0; end
        else begin conv_trigger<=frame_valid; if(frame_valid) a_reg<=a_r; end
    end
    reg [95:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=conv_trigger; if(conv_trigger) result_reg<=gf_result; end
    end
    assign led[2] = |result_reg;

    // ---- UART TX (shift-register, 13 bytes) ----
    localparam [3:0] TX_LEN = 13;
    // TX: buffer+mux (no conflicting NBA — fixes tx race). 13 bytes sliced from tx_load[103:0].
    wire [103:0] tx_load = {result_reg, 8'hA5};
    reg responding; reg [3:0] tx_idx; reg [7:0] tx_buf0, tx_buf1, tx_buf2, tx_buf3, tx_buf4, tx_buf5, tx_buf6, tx_buf7, tx_buf8, tx_buf9, tx_buf10, tx_buf11, tx_buf12;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF; tx_buf1<=8'hFF; tx_buf2<=8'hFF; tx_buf3<=8'hFF; tx_buf4<=8'hFF; tx_buf5<=8'hFF; tx_buf6<=8'hFF; tx_buf7<=8'hFF; tx_buf8<=8'hFF; tx_buf9<=8'hFF; tx_buf10<=8'hFF; tx_buf11<=8'hFF; tx_buf12<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=tx_load[7:0]; tx_buf1<=tx_load[15:8]; tx_buf2<=tx_load[23:16]; tx_buf3<=tx_load[31:24]; tx_buf4<=tx_load[39:32]; tx_buf5<=tx_load[47:40]; tx_buf6<=tx_load[55:48]; tx_buf7<=tx_load[63:56]; tx_buf8<=tx_load[71:64]; tx_buf9<=tx_load[79:72]; tx_buf10<=tx_load[87:80]; tx_buf11<=tx_load[95:88]; tx_buf12<=tx_load[103:96]; responding<=1; tx_idx<=0;
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
                            4'd9: tsr<={1'b1,tx_buf9,1'b0};
                            4'd10: tsr<={1'b1,tx_buf10,1'b0};
                            4'd11: tsr<={1'b1,tx_buf11,1'b0};
                            4'd12: tsr<={1'b1,tx_buf12,1'b0};
                        endcase
                        if(tx_idx==12) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
    endmodule
`default_nettype wire
