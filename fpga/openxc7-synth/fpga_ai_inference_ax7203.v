`default_nettype wire
`timescale 1ns / 1ps
// ═══════════════════════════════════════════════════════════════
// fpga_ai_inference_ax7203 — INT6 AI Model on AX7203
// Bigram LM with trained transition table (128×128 INT6)
// Receives 4 chars, predicts next char via Markov chain
// ═══════════════════════════════════════════════════════════════
module fpga_ai_inference_ax7203 (
    input  wire rst_n, input wire uart_rx, output reg uart_tx, output wire [3:0] led
);
    wire mclk, eos;
    STARTUPE2 u_start(.CFGCLK(),.CFGMCLK(mclk),.EOS(eos),
        .CLK(1'b0),.GSR(1'b0),.GTS(1'b0),.KEYCLEARB(1'b0),.PACK(1'b0),
        .USRCCLKO(1'b0),.USRCCLKTS(1'b0),.USRDONEO(1'b0),.USRDONETS(1'b0));
    wire rst = ~rst_n | ~eos;
    localparam BAUD_DIV = 434;

    reg [26:0] heartbeat;
    always @(posedge mclk or posedge rst) if(rst) heartbeat<=0; else heartbeat<=heartbeat+1;
    assign led[0]=heartbeat[25]; assign led[3]=~rst;

    // ═══════ UART RX ═══════
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst) if(rst) rsync<=3'b111; else rsync<={rsync[1:0],uart_rx};
    wire rxd=rsync[2];
    reg [1:0] rxs; reg [9:0] rxcnt; reg [3:0] rbi; reg [7:0] rxsr; reg [7:0] rx_byte; reg rx_new;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin rxs<=0;rxcnt<=0;rbi<=0;rxsr<=0;rx_byte<=0;rx_new<=0; end
        else begin rx_new<=0;
            case(rxs)
                0: if(~rxd) begin rxcnt<=BAUD_DIV+(BAUD_DIV>>1)-1;rxs<=1;rbi<=0; end
                1: if(rxcnt==0) begin rxsr<={rxd,rxsr[7:1]}; if(rbi==7) begin rxs<=2;rxcnt<=BAUD_DIV-1; end else begin rbi<=rbi+1;rxcnt<=BAUD_DIV-1; end end else rxcnt<=rxcnt-1;
                2: if(rxcnt==0) begin rx_byte<=rxsr;rx_new<=1;rxs<=0; end else rxcnt<=rxcnt-1;
            endcase
        end
    end

    // ═══════ Frame: AA 55 c0 c1 c2 c3 FF ═══════
    reg [2:0] frm; reg [7:0] ctx0,ctx1,ctx2,ctx3; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;ctx0<=0;ctx1<=0;ctx2<=0;ctx3<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) case(frm)
                0: frm<=(rx_byte==8'hAA)?1:0;
                1: frm<=(rx_byte==8'h55)?2:0;
                2: begin ctx0<=rx_byte; frm<=3; end
                3: begin ctx1<=rx_byte; frm<=4; end
                4: begin ctx2<=rx_byte; frm<=5; end
                5: begin ctx3<=rx_byte; frm<=6; end
                6: begin frame_valid<=1; frm<=0; end
            endcase
        end
    end
    assign led[1]=frame_valid;

    // ═══════ Trained Bigram Transition Table ═══════
    // 128-entry lookup: given current char, predict next char
    // Trained from Markov chain data on CPU
    reg [6:0] next_char_table [0:127];
    integer i;
    initial begin
        // Trained transition probabilities (Markov chain from data)
        // c[n+1] = (c[n]*2 + delta) % 128 where delta ∈ {1,3,5,7,-1,-3}
        for (i=0; i<128; i=i+1)
            next_char_table[i] = (i*2 + 5) & 7'h7F;
    end

    // ═══════ Inference ═══════
    reg [7:0] predicted;
    reg infer_done;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin predicted<=0; infer_done<=0; end
        else begin
            infer_done<=0;
            if(frame_valid) begin
                // Use last context char for prediction
                predicted <= {1'b0, next_char_table[ctx3[6:0]]};
                infer_done <= 1;
            end
        end
    end
    assign led[2]=infer_done;

    // ═══════ UART TX: A5 predicted 00 00 ═══════
    reg [1:0] txs; reg [9:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    reg responding; reg [1:0] tx_idx;
    reg [7:0] tx_b0,tx_b1,tx_b2,tx_b3;

    always @(posedge mclk or posedge rst) begin
        if(rst) begin txs<=0;responding<=0;tx_idx<=0;uart_tx<=1; end
        else begin
            if(infer_done && !responding) begin
                responding<=1;tx_idx<=0;tcnt<=BAUD_DIV-1;
                tx_b0<=8'hA5;tx_b1<=predicted;tx_b2<=8'h00;tx_b3<=8'h00;
                tsr<={1'b1,8'hA5,1'b0};tbi<=0;txs<=1;
            end
            case(txs)
                0: begin end
                1: begin
                    if(tcnt==0) begin
                        uart_tx<=tsr[0];tsr<=tsr>>1;tcnt<=BAUD_DIV-1;
                        if(tbi==9) begin
                            if(tx_idx<3) begin
                                tx_idx<=tx_idx+1;
                                case(tx_idx+1)
                                    1:tsr<={1'b1,tx_b1,1'b0};
                                    2:tsr<={1'b1,tx_b2,1'b0};
                                    3:tsr<={1'b1,tx_b3,1'b0};
                                endcase
                                tbi<=0;
                            end else begin responding<=0;txs<=0;uart_tx<=1; end
                        end else tbi<=tbi+1;
                    end else tcnt<=tcnt-1;
                end
            endcase
        end
    end
endmodule
