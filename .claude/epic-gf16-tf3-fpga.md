# [EPIC] GF16/TF3 Arithmetic Unit on XC7A100T (Artix-7, 28nm)

**Labels:** `epic`, `fpga`, `hardware`, `priority:high`
**Milestone:** Sacred Formats Hardware
**Parent:** #357 (Training Farm Tracker)

---

## Goal

Implement and test a native hardware block for **GF16 (Golden Float 16)** and **TF3-9 (Ternary Float 9)** on the XC7A100T (Artix-7) FPGA, with a clean interface for Trinity.

> "Bring Sacred formats down from Level 0 (language) to Level 6 (RTL)" — this is Trinity's key differentiator against GPU-bound frameworks (PyTorch, JAX, TensorRT).

---

## Motivation

| Aspect | CPU (software) | FPGA (this EPIC) |
|--------|----------------|-------------------|
| GF16 add | ~50 cycles | ~1 cycle (50×) |
| GF16 mul | ~100 cycles | ~1 cycle (100×) |
| TF3 mac | ~100 cycles | ~1 cycle (100×) |
| Energy | High | Low (DSP-free) |

**Documentation links:**
- [positioning-zighalf-trinity.md](../docs/docs/concepts/positioning-zighalf-trinity.md) — Level 6 positioning
- [phi-distance-formats.md](../docs/docs/concepts/phi-distance-formats.md) — φ-distance analysis
- [native-f16-comparison.md](../docs/docs/concepts/native-f16-comparison.md) — Language stack comparison

---

## Target chip

| Parameter | Value |
|-----------|---------|
| FPGA | XC7A100T-1FGG484 (Artix-7, 28nm) |
| LUT | ~426k (6-input) |
| FF | ~852k |
| DSP48E1 | 240 |
| BRAM | ~16 Mbit |
| Target frequency | 100–150 MHz (v1) |

---

## Format specification

### GF16 (Golden Float 16)

```
┌─────────────────────────────────────┐
│ 15 │ 14-9  │ 8-0                   │
│────┼────────┼───────────────────────┤
│ S  │ Exp(6) │ Mant(9)               │
└─────────────────────────────────────┘
exp:mant = 6:9 = 0.667
φ-distance = 0.049 (95.1% golden)
```

**Source code:** `src/hslm/intraparietal_sulcus.zig`

### TF3-9 (Ternary Float 9)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 17-16 │ 15-10    │ 9-0                                             │
│──────┼───────────┼─────────────────────────────────────────────────│
│ Sign │ Exp(3×2)  │ Mant(5×2)  // 3 exp trits + 5 mant trits         │
│      │ trits     │           // Each trit = 2 bits: 00=0, 01=-1, 10=+1 │
└─────────────────────────────────────────────────────────────────────┘
exp:mant = 3:5 = 0.600
φ-distance = 0.018 (98.2% golden) — BEST FORMAT!
```

**Source code:** `src/hslm/intraparietal_sulcus.zig`

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │          SACRED_ALU_TOP             │
                    ├─────────────────────────────────────┤
                    │  ┌───────────┐    ┌───────────┐    │
 AXI-Stream ────────►│  │  GF16_ALU │    │  TF3_ALU  │    │├───► AXI-Stream
                    │  │           │    │           │    │
                    │  │ add/mul/fma│   │ add/dot   │    │
                    │  └───────────┘    └───────────┘    │
                    │                                     │
                    │  Control: mode[1:0], csr[31:0]     │
                    └─────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────────────────────┐
                    │  XC7A100T Fabric (28nm)            │
                    │  - LUT: GF16 ops, TF3 decode       │
                    │  - DSP48E1: GF16 mul (optional)    │
                    │  - FF: Pipeline registers          │
                    └─────────────────────────────────────┘
```

---

## Tasks (Phases)

### Phase 1: GF16 Adder

**File:** `fpga/openxc7-synth/gf16_adder.v`

- [ ] Implement a 4-stage pipeline:
  - [ ] Stage 1: Decode (sign/exp/mant), align exponents
  - [ ] Stage 2: Core add (mantissa addition)
  - [ ] Stage 3: Normalize (shift result, adjust exponent)
  - [ ] Stage 4: Round-to-nearest-even, pack to 16-bit

- [ ] Interface (AXI-Stream compatible):
  ```verilog
  module gf16_adder (
      input  wire        clk,
      input  wire        rst,
      input  wire        in_valid,
      input  wire [15:0] in_a,    // GF16 operand A
      input  wire [15:0] in_b,    // GF16 operand B
      output wire        in_ready,

      output wire        out_valid,
      output wire [15:0] out_y,   // GF16 result
      input  wire        out_ready
  );
  ```

- [ ] Testbench: `fpga/openxc7-synth/tb/gf16_adder_tb.v`
  - [ ] Generate test vectors from `src/hslm/intraparietal_sulcus.zig`
  - [ ] Compare against software reference (Zig `gf16FromF32/gf16ToF32`)
  - [ ] Precision: error ≤ 1 LSB

- [ ] Synthesis:
  - [ ] Yosys synthesis report (LUT/FF count)
  - [ ] Timing: ≥ 100 MHz on -1 speed grade

**Labels:** `fpga`, `gf16`, `phase-1`

---

### Phase 2: GF16 Multiplier

**File:** `fpga/openxc7-synth/gf16_multiplier.v`

- [ ] Implement a 3-4 stage pipeline:
  - [ ] Stage 1: Decode, multiply mantissas
  - [ ] Stage 2: DSP48E1 usage (18×18 multiply)
  - [ ] Stage 3: Normalize, add exponents
  - [ ] Stage 4: Round, pack

- [ ] Interface (same as adder):
  ```verilog
  module gf16_multiplier (
      input  wire        clk, rst,
      input  wire        in_valid,
      input  wire [15:0] in_a, in_b,
      output wire        in_ready,
      output wire        out_valid,
      output wire [15:0] out_y,
      input  wire        out_ready
  );
  ```

- [ ] Testbench: `fpga/openxc7-synth/tb/gf16_multiplier_tb.v`
  - [ ] Random test vectors vs software reference
  - [ ] Corner cases: denormals, infinity, NaN

- [ ] Synthesis:
  - [ ] Report: LUT/FF + 1× DSP48E1 usage
  - [ ] Timing: ≥ 100 MHz

**Labels:** `fpga`, `gf16`, `phase-2`

---

### Phase 3: TF3 ALU

**File:** `fpga/openxc7-synth/tf3_alu.v`

- [ ] Ternary decode:
  ```verilog
  // Trit encoding: 00=0, 01=-1, 10=+1, 11=invalid
  function [1:0] trit_decode(input [1:0] t);
      case (t)
          2'b00: trit_decode = 2'b00;  // 0
          2'b01: trit_decode = 2'b11;  // -1 (in 2's comp)
          2'b10: trit_decode = 2'b01;  // +1
          default: trit_decode = 2'b00; // treat as 0
      endcase
  endfunction
  ```

- [ ] `tf3_add`: saturating add of two TF3-9 numbers
- [ ] `tf3_dot`: N-length dot product (configurable N)

- [ ] Interface:
  ```verilog
  module tf3_alu (
      input  wire        clk, rst,
      input  wire [1:0]  mode,    // 00=add, 01=dot
      input  wire        in_valid,
      input  wire [17:0] in_a, in_b,  // TF3-9 operands
      input  wire [7:0]  dot_len,      // N for dot product
      output wire        in_ready,
      output wire        out_valid,
      output wire [17:0] out_y,
      input  wire        out_ready
  );
  ```

- [ ] Testbench: `fpga/openxc7-synth/tb/tf3_alu_tb.v`
  - [ ] Comparison against `src/hslm/intraparietal_sulcus.zig` (TernaryFloat9)

**Labels:** `fpga`, `tf3`, `phase-3`

---

### Phase 4: Sacred ALU Wrapper

**File:** `fpga/openxc7-synth/sacred_alu.v`

- [ ] Unified interface:
  ```verilog
  module sacred_alu (
      // Clock/reset
      input  wire        clk, rst,

      // Control
      input  wire [1:0]  mode,    // 00=GF16_ADD, 01=GF16_MUL, 10=TF3_ADD, 11=TF3_DOT
      input  wire [31:0] csr,     // Control/status registers

      // Data stream
      input  wire        in_valid,
      input  wire [31:0] in_data, // [17:0] op_a, [17:0] op_b (packed)
      output wire        in_ready,

      output wire        out_valid,
      output wire [31:0] out_data,
      input  wire        out_ready
  );
  ```

- [ ] Multiplexing between GF16_ALU and TF3_ALU
- [ ] CSR registers for configuration and status

**Labels:** `fpga`, `integration`, `phase-4`

---

### Phase 5: Trinity Integration

**Files:** `src/hslm/fpga_backend.zig` (new)

- [ ] Zig backend for invoking the FPGA ALU:
  ```zig
  const fpga = @import("fpga_backend.zig");

  pub fn gf16AddFpga(a: GoldenFloat16, b: GoldenFloat16) !GoldenFloat16 {
      return fpga.callAlu(.GF16_ADD, a, b);
  }
  ```

- [ ] Fallback to software implementation if FPGA unavailable
- [ ] Unified interface: `fn gf16Add(a, b) -> result` (HW or SW)

**Labels:** `integration`, `zig`, `phase-5`

---

### Phase 6: Documentation & Benchmarks

- [ ] Update `docs/lab/papers/trinity-fpga/draft.md` with results
- [ ] Benchmarks: HW vs SW (cycles, latency, throughput)
- [ ] Resources: LUT/FF/DSP usage table
- [ ] Timing screenshots from Vivado/Yosys

**Labels:** `docs`, `benchmark`, `phase-6`

---

## Acceptance metrics

| Metric | Target | How to measure |
|--------|--------|----------------|
| **GF16 add correctness** | ≤ 1 LSB | vs Zig `gf16FromF32` |
| **GF16 mul correctness** | ≤ 1 LSB | vs Zig reference |
| **TF3 correctness** | Exact match | vs TernaryFloat9 |
| **GF16 add resources** | < 500 LUT, < 200 FF | Yosys report |
| **GF16 mul resources** | < 300 LUT + 1 DSP | Yosys report |
| **TF3 ALU resources** | < 1000 LUT, < 500 FF | Yosys report |
| **Frequency** | ≥ 100 MHz | Timing report (wns > 0) |
| **Latency** | 4 cycles (GF16) | Simulation |
| **Throughput** | 1 op/cycle (pipelined) | Benchmark |

---

## Dependencies

| Task | Blocks |
|------|--------|
| Phase 1 (GF16 add) | Phase 2, Phase 4 |
| Phase 2 (GF16 mul) | Phase 4 |
| Phase 3 (TF3 ALU) | Phase 4 |
| Phase 4 (Wrapper) | Phase 5 |
| Phase 5 (Integration) | Phase 6 |

---

## Related issues

- #357 — Training Farm Tracker (parent)
- [HSLM Training Review](../docs/lab/papers/hslm/training-review-mar10-14.md) — Training context
- [FPGA Synthesis Results](../docs/lab/papers/trinity-fpga/synthesis-real-data.md) — Existing synthesis

---

## Risks and mitigation

| Risk | Probability | Mitigation |
|------|-------------|------------|
| Timing won't close | Medium | Simplify pipeline (3 stages) |
| Not enough DSP48E1 | Low | GF16 mul on LUT (fallback) |
| TF3 encoding changes | Low | Parameterize trit encoding |

---

## Questions for discussion

1. **Pipeline depth:** 3 or 4 stages for GF16 add? (affects latency vs area)
2. **DSP usage:** Use DSP48E1 for GF16 mul or pure LUT?
3. **Interface:** AXI-Stream or custom handshaking?

---

## Useful links

- [Yosys documentation](https://yosyshq.readthedocs.io/)
- [Xilinx DSP48E1 user guide](https://www.xilinx.com/support/documentation/user_guides/ug479_7Series_DSP48E1.pdf)
- [Trinity FPGA docs](../fpga/openxc7-synth/)

---

*φ² + 1/φ² = 3 | TRINITY*
