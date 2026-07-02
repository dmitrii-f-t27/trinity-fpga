`default_nettype none
`timescale 1ns / 1ps
// quad_double_decode — Bailey/Hida quad-double (4x IEEE-754 binary64) -> binary32.
// value = exact sum of l1..l4 (l1=qd[63:0]..l4=qd[255:192]); round RNE to binary32.
// Clean scale: value_limb = mant53 * 2^eu (mant53={1,mant}, eu=e-1075 / -1074 subnormal).
// Align each mant53 >> (emax-eu) into a wide field; signed-accumulate; e2 = emax + msb(acc).
module quad_double_decode (input wire [255:0] qd, output reg [31:0] fp32_out);
    wire [63:0] l1=qd[63:0], l2=qd[127:64], l3=qd[191:128], l4=qd[255:192];
    wire [10:0] e1=l1[62:52], e2=l2[62:52], e3=l3[62:52], e4=l4[62:52];
    wire [51:0] m1=l1[51:0], m2=l2[51:0], m3=l3[51:0], m4=l4[51:0];
    wire s1=l1[63], s2=l2[63], s3=l3[63], s4=l4[63];
    wire n1=(e1=='h7FF)&(|m1), n2=(e2=='h7FF)&(|m2), n3=(e3=='h7FF)&(|m3), n4=(e4=='h7FF)&(|m4);
    wire i1=(e1=='h7FF)&~(|m1), i2=(e2=='h7FF)&~(|m2), i3=(e3=='h7FF)&~(|m3), i4=(e4=='h7FF)&~(|m4);
    wire z1=(e1==0)&~(|m1), z2=(e2==0)&~(|m2), z3=(e3==0)&~(|m3), z4=(e4==0)&~(|m4);
    wire [52:0] M1=(e1==0)?{1'b0,m1}:{1'b1,m1}, M2=(e2==0)?{1'b0,m2}:{1'b1,m2},
                M3=(e3==0)?{1'b0,m3}:{1'b1,m3}, M4=(e4==0)?{1'b0,m4}:{1'b1,m4};
    wire signed [13:0] eu1=(e1==0)?-14'sd1074:($signed({3'b0,e1})-14'sd1075);
    wire signed [13:0] eu2=(e2==0)?-14'sd1074:($signed({3'b0,e2})-14'sd1075);
    wire signed [13:0] eu3=(e3==0)?-14'sd1074:($signed({3'b0,e3})-14'sd1075);
    wire signed [13:0] eu4=(e4==0)?-14'sd1074:($signed({3'b0,e4})-14'sd1075);
    wire signed [13:0] e12=(eu1>eu2)?eu1:eu2, e34=(eu3>eu4)?eu3:eu4;
    wire signed [13:0] emax=(e12>e34)?e12:e34;

    // align mant53 >> (emax-eu) into 58-bit field (mant53<<5 then >>shift keeps guard bits);
    // sticky from fully-shifted-out.
    function [58:0] aln;
        input [52:0] mant; input signed [13:0] eu; input signed [13:0] em;
        reg [57:0] sh; reg stb; integer sh_amt;
        begin
            sh_amt = em - eu;
            if (sh_amt <= 0) begin sh = {mant, 5'b0} << (-sh_amt); stb = 1'b0; end
            else if (sh_amt >= 58) begin sh = 0; stb = |mant; end
            else begin sh = ({mant, 5'b0} >> sh_amt); stb = |( {mant,5'b0} & ((58'h1<<sh_amt)-1) ); end
            aln = {sh, stb};
        end
    endfunction
    wire [58:0] a1=aln(M1,eu1,emax), a2=aln(M2,eu2,emax), a3=aln(M3,eu3,emax), a4=aln(M4,eu4,emax);
    wire signed [61:0] acc =
        (z1?62'sd0:(s1?-$signed({1'b0,a1[58:1]}):$signed({1'b0,a1[58:1]}))) +
        (z2?62'sd0:(s2?-$signed({1'b0,a2[58:1]}):$signed({1'b0,a2[58:1]}))) +
        (z3?62'sd0:(s3?-$signed({1'b0,a3[58:1]}):$signed({1'b0,a3[58:1]}))) +
        (z4?62'sd0:(s4?-$signed({1'b0,a4[58:1]}):$signed({1'b0,a4[58:1]})));
    wire stb_all = a1[0]|a2[0]|a3[0]|a4[0];

    integer k, msb; reg [61:0] am; reg signed [15:0] bres;
    always @* begin
        am = acc[61] ? (~acc + 1) : acc;
        msb = -1; for (k=61;k>=0;k=k-1) if (am[k] && msb==-1) msb=k;
        bres = (msb<0) ? 0 : (emax + (msb - 5));
    end
    reg [61:0] shf; reg [24:0] mant25; reg guard,rnd,stb,round_up; reg [23:0] mant24;
    always @* begin
        if (msb>=25) shf = am >> (msb-25); else shf = am << (25-msb);
        guard=shf[1]; rnd=shf[0];
        stb = stb_all | (msb>=26 ? |(am << (61-(msb-26))) : 1'b0);
        mant25={1'b0,shf[25:2]};
        round_up = guard & (rnd|stb|mant25[0]);
        if (round_up) mant25=mant25+1;
        if (mant25[24]) begin mant24=24'h800000; bres=bres+1; end
        else mant24=mant25[23:0];
    end
    wire rsign = acc[61];
    always @* begin
        fp32_out = 32'h7FC00000;
        if (n1|n2|n3|n4) fp32_out = 32'h7FC00000;
        else if (i1|i2|i3|i4) begin
            if (((i1&~s1)|(i2&~s2)|(i3&~s3)|(i4&~s4)) && ((i1&s1)|(i2&s2)|(i3&s3)|(i4&s4)))
                fp32_out = 32'h7FC00000;                                  // +inf and -inf -> NaN
            else if ((i1&~s1)|(i2&~s2)|(i3&~s3)|(i4&~s4)) fp32_out = 32'h7F800000;  // +inf
            else fp32_out = 32'hFF800000;                                            // -inf
        end
        else begin
            if (bres>16'sd127) fp32_out = {rsign,8'hFF,23'h0};
            else if (bres<-16'sd150) fp32_out = {rsign,31'h0};
            else if (bres<-16'sd126) begin
                if (bres>=-16'sd149) fp32_out = {rsign,8'h00,23'h000001};
                else fp32_out = {rsign,31'b0};
            end else fp32_out = {rsign, bres[7:0]+8'd127, mant24[22:0]};
        end
    end
endmodule
`default_nettype none
