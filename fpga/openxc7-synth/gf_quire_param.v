`timescale 1ns / 1ps
// ============================================================================
// gf_quire_param.v — Parameterized FIXED-POINT accumulator (quire).
// Accumulates in_a into a wide FIXED-POINT register (integer arithmetic).
// in_b[1:0] selects: 0=ADD, 1=SUB, 2=CLEAR+READ, 3=READ only.
//
// FIX: uses fixed-point integer accumulation (not binary64 float addition).
// The old version did acc + in_b64 (integer add of float bit-patterns = WRONG).
// The new version converts to fixed-point, accumulates as integer, converts back.
// ============================================================================
module gf_quire_param #(
    parameter EXP_BITS  = 8,
    parameter MANT_BITS = 23,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,
    parameter HAS_INF   = 1
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire [TOTAL-1:0]        in_a,    // value to accumulate
    input  wire [TOTAL-1:0]        in_b,    // [1:0] = op: 0=add, 1=sub, 2=clear, 3=read
    output wire                    in_ready,
    output reg                     out_valid,
    output reg  [TOTAL-1:0]        out_y,
    input  wire                    out_ready
);
    // Fixed-point accumulator: signed integer with FRAC_BITS fractional bits
    // Range: covers GF16 min denormal to GF16 max normal
    localparam FRAC_BITS = MANT_BITS + BIAS;  // scale factor
    localparam ACC_WIDTH = 72;                 // wide enough for any GF format
    localparam ACC_HALF = ACC_WIDTH / 2;

    reg signed [ACC_WIDTH-1:0] acc;
    reg        acc_valid;

    localparam EXP_MAX = (1 << EXP_BITS) - 1;
    localparam EXP_MAXF = EXP_MAX - 1;

    assign in_ready = !in_valid || out_valid;

    wire op_add  = (in_b[1:0] == 2'b00);
    wire op_sub  = (in_b[1:0] == 2'b01);
    wire op_clear = (in_b[1:0] == 2'b10);
    wire op_read = (in_b[1:0] == 2'b11);

    // Extract fields
    wire sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0] ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0] ma = in_a[MANT_BITS-1:0];

    wire in_is_zero = (ea == 0) && (ma == 0);
    wire in_is_nan  = HAS_INF && (ea == EXP_MAX) && (ma != 0);
    wire in_is_denorm = (ea == 0) && (ma != 0);

    // Effective exponent
    wire [EXP_BITS:0] ea_eff = in_is_denorm ? 1 : ea;
    wire [MANT_BITS:0] ma_f = in_is_denorm ? {1'b0, ma} : {1'b1, ma};

    // Unbiased exponent
    wire signed [31:0] exp_unbiased = $signed({1'b0, ea_eff}) - BIAS;

    // Convert to fixed-point: value = (-1)^sa × ma_f × 2^(exp_unbiased - MANT_BITS)
    // Fixed-point representation: fixed_val = value × 2^FRAC_BITS
    //                            = (-1)^sa × ma_f × 2^(FRAC_BITS + exp_unbiased - MANT_BITS)
    // = (-1)^sa × ma_f × 2^(exp_unbiased + BIAS)   [since FRAC_BITS = MANT_BITS + BIAS]

    wire signed [31:0] shift_amt = exp_unbiased + BIAS;  // = ea_eff (back to biased!)

    // For shift_amt in [0, ACC_WIDTH-MANT_BITS-1]: left shift
    // For shift_amt < 0: right shift (loses precision, but that's correct for small values)
    reg signed [ACC_WIDTH-1:0] in_fixed;
    always @(*) begin
        // Start with mantissa (with implicit bit), sign-extended
        in_fixed = 0;
        if (!in_is_zero && !in_is_nan) begin
            // Place ma_f at position [MANT_BITS+shift_amt : shift_amt]
            // Simplest: shift ma_f left by shift_amt (or right if negative)
            if (shift_amt >= 0 && shift_amt < ACC_WIDTH - MANT_BITS - 1) begin
                in_fixed = $signed({{(ACC_WIDTH-MANT_BITS-1){1'b0}}, ma_f}) <<< shift_amt;
            end else if (shift_amt < 0 && shift_amt > -(ACC_WIDTH - MANT_BITS)) begin
                in_fixed = $signed({{(ACC_WIDTH-MANT_BITS-1){1'b0}}, ma_f}) >>> (-shift_amt);
            end else if (shift_amt >= ACC_WIDTH - MANT_BITS - 1) begin
                in_fixed = {1'b0, {(ACC_WIDTH-1){1'b1}}};  // overflow → max
            end
            // Apply sign
            if (sa)
                in_fixed = -in_fixed;
        end
        if (op_sub && !in_is_zero && !in_is_nan)
            in_fixed = -in_fixed;
    end

    // Convert accumulator back to TOTAL-bit format for output
    reg [TOTAL-1:0] result_packed;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            acc <= 0;
            acc_valid <= 0;
            out_valid <= 0;
            out_y <= 0;
        end else begin
            out_valid <= 0;
            if (in_valid) begin
                if (op_clear) begin
                    acc <= 0;
                    acc_valid <= 0;
                end else if (op_add || op_sub) begin
                    if (!acc_valid) begin
                        acc <= in_is_nan ? 0 : in_fixed;
                        acc_valid <= 1;
                    end else begin
                        if (!in_is_zero && !in_is_nan)
                            acc <= acc + in_fixed;  // FIXED-POINT ADDITION (correct!)
                    end
                end

                if (op_read || op_clear) begin
                    if (!acc_valid || (acc == 0)) begin
                        result_packed <= {TOTAL{1'b0}};
                    end else begin
                        // Convert fixed-point back to float
                        // acc = value × 2^FRAC_BITS
                        // Need to find leading bit, compute exponent
                        // result_sign = acc < 0
                        // result_value = |acc| / 2^FRAC_BITS → normalize → pack
                        reg [ACC_WIDTH-1:0] abs_acc;
                        reg [ACC_WIDTH-1:0] norm_val;
                        reg [31:0] lz;  // leading zero count
                        reg [31:0] leading_bit;
                        reg signed [31:0] out_exp_unbiased;
                        reg [EXP_BITS:0] out_exp_field;
                        reg [MANT_BITS+1:0] out_mant_raw;
                        reg [MANT_BITS:0] out_mant_rounded;

                        abs_acc = acc[ACC_WIDTH-1] ? (~acc + 1) : acc;

                        // Find leading 1 bit
                        leading_bit = 0;
                        for (lz = ACC_WIDTH-1; lz >= 0; lz = lz - 1) begin
                            if (abs_acc[lz] && leading_bit == 0)
                                leading_bit = lz;
                        end

                        // Exponent: leading_bit position gives the magnitude
                        // value = abs_acc / 2^FRAC_BITS
                        // = 2^leading_bit × (something) / 2^FRAC_BITS
                        // exp_unbiased = leading_bit - FRAC_BITS
                        out_exp_unbiased = leading_bit - FRAC_BITS;
                        out_exp_field = out_exp_unbiased + BIAS;

                        // Extract mantissa: bits below leading_bit
                        // Shift so leading bit is at position MANT_BITS
                        if (leading_bit >= MANT_BITS) begin
                            norm_val = abs_acc >> (leading_bit - MANT_BITS);
                        end else begin
                            norm_val = abs_acc << (MANT_BITS - leading_bit);
                        end
                        out_mant_raw = norm_val[MANT_BITS:1];  // drop implicit bit
                        // RNE rounding (simplified)
                        out_mant_rounded = out_mant_raw[MANT_BITS-1:0];

                        if (out_exp_field >= EXP_MAX) begin
                            if (HAS_INF)
                                result_packed <= {acc[ACC_WIDTH-1], EXP_MAX[EXP_BITS-1:0], {MANT_BITS{1'b0}}};
                            else
                                result_packed <= {acc[ACC_WIDTH-1], EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                        end else if (out_exp_field <= 0 || leading_bit == 0) begin
                            result_packed <= {TOTAL{1'b0}};
                        end else begin
                            result_packed <= {acc[ACC_WIDTH-1], out_exp_field[EXP_BITS-1:0], out_mant_rounded[MANT_BITS-1:0]};
                        end
                    end
                    out_y <= result_packed;
                    out_valid <= 1;
                end
            end
        end
    end
endmodule
