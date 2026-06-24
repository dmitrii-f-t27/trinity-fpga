use std::net::IpAddr;
use std::path::PathBuf;
use std::process::Command;
use std::time::Instant;

use anyhow::{Context, bail};
use clap::{Parser, Subcommand};
use trios_fpga_fp00::{BoardConfig, TritValue, XvcConfig, ALINX_AX7203, ARTIX7_100T, ARTIX7_200T};

#[derive(Parser)]
#[command(name = "trios-fpga", version, about = "FPGA synthesis, flash and verify via XVC WiFi JTAG")]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    #[arg(long, default_value = "192.168.1.100")]
    xvc_host: String,

    #[arg(long, default_value_t = 2542)]
    xvc_port: u16,

    #[arg(long, default_value_t = 30_000)]
    timeout_ms: u64,
}

#[derive(Subcommand)]
enum Commands {
    Flash {
        #[arg(long)]
        bitstream: PathBuf,
        #[arg(long, default_value = "XC7A100T")]
        board: String,
    },
    FlashOpenocd {
        #[arg(long)]
        bitstream: PathBuf,
        #[arg(long, default_value = "fpga/openxc7-synth/ax7203_al321.cfg")]
        openocd_cfg: PathBuf,
    },
    Synth {
        #[arg(long)]
        rtl_dir: PathBuf,
        #[arg(long)]
        constraints: PathBuf,
        #[arg(long, default_value = "build")]
        output_dir: PathBuf,
        #[arg(long, default_value = "hslm_full_top")]
        top: String,
    },
    SynthVsa {
        #[arg(long, default_value = "build/vsa_matmul")]
        output_dir: PathBuf,
    },
    Status {},
    StatusOpenocd {
        #[arg(long, default_value = "fpga/openxc7-synth/ax7203_al321.cfg")]
        openocd_cfg: PathBuf,
    },
    Verify {},
    VerifyOpenocd {
        #[arg(long, default_value = "fpga/openxc7-synth/ax7203_al321.cfg")]
        openocd_cfg: PathBuf,
    },
    Bench {
        #[arg(long, default_value_t = 100)]
        iterations: u64,
        #[arg(long)]
        gf16_bin: Option<PathBuf>,
    },
}

fn resolve_board(name: &str) -> Option<&'static BoardConfig> {
    match name.to_uppercase().as_str() {
        "XC7A100T" | "ARTIX7-100T" => Some(&ARTIX7_100T),
        "XC7A200T" | "ARTIX7-200T" => Some(&ARTIX7_200T),
        "AX7203" | "ALINX-AX7203" | "XC7A200T-FBG484-2" => Some(&ALINX_AX7203),
        _ => None,
    }
}

fn run_openocd_verify(cfg: &PathBuf) -> anyhow::Result<()> {
    let output = Command::new("openocd")
        .arg("-f")
        .arg(cfg)
        .args([
            "-c", "init",
            "-c", "scan_chain",
            "-c", "shutdown",
        ])
        .output()
        .with_context(|| format!("run openocd with {}", cfg.display()))?;
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        bail!("openocd failed: {stderr}");
    }
    for line in stderr.lines() {
        if line.contains("found: 0x13636093") {
            println!("IDCODE: 0x13636093 — MATCH");
            return Ok(());
        }
    }
    bail!("IDCODE 0x13636093 not found in openocd output")
}

fn run_openocd_flash(cfg: &PathBuf, bitstream: &PathBuf) -> anyhow::Result<()> {
    let output = Command::new("openocd")
        .arg("-f")
        .arg(cfg)
        .args([
            "-c", "init",
            "-c", "xc7_program xc7.tap",
            "-c", &format!("pld load 0 {}", bitstream.display()),
            "-c", "shutdown",
        ])
        .output()
        .with_context(|| format!("run openocd with {}", cfg.display()))?;
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        bail!("openocd flash failed: {stderr}");
    }
    println!("OK: flashed {} via OpenOCD", bitstream.display());
    Ok(())
}

fn run_openocd_status(cfg: &PathBuf) -> anyhow::Result<()> {
    let output = Command::new("openocd")
        .arg("-f")
        .arg(cfg)
        .args([
            "-c", "init",
            "-c", "scan_chain",
            "-c", "shutdown",
        ])
        .output()
        .with_context(|| format!("run openocd with {}", cfg.display()))?;
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        bail!("openocd failed: {stderr}");
    }
    print!("{stderr}");
    Ok(())
}

fn make_xvc_config(cli: &Cli) -> anyhow::Result<XvcConfig> {
    let host: IpAddr = cli
        .xvc_host
        .parse()
        .map_err(|e| anyhow::anyhow!("invalid IP '{}': {}", cli.xvc_host, e))?;
    Ok(XvcConfig {
        host,
        port: cli.xvc_port,
        timeout_ms: cli.timeout_ms,
    })
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    let xvc = make_xvc_config(&cli)?;

    match &cli.command {
        Commands::Flash {
            bitstream,
            board,
        } => {
            let board_cfg = resolve_board(board)
                .ok_or_else(|| anyhow::anyhow!("unknown board '{board}'. Use XC7A100T, XC7A200T or AX7203"))?;
            let flasher = trios_fpga_fp02::XvcFlasher::new(xvc, board_cfg);

            eprintln!("Flashing {} via XVC...", bitstream.display());
            let result = flasher.flash_file(bitstream)?;
            eprintln!(
                "OK: {} bytes, IDCODE=0x{:08X}, done={}, {:.2}s",
                result.bytes_written,
                result.idcode,
                result.done,
                result.elapsed.as_secs_f64()
            );
        }
        Commands::FlashOpenocd {
            bitstream,
            openocd_cfg,
        } => {
            eprintln!("Flashing {} via OpenOCD (AL321)...", bitstream.display());
            run_openocd_flash(openocd_cfg, bitstream)?;
        }

        Commands::Synth {
            rtl_dir,
            constraints,
            output_dir,
            top,
        } => {
            let config = trios_fpga_fp01::SynthConfig::for_board(
                &ARTIX7_200T,
                rtl_dir,
                constraints,
                output_dir,
            );
            let runner = trios_fpga_fp01::OpenXc7Runner::new(config);

            eprintln!("Synthesizing {}...", top);
            let result = runner.synthesize()?;
            eprintln!("OK: {}", result.bit_path.display());
        }

        Commands::SynthVsa { output_dir } => {
            let config = trios_fpga_fp01::SynthConfig::vsa_matmul(&ARTIX7_200T, output_dir);
            let runner = trios_fpga_fp01::OpenXc7Runner::new(config);

            eprintln!("Synthesizing vsa_matmul_top (VSA ternary, 0 DSP)...");
            let result = runner.synthesize()?;
            eprintln!("OK: {}", result.bit_path.display());
        }

        Commands::Status {} => {
            let board = resolve_board("AX7203").unwrap_or(&ARTIX7_100T);
            let flasher = trios_fpga_fp02::XvcFlasher::new(xvc, board);
            let status = flasher.status()?;
            print!("{status}");
        }
        Commands::StatusOpenocd { openocd_cfg } => {
            run_openocd_status(openocd_cfg)?;
        }
        Commands::Verify {} => {
            let board = resolve_board("AX7203").unwrap_or(&ARTIX7_100T);
            let flasher = trios_fpga_fp02::XvcFlasher::new(xvc, board);
            let idcode = flasher.verify_idcode()?;
            println!("IDCODE: 0x{idcode:08X} — MATCH");
        }
        Commands::VerifyOpenocd { openocd_cfg } => {
            run_openocd_verify(openocd_cfg)?;
        }

        Commands::Bench { iterations, gf16_bin } => {
            let dim: usize = 64;
            let n_out: usize = 64;
            let conv = trios_fpga_fp01::TernaryWeightConverter::default();

            let x_trits: Vec<TritValue> = (0..dim).map(|i| {
                if i % 3 == 0 { TritValue::PlusOne }
                else if i % 3 == 1 { TritValue::MinusOne }
                else { TritValue::Zero }
            }).collect();

            let w_trits: Vec<Vec<TritValue>> = (0..n_out).map(|j| {
                (0..dim).map(|i| {
                    match (i + j) % 3 {
                        0 => TritValue::PlusOne,
                        1 => TritValue::MinusOne,
                        _ => TritValue::Zero,
                    }
                }).collect()
            }).collect();

            let t0 = Instant::now();
            let mut total_tokens = 0u64;
            for _ in 0..*iterations {
                for row in w_trits.iter().take(n_out) {
                    let _sum: i32 = (0..dim).map(|i| {
                        let w = match row[i] { TritValue::PlusOne => 1i32, TritValue::MinusOne => -1i32, TritValue::Zero => 0i32 };
                        let x = match x_trits[i] { TritValue::PlusOne => 1i32, TritValue::MinusOne => -1i32, TritValue::Zero => 0i32 };
                        w * x
                    }).sum();
                }
                total_tokens += 1;
            }
            let elapsed = t0.elapsed();
            let tokens_per_sec = total_tokens as f64 / elapsed.as_secs_f64();
            let ns_per_token = elapsed.as_nanos() as f64 / total_tokens as f64;

            eprintln!("CPU ternary matmul benchmark ({dim}x{n_out}):");
            eprintln!("  iterations: {total_tokens}");
            eprintln!("  total time: {:.3}s", elapsed.as_secs_f64());
            eprintln!("  tokens/sec: {tokens_per_sec:.1}");
            eprintln!("  ns/token:   {ns_per_token:.1}");
            eprintln!();
            eprintln!("FPGA estimate (81.25 MHz, ~65 cycles/token):");
            let fpga_tokens_per_sec = 81_250_000.0 / 65.0;
            let speedup = fpga_tokens_per_sec / tokens_per_sec;
            eprintln!("  tokens/sec: {fpga_tokens_per_sec:.0}");
            eprintln!("  speedup vs CPU: {speedup:.1}x");

            if let Some(bin_path) = gf16_bin {
                let gf16 = trios_fpga_fp01::Gf16Binary::from_file(bin_path)?;
                eprintln!();
                eprintln!("GF16 binary: {} tensors", gf16.tensors.len());
                for t in &gf16.tensors {
                    let tw = conv.convert_tensor(t);
                    let nz: usize = tw.rows * tw.cols;
                    eprintln!("  {} ({}x{}) -> {} packed words, {} trits", tw.name, tw.rows, tw.cols, tw.packed.len(), nz);
                }
            }
        }
    }

    Ok(())
}
