`default_nettype none
`timescale 1ns / 1ps
// takum16_decode — takum16 (Hunhold 2024 logarithmic, arXiv:2404.18603) -> FP32
// via a 65536-entry BRAM LUT. LUT precomputed offline by replicating the t27
// verified second-witness (value = (-1)^S * exp(ell/2), ell=(1-2S)(c+m)) and
// rounding to binary32 RNE; stored in takum16_lut.mem ($readmemh at synth).
// BRAM-based -> trivial to route (no wide logic datapath).
module takum16_decode (
    input  wire [15:0] takum16_in,
    output reg  [31:0] fp32_out
);
    reg [31:0] lut [0:65535];
    initial $readmemh("fpga/openxc7-synth/takum16_lut.mem", lut);
    always @* fp32_out = lut[takum16_in];
endmodule
`default_nettype none
