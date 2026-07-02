`default_nettype none
`timescale 1ns / 1ps
// decimal64_decode — IEEE 754 decimal64 (BID) -> binary32 (FP32), bit-exact RNE.
// value = (-1)^sign * C * 10^(E-398), RNE to binary32.
// de>=0: exact C*10^de (pow10n).  de<0: C*M[de]*2^-G, M[de]=round(10^de*2^G) (G=210);
//   error < C*2^-(210+1) <= 2^-157 < 0.5*2^-149 -> bit-exact RNE for all magnitudes.
// NO divide (multiply only) -> synth-feasible + sim-fast.
module decimal64_decode (
    input  wire [63:0] bid,
    output reg  [31:0] fp32_out
);
    localparam integer W = 288;
    localparam integer G = 210;

    wire        sign   = bid[63];
    wire [12:0] cf     = bid[62:50];
    wire        top2   = (cf[12:11] == 2'b11);
    wire        topspe = (cf[12:9]  == 4'b1111);
    wire        is_special = top2 & topspe;
    wire        is_nan = is_special &  bid[58];
    wire        is_inf = is_special & ~bid[58];
    wire        caseB  = top2 & ~is_special;
    wire [9:0]  expb   = caseB ? bid[60:51] : bid[62:53];
    wire [53:0] C      = caseB ? {3'b100, bid[50:0]} : {1'b0, bid[52:0]};
    wire signed [11:0] de = $signed({2'b00, expb}) - 12'sd398;

    function [W-1:0] pow10n;
        input integer n; integer i; reg [W-1:0] r;
        begin r = {{W-1 {1'b0}}, 1'b1}; for (i = 0; i < n; i = i + 1) r = r * 64'd10; pow10n = r; end
    endfunction

    function [W-1:0] mp10_neg;        // M[de] = round(10^de * 2^G), de in [-61,-1]
        input signed [11:0] d; reg [W-1:0] Mp10;
        begin
            case (d)
            12'hfc3: Mp10 = 288'h0000000000000000000000000000000000000000000000000000000000000000000000a5;   // de=-61

            12'hfc4: Mp10 = 288'h00000000000000000000000000000000000000000000000000000000000000000000066e;   // de=-60

            12'hfc5: Mp10 = 288'h000000000000000000000000000000000000000000000000000000000000000000004047;   // de=-59

            12'hfc6: Mp10 = 288'h0000000000000000000000000000000000000000000000000000000000000000000282c6;   // de=-58

            12'hfc7: Mp10 = 288'h000000000000000000000000000000000000000000000000000000000000000000191bc1;   // de=-57

            12'hfc8: Mp10 = 288'h000000000000000000000000000000000000000000000000000000000000000000fb1586;   // de=-56

            12'hfc9: Mp10 = 288'h000000000000000000000000000000000000000000000000000000000000000009ced738;   // de=-55

            12'hfca: Mp10 = 288'h00000000000000000000000000000000000000000000000000000000000000006214682d;   // de=-54

            12'hfcb: Mp10 = 288'h0000000000000000000000000000000000000000000000000000000000000003d4cc11c5;   // de=-53

            12'hfcc: Mp10 = 288'h00000000000000000000000000000000000000000000000000000000000000264ff8b1b4;   // de=-52

            12'hfcd: Mp10 = 288'h000000000000000000000000000000000000000000000000000000000000017f1fb6f109;   // de=-51

            12'hfce: Mp10 = 288'h0000000000000000000000000000000000000000000000000000000000000ef73d256a5c;   // de=-50

            12'hfcf: Mp10 = 288'h00000000000000000000000000000000000000000000000000000000000095a863762799;   // de=-49

            12'hfd0: Mp10 = 288'h000000000000000000000000000000000000000000000000000000000005d893e29d8bf6;   // de=-48

            12'hfd1: Mp10 = 288'h00000000000000000000000000000000000000000000000000000000003a75c6da27779c;   // de=-47

            12'hfd2: Mp10 = 288'h00000000000000000000000000000000000000000000000000000000024899c4858aac1c;   // de=-46

            12'hfd3: Mp10 = 288'h0000000000000000000000000000000000000000000000000000000016d601ad376ab91a;   // de=-45

            12'hfd4: Mp10 = 288'h00000000000000000000000000000000000000000000000000000000e45c10c42a2b3b06;   // de=-44

            12'hfd5: Mp10 = 288'h00000000000000000000000000000000000000000000000000000008eb98a7a9a5b04e37;   // de=-43

            12'hfd6: Mp10 = 288'h0000000000000000000000000000000000000000000000000000005933f68ca078e30e2b;   // de=-42

            12'hfd7: Mp10 = 288'h0000000000000000000000000000000000000000000000000000037c07a17e44b8de8dae;   // de=-41

            12'hfd8: Mp10 = 288'h000000000000000000000000000000000000000000000000000022d84c4eeeaf38b188c9;   // de=-40

            12'hfd9: Mp10 = 288'h00000000000000000000000000000000000000000000000000015c72fb1552d836ef57d9;   // de=-39

            12'hfda: Mp10 = 288'h000000000000000000000000000000000000000000000000000d9c7dced53c7225596e7c;   // de=-38

            12'hfdb: Mp10 = 288'h00000000000000000000000000000000000000000000000000881cea14545c75757e50d6;   // de=-37

            12'hfdc: Mp10 = 288'h00000000000000000000000000000000000000000000000005512124cb4b9c9696ef285f;   // de=-36

            12'hfdd: Mp10 = 288'h000000000000000000000000000000000000000000000000352b4b6ff0f41de1e55793b2;   // de=-35

            12'hfde: Mp10 = 288'h00000000000000000000000000000000000000000000000213b0f25f69892ad2f56bc4f0;   // de=-34

            12'hfdf: Mp10 = 288'h000000000000000000000000000000000000000000000014c4e977ba1f5bac3d9635b15d;   // de=-33

            12'hfe0: Mp10 = 288'h0000000000000000000000000000000000000000000000cfb11ead453994ba67de18eda6;   // de=-32

            12'hfe1: Mp10 = 288'h00000000000000000000000000000000000000000000081ceb32c4b43fcf480eacf94877;   // de=-31

            12'hfe2: Mp10 = 288'h0000000000000000000000000000000000000000000051212ffbaf0a7e18d092c1bcd4a7;   // de=-30

            12'hfe3: Mp10 = 288'h000000000000000000000000000000000000000000032b4bdfd4d668ecf825bb91604e81;   // de=-29

            12'hfe4: Mp10 = 288'h0000000000000000000000000000000000000000001fb0f6be50601941b17953adc3110a;   // de=-28

            12'hfe5: Mp10 = 288'h0000000000000000000000000000000000000000013ce9a36f23c0fc90eebd44c99eaa69;   // de=-27

            12'hfe6: Mp10 = 288'h00000000000000000000000000000000000000000c612062576589dda95364afe032a81a;   // de=-26

            12'hfe7: Mp10 = 288'h00000000000000000000000000000000000000007bcb43d769f762a89d41eedec1fa9102;   // de=-25

            12'hfe8: Mp10 = 288'h0000000000000000000000000000000000000004d5f0a66a23a9da96249354b393c9aa17;   // de=-24

            12'hfe9: Mp10 = 288'h00000000000000000000000000000000000000305b66802564a289dd6dc14f03c5e0a4e3;   // de=-23

            12'hfea: Mp10 = 288'h00000000000000000000000000000000000001e392010175ee5962a6498d1625bac670e2;   // de=-22

            12'hfeb: Mp10 = 288'h00000000000000000000000000000000000012e3b40a0e9b4f7dda7edf82dd794bc068d0;   // de=-21

            12'hfec: Mp10 = 288'h000000000000000000000000000000000000bce5086492111aea88f4bb1ca6bcf584181f;   // de=-20

            12'hfed: Mp10 = 288'h00000000000000000000000000000000000760f253edb4ab0d29598f4f1e83619728f133;   // de=-19

            12'hfee: Mp10 = 288'h000000000000000000000000000000000049c97747490eae839d7f99173121cfe7996bfa;   // de=-18

            12'hfef: Mp10 = 288'h0000000000000000000000000000000002e1dea8c8da92d12426fbfae7eb521f0bfe37c0;   // de=-17

            12'hff0: Mp10 = 288'h000000000000000000000000000000001cd2b297d889bc2b6985d7cd0f31353677ee2d83;   // de=-16

            12'hff1: Mp10 = 288'h00000000000000000000000000000001203af9ee756159b21f3a6e0297ec1420af4dc722;   // de=-15

            12'hff2: Mp10 = 288'h0000000000000000000000000000000b424dc35095cd80f538484c19ef38c946d909c750;   // de=-14

            12'hff3: Mp10 = 288'h000000000000000000000000000000709709a125da07099432d2f9035837dcc47a61c91e;   // de=-13

            12'hff4: Mp10 = 288'h00000000000000000000000000000465e6604b7a84465fc9fc3dba21722e9facc7d1db2c;   // de=-12

            12'hff5: Mp10 = 288'h00000000000000000000000000002bfaffc2f2c92abfbde3da69454e75d23cbfce328fb7;   // de=-11

            12'hff6: Mp10 = 288'h0000000000000000000000000001b7cdfd9d7bdbab7d6ae6881cb5109a365f7e0df99d22;   // de=-10

            12'hff7: Mp10 = 288'h00000000000000000000000000112e0be826d694b2e62d01511f12a6061fbaec8bc02357;   // de=-9

            12'hff8: Mp10 = 288'h00000000000000000000000000abcc77118461cefcfdc20d2b36ba7c3d3d4d3d75816169;   // de=-8

            12'hff9: Mp10 = 288'h00000000000000000000000006b5fca6af2bd215e1e99483b02348da64650466970dce1f;   // de=-7

            12'hffa: Mp10 = 288'h000000000000000000000000431bde82d7b634dad31fcd24e160d887ebf22c01e68a0d35;   // de=-6

            12'hffb: Mp10 = 288'h0000000000000000000000029f16b11c6d1e108c3f3e0370cdc8754f3775b8130164840e;   // de=-5

            12'hffc: Mp10 = 288'h00000000000000000000001a36e2eb1c432ca57a786c226809d495182a9930be0ded288d;   // de=-4

            12'hffd: Mp10 = 288'h00000000000000000000010624dd2f1a9fbe76c8b4395810624dd2f1a9fbe76c8b439581;   // de=-3

            12'hffe: Mp10 = 288'h000000000000000000000a3d70a3d70a3d70a3d70a3d70a3d70a3d70a3d70a3d70a3d70a;   // de=-2

            12'hfff: Mp10 = 288'h000000000000000000006666666666666666666666666666666666666666666666666666;   // de=-1

                default: Mp10 = {W {1'b0}};
            endcase
            mp10_neg = Mp10;
        end
    endfunction

    function integer msbpos;
        input [W-1:0] x; integer j;
        begin msbpos = -1; for (j = W-1; j >= 0; j = j-1) if (x[j] && msbpos == -1) msbpos = j; end
    endfunction

    reg [W-1:0] Mfactor, mant_full, shifted, lowbits;
    integer msb, e2;
    reg [24:0] mant25;
    reg sticky, guard, round_b, round_up;
    reg [23:0] mant24;

    always @* begin
        fp32_out = {sign, 8'hFF, 23'h400000};
        Mfactor = 0; mant_full = 0; shifted = 0; lowbits = 0;
        msb = 0; e2 = 0; mant25 = 0; guard = 0; round_b = 0;
        sticky = 0; round_up = 0; mant24 = 0;

        if (is_nan)         fp32_out = {sign, 8'hFF, 23'h400000};
        else if (is_inf)    fp32_out = {sign, 8'hFF, 23'h000000};
        else if (C == 0)    fp32_out = {sign, 31'b0};
        else begin
            if (de > 12'sd38)         fp32_out = {sign, 8'hFF, 23'h000000};   // overflow
            else if (de < -12'sd61)   fp32_out = {sign, 31'b0};               // underflow
            else begin
                if (de >= 0) begin
                    Mfactor   = pow10n(de);
                    mant_full = C * Mfactor;                  // exact C*10^de
                    msb       = msbpos(mant_full);
                    e2        = msb;
                end else begin
                    Mfactor   = mp10_neg(de);                 // round(10^de*2^G)
                    mant_full = C * Mfactor;                  // ~ C*10^de * 2^G
                    msb       = msbpos(mant_full);
                    e2        = msb - G;                      // value = mant_full * 2^-G
                end

                if (e2 > 127)         fp32_out = {sign, 8'hFF, 23'h000000};
                else if (e2 < -150)   fp32_out = {sign, 31'b0};
                else begin
                    if (msb >= 25) begin
                        shifted = mant_full >> (msb - 25);    // bit msb -> pos 25
                        guard   = shifted[1];
                        round_b = shifted[0];
                        lowbits = mant_full << (W + 25 - msb); // bits [msb-26:0] -> sticky
                        sticky  = |lowbits;
                    end else begin
                        shifted = mant_full << (25 - msb);
                        guard   = 1'b0; round_b = 1'b0;
                    end
                    mant25   = {1'b0, shifted[25:2]};       // 24-bit mantissa + carry
                    round_up = guard & (round_b | sticky | mant25[0]);
                    if (round_up) mant25 = mant25 + 25'd1;
                    if (mant25[24]) begin                    // carry out
                        mant24 = 24'h800000; e2 = e2 + 1;
                    end else mant24 = mant25[23:0];

                    if (e2 > 127)         fp32_out = {sign, 8'hFF, 23'h000000};
                    else if (e2 < -126) begin
                        if (e2 >= -149) fp32_out = {sign, 8'h00, 23'h000001};
                        else            fp32_out = {sign, 31'b0};
                    end else
                        fp32_out = {sign, e2[7:0] + 8'd127, mant24[22:0]};
                end
            end
        end
    end
endmodule
`default_nettype none
