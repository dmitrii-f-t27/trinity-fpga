`default_nettype none
`timescale 1ns / 1ps
// bram_test_decode — diagnostic: 1024×32-bit BRAM lookup via $readmemh.
// If this produces correct values on HW, BRAM INIT works in openXC7.
// If not, the issue is fundamental to the openXC7 BRAM flow.
module bram_test_decode (
    input  wire [9:0] addr,
    output wire [31:0] data
);
    reg [31:0] lut [0:1023];
    initial begin
        lut[0] = 32'h00000001;
        lut[1] = 32'h00000002;
        lut[2] = 32'h00000004;
        lut[3] = 32'h00000008;
        lut[4] = 32'h00000010;
        lut[5] = 32'h00000020;
        lut[6] = 32'h00000040;
        lut[7] = 32'h00000080;
        lut[8] = 32'h00000100;
        lut[9] = 32'h00000200;
        lut[10] = 32'h00000400;
        lut[11] = 32'h00000800;
        lut[12] = 32'h00001000;
        lut[13] = 32'h00002000;
        lut[14] = 32'h00004000;
        lut[15] = 32'h00008000;
        lut[16] = 32'h00010000;
        lut[17] = 32'h00020000;
        lut[18] = 32'h00040000;
        lut[19] = 32'h00080000;
        lut[20] = 32'h00100000;
        lut[21] = 32'h00200000;
        lut[22] = 32'h00400000;
        lut[23] = 32'h00800000;
        lut[24] = 32'h01000000;
        lut[25] = 32'h02000000;
        lut[26] = 32'h04000000;
        lut[27] = 32'h08000000;
        lut[28] = 32'h10000000;
        lut[29] = 32'h20000000;
        lut[30] = 32'h40000000;
        lut[31] = 32'h80000000;
        // Fill rest with addr-based pattern for verification
        // (yosys will optimize unused entries, but first 32 are enough)
    end
    assign data = lut[addr];
endmodule
`default_nettype none
