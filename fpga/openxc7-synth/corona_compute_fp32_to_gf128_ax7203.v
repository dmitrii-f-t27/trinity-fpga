`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_fp32_to_gf128_ax7203 — IEEE binary32 to GF128 converter.
// Output: GF128 [S:1][E:49][M:78]
module corona_compute_fp32_to_gf128_ax7203 (
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
    wire signed [50:0] gf_exp_calc = $signed({2'b0, fp_exp}) + 51'sd281474976710528;
    wire overflow = (gf_exp_calc > 51'sd562949953421310);
    wire underflow = (gf_exp_calc < 51'sd1);
    wire [77:0] gf_mant_trunc = fp_mant[22:-55];
    reg [127:0] gf_result;
    always @(*) begin
        if(fp_nan) gf_result = {1'b0, {49{1'b1}}, {77{1'b0}}, 1'b1};
        else if(fp_inf || overflow) gf_result = {fp_sign, {49{1'b1}}, {78{1'b0}}};
        else if(fp_zero || fp_denorm || underflow) gf_result = {fp_sign, {49{1'b0}}, {78{1'b0}}};
        else gf_result = {fp_sign, gf_exp_calc[48:0], gf_mant_trunc};
    end
    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0;conv_trigger<=0; end
        else begin conv_trigger<=frame_valid; if(frame_valid) a_reg<=a_r; end
    end
    reg [127:0] result_reg; reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0;result_ready<=0; end
        else begin result_ready<=conv_trigger; if(conv_trigger) result_reg<=gf_result; end
    end
    assign led[2] = |result_reg;

    // ---- UART TX (shift-register, 17 bytes) ----
    localparam [4:0] TX_LEN = 17;
    reg responding; reg [4:0] tx_cnt;
    reg [135:0] tx_shift;
    // Wide result: {result, A5}
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
