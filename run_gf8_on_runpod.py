#!/usr/bin/env python3
"""
Autonomous GF8 ablation runner for RunPod.
Paste in Web Terminal: curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/run_gf8_on_runpod.py | python3

Runs 3 arms: FP8 (baseline), FP8S (scaled e4m3), GF8 (e3m4 phi-rule).
"""
import subprocess, sys, os, json, time

def sh(cmd, timeout=900):
    return subprocess.run(cmd, shell=True, timeout=timeout, capture_output=True, text=True)

# Step 1: Check GPU
import torch
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"GPUs: {torch.cuda.device_count()}")
nvidia = sh("nvidia-smi -L")
print(nvidia.stdout[:200])

# Step 2: Install deps
print("\n=== Installing deps ===")
sh("pip3 install sentencepiece huggingface_hub flash-attn -q 2>&1 | tail -2", 300)

# Step 3: Clone + setup
os.makedirs("/workspace/pg", exist_ok=True)
os.chdir("/workspace/pg")

if not os.path.exists("parameter-golf"):
    sh("git clone --depth 1 https://github.com/openai/parameter-golf.git", 60)

# Download GF8 ablation files
sh("cd parameter-golf && curl -sLO https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/parameter_golf_gf8_ablation/gf8_quant.py")
sh("cd parameter-golf && curl -sLO https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/parameter_golf_gf8_ablation/train_gpt_cuda_gf8.py")
sh("cd parameter-golf && curl -sLO https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/parameter_golf_gf8_ablation/run_gf8_ablation.sh")
sh("chmod +x parameter-golf/run_gf8_ablation.sh")

# Download SP8192 data
os.chdir("/workspace/pg/parameter-golf")
if not os.path.exists("data/datasets/fineweb10B_sp8192"):
    print("\n=== Downloading SP8192 data ===")
    sh("python3 data/cached_challenge_fineweb.py --variant sp8192 --train-shards 1", 600)

# Step 4: Run ablation — all 3 arms
results = {}
for arm in ["fp8", "gf8"]:
    seed = 1337
    print(f"\n{'='*60}")
    print(f"=== ARM: {arm} (seed={seed}) ===")
    print(f"{'='*60}")
    
    result = sh(f"cd /workspace/pg/parameter-golf && bash run_gf8_ablation.sh {arm} {seed}", 900)
    output = result.stdout + result.stderr
    
    # Extract val_bpb
    for line in output.split("\n"):
        if "val_bpb" in line.lower() or "bpb" in line.lower():
            print(f"  {line.strip()}")
            if "val_bpb" in line:
                try:
                    bpb = float(line.split("val_bpb:")[1].split()[0])
                    results[arm] = bpb
                except:
                    pass
    
    print(f"\n  Output (last 500 chars): {output[-500:]}")

# Step 5: Report
print(f"\n{'='*60}")
print(f"GF8 ABLATION RESULTS")
print(f"{'='*60}")
print(f"\n{'Arm':<10} {'val_bpb':>10}")
print("-" * 25)
for arm, bpb in sorted(results.items(), key=lambda x: x[1]):
    print(f"{arm:<10} {bpb:>10.4f}")

if "fp8" in results and "gf8" in results:
    delta = results["gf8"] - results["fp8"]
    print(f"\nΔ (GF8 - FP8): {delta:+.4f} BPB")
    if delta < 0:
        print("★ GF8 WINS! φ-rule e3m4 beats e4m3!")
    else:
        print(f"FP8 wins by {delta:.4f}")

# Save
with open("/workspace/gf8_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved: /workspace/gf8_results.json")
print("DONE")
