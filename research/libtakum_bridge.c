/* Bridge: dump libtakum's decode of every takum8 / takum16 code.
 *
 * Purpose: give the takum family a genuine SECOND reference. ml_dtypes does not
 * implement takum, so the catalog's takum packs are otherwise single-source.
 * libtakum (Hunhold) is the format author's own C99 reference implementation.
 *
 * Storage in libtakum is SIGNED (typedef int8_t takum8), while the conformance
 * oracles index codes as unsigned 0..2^n-1. The mapping is applied here so both
 * sides talk about the same bit pattern.
 *
 * Output: one line per code, "<unsigned_raw>\t<f64 bit pattern as 16 hex digits>".
 * Bit patterns rather than decimal text so the comparison loses nothing to
 * printf rounding.
 *
 * Build (libtakum checked out and built alongside):
 *   cc -O2 -I<libtakum> research/libtakum_bridge.c <libtakum>/libtakum.a -lm \
 *      -o /tmp/libtakum_bridge
 * Usage:
 *   /tmp/libtakum_bridge 8        > linear variant
 *   /tmp/libtakum_bridge 8 log    > logarithmic variant
 *   /tmp/libtakum_bridge 16   > /tmp/libtakum_takum16.tsv
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "takum.h"

static void emit(unsigned long raw, double v)
{
	uint64_t bits;
	memcpy(&bits, &v, sizeof bits);
	printf("%lu\t%016llx\n", raw, (unsigned long long)bits);
}

int main(int argc, char **argv)
{
	int width = (argc > 1) ? atoi(argv[1]) : 8;
	int use_log = (argc > 2 && strcmp(argv[2], "log") == 0);

	if (width == 8) {
		for (unsigned long raw = 0; raw < 256UL; raw++) {
			/* unsigned code -> signed storage */
			takum8 t = (takum8)(int8_t)(raw < 128UL ? (int)raw
			                                        : (int)raw - 256);
			emit(raw, use_log ? takum_log8_to_float64((takum_log8)t)
			                  : takum8_to_float64(t));
		}
	} else if (width == 16) {
		for (unsigned long raw = 0; raw < 65536UL; raw++) {
			takum16 t = (takum16)(int16_t)(raw < 32768UL ? (long)raw
			                                            : (long)raw - 65536L);
			emit(raw, use_log ? takum_log16_to_float64((takum_log16)t)
			                  : takum16_to_float64(t));
		}
	} else {
		fprintf(stderr, "width must be 8 or 16 (32/64 are not enumerable)\n");
		return 2;
	}
	return 0;
}
