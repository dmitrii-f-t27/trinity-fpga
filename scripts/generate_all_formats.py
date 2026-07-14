#!/usr/bin/env python3
"""
generate_all_formats.py — Batch-generate RTL + CI + conformance for all
remaining catalog formats that have a decode law (→ FP32).

Generates: decoder .v, corona wrapper .v, CI workflow .yml, conformance .py
for each format. Pushes to main (triggers parallel CI runs).
"""
import os, textwrap, json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── FORMAT DEFINITIONS ──────────────────────────────────────────────
# (name, N, E, M, BIAS, bias_expr, decoder_type, extra_note)
# decoder_type: "gf_param" = use gf_decode_param, "generic_float" = write custom

GF_FORMATS = [
    # name   N   E   M    BIAS         expr                  note
    ("gf48",  48, 18, 29, 131071,      "2^17-1"),
    ("gf64",  64, 24, 39, 8388607,     "2^23-1"),
    ("gf96",  96, 36, 59, 34359738367, "2^35-1"),
    ("gf128", 128,49, 78, 281474976710655, "2^48-1"),
    # gf256/512/1024: very wide, likely routing-limited but include for completeness
    ("gf256", 256,97,158, 79228162514264337593543950335, "2^96-1"),
]

# Simple float formats: (name, total_bits, sign_bits, exp_bits, mant_bits, bias, has_hidden, frame_bytes, description)
FLOAT_FORMATS = [
    # name       bits  S  E   M    bias   hidden  frame  desc
    ("binary256", 256, 1, 19, 236, 393215, True,  32, "IEEE 754 binary256"),
    ("vax_h",     128, 1, 15, 112, 16384,  False, 16, "VAX H_floating (no hidden bit)"),
    ("x87_fp80",   80, 1, 15, 64,  16383,  False, 10, "x87 80-bit extended (explicit integer bit)"),
    ("cray_float", 64, 1, 15, 48,  16384,  False,  8, "CRAY-1 floating point (no hidden, bias 0x4000)"),
    ("ibm_hfp128",128, 1, 7,  120, 64,     False, 16, "IBM hex float 128 (base-16 exponent)"),
    ("ibm_hfp128",128, 1, 7,  120, 64,     False, 16, "IBM hex float 128"),  # dup-safe
]

# ── CORONA WRAPPER GENERATOR ────────────────────────────────────────

def gen_corona_wrapper(fmt_name, decoder_module, decoder_ports, N, frame_bytes):
    """Generate corona wrapper for any format."""
    nbits = N
    frm_bits = frame_bytes + 3  # AA + 55 + fmt + N bytes + trig
    frm_width = len(bin(frm_bits - 1)) - 2  # bits needed for frm counter

    # Frame state machine: collect bytes
    code_assigns = []
    for b in range(frame_bytes):
        lo = b * 8
        hi = lo + 7
        code_assigns.append(f"                {frm_width}'d{3+b}: begin code_r[{hi}:{lo}]<=rx_byte;frm<={frm_width}'d{4+b}; end")
    code_assigns.append(f"                {frm_width}'d{3+frame_bytes}: begin frame_valid<=1;frm<=0; end")

    wrapper = f"""`default_nettype wire
`timescale 1ns / 1ps
// corona_decode_{fmt_name}_ax7203 — {decoder_module} on AX7203 ({frame_bytes}-byte frame).
module corona_decode_{fmt_name}_ax7203 (
    input  wire rst_n, input wire uart_rx, output reg uart_tx, output wire [3:0] led
);
    wire mclk, eos;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startup (
        .CFGCLK(), .CFGMCLK(mclk), .EOS(eos),
        .CLK(1'b0),.GSR(1'b0),.GTS(1'b0),.KEYCLEARB(1'b0),.PACK(1'b0),
        .USRCCLKO(1'b0),.USRCCLKTS(1'b0),.USRDONEO(1'b0),.USRDONETS(1'b0));
    wire rst = ~rst_n | ~eos;
    localparam [8:0] BAUD_DIV = 9'd434;
    reg [26:0] cnt_c;
    always @(posedge mclk or posedge rst) if(rst) cnt_c<=0; else cnt_c<=cnt_c+1;
    assign led[0]=cnt_c[25]; assign led[3]=~rst;
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst) if(rst) rsync<=3'b111; else rsync<={{rsync[1:0]},uart_rx}};
    wire rxd=rsync[2];
    reg [1:0] rxs; reg [9:0] rxcnt; reg [2:0] rbi; reg [7:0] rxsr; reg [7:0] rx_byte; reg rx_new;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin rxs<=0;rxcnt<=0;rbi<=0;rxsr<=0;rx_byte<=0;rx_new<=0; end
        else begin rx_new<=0;
            case(rxs)
                2'd0: if(~rxd) begin rxcnt<=(BAUD_DIV+(BAUD_DIV>>1))-1;rxs<=1;rbi<=0; end
                2'd1: begin if(rxcnt==0) begin rxsr<={{rxd,rxsr[7:1]}}; if(rbi==7) begin rxs<=2;rxcnt<=BAUD_DIV-1; end else begin rbi<=rbi+1;rxcnt<=BAUD_DIV-1; end end else rxcnt<=rxcnt-1; end
                2'd2: begin if(rxcnt==0) begin rx_byte<=rxsr;rx_new<=1;rxs<=0; end else rxcnt<=rxcnt-1; end
            endcase
        end
    end
    reg [{frm_width-1}:0] frm; reg [7:0] fmt_r; reg [{nbits-1}:0] code_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;code_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                {frm_width}'d0: frm<=(rx_byte==8'hAA)?{frm_width}'d1:{frm_width}'d0;
                {frm_width}'d1: frm<=(rx_byte==8'h55)?{frm_width}'d2:{frm_width}'d0;
                {frm_width}'d2: begin fmt_r<=rx_byte;frm<={frm_width}'d3; end
{chr(10).join(code_assigns)}
                default: frm<=0;
            endcase end
        end
    end
    assign led[1]=frame_valid;
    wire [31:0] result;
    {decoder_module} u_dec ({decoder_ports});
    assign led[2] = |result;
    reg responding; reg [3:0] tx_idx; reg [7:0] tx_buf0,tx_buf1,tx_buf2,tx_buf3,tx_buf4;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF;tx_buf1<=8'hFF;tx_buf2<=8'hFF;tx_buf3<=8'hFF;tx_buf4<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(frame_valid) begin
                tx_buf0<=8'hA5; tx_buf1<=result[7:0]; tx_buf2<=result[15:8];
                tx_buf3<=result[23:16]; tx_buf4<=result[31:24]; responding<=1; tx_idx<=0;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        case(tx_idx)
                            4'd0: tsr<={{1'b1,tx_buf0,1'b0}}; 4'd1: tsr<={{1'b1,tx_buf1,1'b0}};
                            4'd2: tsr<={{1'b1,tx_buf2,1'b0}}; 4'd3: tsr<={{1'b1,tx_buf3,1'b0}};
                            4'd4: tsr<={{1'b1,tx_buf4,1'b0}};
                        endcase
                        if(tx_idx==4) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={{1'b1,tsr[9:1]}}; end
            end else tcnt<=tcnt-1;
        end
    end
endmodule
`default_nettype wire
"""
    return wrapper

def gen_ci_workflow(fmt_name):
    """Generate CI workflow for a format."""
    upper = fmt_name.upper()
    return f"""name: AX7203 Corona Decode {upper}
on:
  workflow_dispatch:
  push:
    branches: [main]
    paths:
      - 'fpga/openxc7-synth/corona_decode_{fmt_name}_ax7203.v'
      - 'fpga/openxc7-synth/*_{fmt_name}*.v'
      - 'fpga/openxc7-synth/gf_decode_param.v'
      - 'fpga/openxc7-synth/corona_decode_ax7203.xdc'
      - '.github/workflows/ax7203-corona-decode-{fmt_name}.yml'
jobs:
  bitstream:
    runs-on: ubuntu-latest
    timeout-minutes: 360
    steps:
      - uses: actions/checkout@v4
      - name: Docker pull regymm/openxc7 (retry on transient 5xx)
        run: |
          for i in 1 2 3 4 5 6; do
            docker pull regymm/openxc7:latest && break
            echo "::warning::docker pull attempt $i failed, sleeping $((i*20))s"; sleep $((i*20))
          done
          docker image inspect regymm/openxc7:latest >/dev/null 2>&1 || {{ echo "::error::docker pull failed after 6 retries"; exit 1; }}
      - name: Yosys
        run: |
          mkdir -p build/corona_decode_{fmt_name}
          docker run --rm -v "$PWD:/work" -w /work regymm/openxc7 yosys -p "
            read_verilog fpga/openxc7-synth/corona_decode_{fmt_name}_ax7203.v fpga/openxc7-synth/gf_decode_param.v;
            synth_xilinx -abc9 -arch xc7 -top corona_decode_{fmt_name}_ax7203;
            setundef -zero -params; write_json build/corona_decode_{fmt_name}/corona_decode_ax7203.json" 2>&1 | tee /tmp/yosys.log
          grep -E "Estimated|ERROR" /tmp/yosys.log
      - uses: actions/cache@v4
        id: chipdb
        with:
          path: build/corona_decode_{fmt_name}/chipdb/xc7a200tfbg484-2.bin
          key: chipdb-xc7a200tfbg484-2-regymm-${{ '{{' }}github.run_id{{ '}}' }}
          restore-keys: chipdb-xc7a200tfbg484-2-regymm-
      - if: steps.chipdb.outputs.cache-hit != 'true'
        run: |
          mkdir -p build/corona_decode_{fmt_name}/chipdb
          docker run --rm -v "$PWD:/work" -w /work regymm/openxc7 bash -c "cd /nextpnr-xilinx && python3 xilinx/python/bbaexport.py --device xc7a200tfbg484-2 --bba /work/build/corona_decode_{fmt_name}/chipdb/xc7a200tfbg484-2.bba && bbasm -l /work/build/corona_decode_{fmt_name}/chipdb/xc7a200tfbg484-2.bba /work/build/corona_decode_{fmt_name}/chipdb/xc7a200tfbg484-2.bin"
      - name: nextpnr (seed search, heap placer)
        run: |
          CLEAN=0; for s in $(seq 1 8); do
            rm -f build/corona_decode_{fmt_name}/corona_decode_ax7203.fasm
            docker run --rm -v "$PWD:/work" -w /work regymm/openxc7 timeout --signal=KILL 1800 nextpnr-xilinx \\
              --chipdb /work/build/corona_decode_{fmt_name}/chipdb/xc7a200tfbg484-2.bin \\
              --xdc /work/fpga/openxc7-synth/corona_decode_ax7203.xdc \\
              --json /work/build/corona_decode_{fmt_name}/corona_decode_ax7203.json \\
              --write /work/build/corona_decode_{fmt_name}/corona_decode_ax7203_routed.json \\
              --fasm /work/build/corona_decode_{fmt_name}/corona_decode_ax7203.fasm \\
              --freq 50.0 --seed $s --placer heap --router router1 --timing-allow-fail > /tmp/np_$s.log 2>&1 || true
            if grep -q "Failed to find a route" /tmp/np_$s.log || [ ! -f build/corona_decode_{fmt_name}/corona_decode_ax7203.fasm ]; then continue; fi
            cp /tmp/np_$s.log /tmp/np.log; CLEAN=$s; break
          done; [ "$CLEAN" = "0" ] && {{ echo "::error::no clean seed"; exit 1; }}; echo "seed=$CLEAN"
      - name: fasm2bit
        run: |
          docker run --rm -v "$PWD:/work" -w /work regymm/openxc7 bash -c "
            source /prjxray/env/bin/activate && fasm2frames --db-root /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 --part xc7a200tfbg484-2 /work/build/corona_decode_{fmt_name}/corona_decode_ax7203.fasm /work/build/corona_decode_{fmt_name}/corona_decode_ax7203.frames && /prjxray/build/tools/xc7frames2bit --part_file /nextpnr-xilinx/xilinx/external/prjxray-db/artix7/xc7a200tfbg484-2/part.yaml --part_name xc7a200tfbg484-2 --frm_file /work/build/corona_decode_{fmt_name}/corona_decode_ax7203.frames --output_file /work/build/corona_decode_{fmt_name}/corona_decode_ax7203.bit"
      - uses: actions/upload-artifact@v4
        with: {{name: corona-decode-{fmt_name}-bitstream, path: build/corona_decode_{fmt_name}/corona_decode_ax7203.bit}}
"""

def gen_conformance_gf(name, N, E, M, BIAS, frame_bytes):
    """Generate conformance script for GF format (uses gf_decode_param golden)."""
    return f'''#!/usr/bin/env python3
"""{name} decode conformance — GF{name[2:]} (N={N},E={E},M={M},BIAS={BIAS}) → FP32."""
import serial, struct, time, random, sys, argparse, math

N,E,M,BIAS = {N},{E},{M},{BIAS}
EM = (1<<E)-1

def decode(raw):
    raw &= (1<<N)-1
    s = raw>>(N-1); e = (raw>>M)&EM; m = raw&((1<<M)-1)
    if e==EM:
        if m==0: return 0xFF800000 if s else 0x7F800000
        return 0x7FC00001
    if e==0:
        if m==0: return s<<31
        v = (m/float(1<<M))*(2.0**(1-BIAS))
    else: v = (1+m/float(1<<M))*(2.0**(e-BIAS))
    if abs(v) > 3.4e38: return 0xFF800000 if v<0 else 0x7F800000
    return struct.unpack(">I",struct.pack(">f",-v if s else v))[0]

def make_codes():
    codes = set()
    MMAX = (1<<M)-1; NMAX = (1<<N)-1
    for s in (0,1):
        codes.add(s<<(N-1)); codes.add((s<<(N-1))|(EM<<M))
    codes.add((EM<<M)|1); codes.add((EM<<M)|MMAX)
    for s in (0,1):
        for mv in [1,MMAX,MMAX//2]:
            codes.add((s<<(N-1))|mv)
    for e in [1,2,BIAS&EM if BIAS<EM else 1,(BIAS+1)&EM,(BIASEMERGE:=(BIAS-1)&EM)]:
        if 1<=e<EM:
            for mv in [0,MMAX,MMAX//2]:
                for s in (0,1): codes.add((s<<(N-1))|(e<<M)|mv)
    rng = random.Random({N})
    for _ in range(min(2000, NMAX)): codes.add(rng.randrange(NMAX+1))
    return sorted(codes)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    args = ap.parse_args()
    codes = make_codes()
    port = serial.Serial(args.port, args.baud, timeout=3)
    ok = 0; fails = []
    for raw in codes:
        g = decode(raw)
        nbytes = {frame_bytes}
        b = [(raw >> (i*8)) & 0xFF for i in range(nbytes)]
        port.write(bytes([0xAA,0x55,0x00]+b+[0x00]))
        time.sleep(0.005)
        r = port.read(5)
        if len(r)>=5 and r[0]==0xA5:
            d = r[1]|(r[2]<<8)|(r[3]<<16)|(r[4]<<24)
            gn = (g>>23&0xFF)==0xFF and g&0x7FFFFF
            dn = (d>>23&0xFF)==0xFF and d&0x7FFFFF
            if gn and dn or d==g: ok+=1
            else:
                if len(fails)<10: fails.append(f"raw={{raw:#0{8+2*nbytes}x}} g={{g:#010x}} d={{d:#010x}}")
        else:
            if len(fails)<10: fails.append(f"raw={{raw:#0{8+2*nbytes}x}} noresp")
    print(f"HW RESULT: {{ok}}/{{len(codes)}} bit-exact (fails={{len(codes)-ok}})")
    for f in fails: print(f"  {{f}}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
'''

# ── MAIN: Generate all formats ──────────────────────────────────────

def main():
    os.chdir(REPO)
    generated = []

    # GF formats using gf_decode_param
    for name, N, E, M, BIAS, bias_expr in GF_FORMATS:
        # Check if already exists
        wrapper_path = f"fpga/openxc7-synth/corona_decode_{name}_ax7203.v"
        if os.path.exists(wrapper_path):
            print(f"SKIP {name}: wrapper already exists")
            continue

        frame_bytes = (N + 7) // 8  # ceil(N/8)
        ports = f".clk(1'b0), .rst_n(1'b1), .gf_in(code_r), .fp32_out(result), .is_nan_o(), .is_inf_o(), .is_zero_o(), .is_subnormal_o()"
        # Need gf_decode_param params
        wrapper = gen_corona_wrapper(name, f"gf_decode_param", ports, N, frame_bytes)
        # Add parameter override
        wrapper = wrapper.replace(
            f"gf_decode_param u_dec",
            f"gf_decode_param #(.N({N}), .E({E}), .M({M}), .BIAS({BIAS}), .OUT_REG(0)) u_dec"
        )

        with open(wrapper_path, "w") as f: f.write(wrapper)
        print(f"GEN {name}: wrapper ({frame_bytes}-byte frame)")

        # CI workflow
        ci = gen_ci_workflow(name)
        ci_path = f".github/workflows/ax7203-corona-decode-{name}.yml"
        with open(ci_path, "w") as f: f.write(ci)

        # Conformance
        conf = gen_conformance_gf(name, N, E, M, BIAS, frame_bytes)
        conf_path = f"conformance/{name}_decode_conformance_ax7203.py"
        with open(conf_path, "w") as f: f.write(conf)

        generated.append(name)

    print(f"\n=== Generated {len(generated)} format RTL sets: {', '.join(generated)} ===")
    if generated:
        print("Next: git add + commit + push → triggers parallel CI")

if __name__ == "__main__":
    main()
