// Dump fp8_e4m3_fnuz + posit8 decoder outputs (all 256 codes each) for 2-oracle
// cross-check vs the Python golden. Local iverilog only.
`timescale 1ns/1ps
`default_nettype none
module corona_fp8_posit8_dump_tb;
    reg  [7:0] code;
    wire [31:0] fp8_out, posit_out;
    wire fp8_z, fp8_nan, posit_z, posit_nar;
    integer fd, c;
    fp8_e4m3_fnuz_decode u_fp8  (.e4m3_in(code), .fp32_out(fp8_out),   .is_zero(fp8_z),   .is_nan(fp8_nan));
    posit8_decode          u_posit(.posit_in(code),.fp32_out(posit_out), .is_zero(posit_z), .is_nar(posit_nar));
    initial begin
        fd = $fopen("/tmp/corona_fp8_posit8_dump.txt", "w");
        for (c = 0; c < 256; c = c + 1) begin
            code = c[7:0]; #1;
            $fdisplay(fd, "1 %0d %0d", c, fp8_out);     // fmt=1 = fp8_e4m3_fnuz
            $fdisplay(fd, "4 %0d %0d", c, posit_out);   // fmt=4 = posit8
        end
        $fclose(fd);
        $finish;
    end
endmodule
`default_nettype wire
