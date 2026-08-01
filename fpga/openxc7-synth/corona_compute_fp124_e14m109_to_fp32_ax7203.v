`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_fp124_e14m109_to_fp32_ax7203 — FP124_E14M109 TO_FP32 on AX7203.
module corona_compute_fp124_e14m109_to_fp32_ax7203 (
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

    reg [4:0] frm; reg [7:0] fmt_r; reg [123:0] a_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;a_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                5'd0: frm<=(rx_byte==8'hAA)?5'd1:5'd0;
                5'd1: frm<=(rx_byte==8'h55)?5'd2:5'd0;
                5'd2: begin fmt_r<=rx_byte;frm<=5'd3; end
                5'd3: begin a_r[7:0]<=rx_byte;frm<=5'd4; end
                5'd4: begin a_r[15:8]<=rx_byte;frm<=5'd5; end
                5'd5: begin a_r[23:16]<=rx_byte;frm<=5'd6; end
                5'd6: begin a_r[31:24]<=rx_byte;frm<=5'd7; end
                5'd7: begin a_r[39:32]<=rx_byte;frm<=5'd8; end
                5'd8: begin a_r[47:40]<=rx_byte;frm<=5'd9; end
                5'd9: begin a_r[55:48]<=rx_byte;frm<=5'd10; end
                5'd10: begin a_r[63:56]<=rx_byte;frm<=5'd11; end
                5'd11: begin a_r[71:64]<=rx_byte;frm<=5'd12; end
                5'd12: begin a_r[79:72]<=rx_byte;frm<=5'd13; end
                5'd13: begin a_r[87:80]<=rx_byte;frm<=5'd14; end
                5'd14: begin a_r[95:88]<=rx_byte;frm<=5'd15; end
                5'd15: begin a_r[103:96]<=rx_byte;frm<=5'd16; end
                5'd16: begin a_r[111:104]<=rx_byte;frm<=5'd17; end
                5'd17: begin a_r[119:112]<=rx_byte;frm<=5'd18; end
                5'd18: begin a_r[123:120]<=rx_byte;frm<=5'd19; end
                5'd19: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;

    reg [123:0] a_reg; reg conv_trigger;
    wire [123:0] fmt_a = a_reg;
    wire f_sign_a = fmt_a[123];
    wire [13:0] f_exp_a = fmt_a[122:109];
    wire [108:0] f_mant_a = fmt_a[108:0];
    wire f_zero_a = (f_exp_a == 0) && ((f_mant_a == 0));
    wire f_inf_a = (f_exp_a == 16383) && ((f_mant_a == 0));
    wire f_nan_a = (f_exp_a == 16383) && ((f_mant_a != 0));
    wire f_sub_a = (f_exp_a == 0) && ((f_mant_a != 0));
    wire signed [23:0] f_de_a = $signed({1'b0, f_exp_a}) - 24'sd8191 + 24'sd127;
    wire [7:0] f_exp32_a = (f_de_a > 24'sd254) ? 8'd254 : (f_de_a < 0) ? 8'd0 : f_de_a[7:0];
    wire [22:0] f_mant32_a = {f_mant_a, -86'b0};
    wire [22:0] f_mant32_norm_a = f_mant_a;
    reg [31:0] fp32_a;
    always @(*) begin
        if(f_zero_a) fp32_a=32'h00000000;
        else if(f_inf_a) fp32_a=f_sign_a?32'hFF800000:32'h7F800000;
        else if(f_nan_a) fp32_a=32'h7FC00000;
        else if(f_sub_a) fp32_a={f_sign_a, 8'd0, f_mant32_norm_a};
        else fp32_a={f_sign_a, f_exp32_a, f_mant32_a};
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
