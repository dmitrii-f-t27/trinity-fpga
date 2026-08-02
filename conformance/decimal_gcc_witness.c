/* An independent second witness for the decimal32/64/128 packs.
 *
 * Every `expected` value in conformance/vectors/decimal{32,64,128}_{add,sub,mul}.json
 * comes from conformance/decimal_ref.py -- one implementation, checking itself. Honesty
 * rule #10 wants a second one that shares no code with the first.
 *
 * GCC's _Decimal32/64/128 are that: the arithmetic is Intel's BID library, written from
 * IEEE 754-2008 and reachable here without any of our source. It was recorded as
 * unavailable on this machine, and it is not -- Homebrew gcc-14 has it, and it emits BID
 * rather than DPD, which is the encoding the packs use. Confirmed rather than assumed:
 *
 *     _Decimal32 1.0 -> 0x3200000a
 *     sign 0, biased exponent 0x64 = 100 (unbiased -1), coefficient 10.
 *     DPD would place the coefficient in declets and give a different word.
 *
 * Reads "a_hex b_hex" pairs on stdin, writes the result word per line on stdout. No JSON
 * parsing here on purpose: the Python side owns the vector files, and a second hand-rolled
 * parser is a second thing that can be wrong about them.
 *
 *   gcc-14 -isysroot "$(xcrun --show-sdk-path)" -O2 \
 *          conformance/decimal_gcc_witness.c -o /tmp/decimal_gcc_witness
 *   (the sysroot is required: gcc's own fixed headers are stale against the macOS SDK)
 *
 * Rounding is left at the default, round-half-even, which is what decimal_ref.py's
 * _round_half_even implements. Changing it here would make a disagreement meaningless.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: %s <32|64|128> <add|sub|mul>\n", argv[0]);
        return 2;
    }
    int width = atoi(argv[1]);
    const char *op = argv[2];
    char la[64], lb[64];

    while (scanf("%63s %63s", la, lb) == 2) {
        if (width == 32) {
            uint32_t ua = (uint32_t)strtoull(la, NULL, 16);
            uint32_t ub = (uint32_t)strtoull(lb, NULL, 16);
            _Decimal32 a, b, r;
            memcpy(&a, &ua, 4); memcpy(&b, &ub, 4);
            /* The operands are promoted to _Decimal64 by the usual arithmetic
             * conversions if written naively; the explicit casts keep every step at the
             * pack's own width, which is the thing being witnessed. */
            if (!strcmp(op, "add"))      r = (_Decimal32)(a + b);
            else if (!strcmp(op, "sub")) r = (_Decimal32)(a - b);
            else                         r = (_Decimal32)(a * b);
            uint32_t ur; memcpy(&ur, &r, 4);
            printf("%08x\n", ur);
        } else if (width == 64) {
            uint64_t ua = strtoull(la, NULL, 16);
            uint64_t ub = strtoull(lb, NULL, 16);
            _Decimal64 a, b, r;
            memcpy(&a, &ua, 8); memcpy(&b, &ub, 8);
            if (!strcmp(op, "add"))      r = (_Decimal64)(a + b);
            else if (!strcmp(op, "sub")) r = (_Decimal64)(a - b);
            else                         r = (_Decimal64)(a * b);
            uint64_t ur; memcpy(&ur, &r, 8);
            printf("%016llx\n", (unsigned long long)ur);
        } else {
            /* 128 bits do not fit strtoull. Split at the halfway point; the Python side
             * emits exactly 32 hex digits so the split is fixed, not searched for. */
            char hi[17], lo[17];
            size_t n = strlen(la);
            if (n != 32) { fprintf(stderr, "expected 32 hex digits, got %zu\n", n); return 3; }
            memcpy(hi, la, 16); hi[16] = 0; memcpy(lo, la + 16, 16); lo[16] = 0;
            uint64_t ah = strtoull(hi, NULL, 16), al = strtoull(lo, NULL, 16);
            memcpy(hi, lb, 16); hi[16] = 0; memcpy(lo, lb + 16, 16); lo[16] = 0;
            uint64_t bh = strtoull(hi, NULL, 16), bl = strtoull(lo, NULL, 16);
            _Decimal128 a, b, r;
            uint64_t w[2];
            w[0] = al; w[1] = ah; memcpy(&a, w, 16);   /* little-endian container */
            w[0] = bl; w[1] = bh; memcpy(&b, w, 16);
            if (!strcmp(op, "add"))      r = a + b;
            else if (!strcmp(op, "sub")) r = a - b;
            else                         r = a * b;
            memcpy(w, &r, 16);
            printf("%016llx%016llx\n", (unsigned long long)w[1],
                                       (unsigned long long)w[0]);
        }
    }
    return 0;
}
