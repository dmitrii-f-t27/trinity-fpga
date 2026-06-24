#![doc = include_str!("../README.md")]

use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use trios_fpga_fp00::{BoardConfig, JtagConfig, XvcConfig};

const XVC_INFO_CMD: &[u8] = b"getinfo:";

const IR_IDCODE: u8 = 0x09;
const IR_CFG_IN: u8 = 0x05;
const IR_CFG_OUT: u8 = 0x04;
const IR_JPROGRAM: u8 = 0x0B;
const IR_JSTART: u8 = 0x0C;
const IR_BYPASS: u8 = 0x3F;
const IR_WIDTH: u32 = 6;
const TDO_DELAY: usize = 0;

const REVERSE_BYTE: [u8; 256] = [
    0, 128, 64, 192, 32, 160, 96, 224, 16, 144, 80, 208, 48, 176, 112, 240,
    8, 136, 72, 200, 40, 168, 104, 232, 24, 152, 88, 216, 56, 184, 120, 248,
    4, 132, 68, 196, 36, 164, 100, 228, 20, 148, 84, 212, 52, 180, 116, 244,
    12, 140, 76, 204, 44, 172, 108, 236, 28, 156, 92, 220, 60, 188, 124, 252,
    2, 130, 66, 194, 34, 162, 98, 226, 18, 146, 82, 210, 50, 178, 114, 242,
    10, 138, 74, 202, 42, 170, 106, 234, 26, 154, 90, 218, 58, 186, 122, 250,
    6, 134, 70, 198, 38, 166, 102, 230, 22, 150, 86, 214, 54, 182, 118, 246,
    14, 142, 78, 206, 46, 174, 110, 238, 30, 158, 94, 222, 62, 190, 126, 254,
    1, 129, 65, 193, 33, 161, 97, 225, 17, 145, 81, 209, 49, 177, 113, 241,
    9, 137, 73, 201, 41, 169, 105, 233, 25, 153, 89, 217, 57, 185, 121, 249,
    5, 133, 69, 197, 37, 165, 101, 229, 21, 149, 85, 213, 53, 181, 117, 245,
    13, 141, 77, 205, 45, 173, 109, 237, 29, 157, 93, 221, 61, 189, 125, 253,
    3, 131, 67, 195, 35, 163, 99, 227, 19, 147, 83, 211, 51, 179, 115, 243,
    11, 139, 75, 203, 43, 171, 107, 235, 27, 155, 91, 219, 59, 187, 123, 251,
    7, 135, 71, 199, 39, 167, 103, 231, 23, 151, 87, 215, 55, 183, 119, 247,
    15, 143, 79, 207, 47, 175, 111, 239, 31, 159, 95, 223, 63, 191, 127, 255,
];

#[derive(Debug)]
pub struct FlashResult {
    pub bytes_written: usize,
    pub idcode: u32,
    pub elapsed: Duration,
    pub done: bool,
}

#[derive(Debug)]
pub enum FlashError {
    Connection(String),
    Protocol(String),
    Verify { expected: u32, got: u32 },
    Timeout,
}

impl std::fmt::Display for FlashError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FlashError::Connection(e) => write!(f, "connection: {e}"),
            FlashError::Protocol(e) => write!(f, "protocol: {e}"),
            FlashError::Verify { expected, got } => {
                write!(f, "IDCODE mismatch: expected 0x{expected:08X}, got 0x{got:08X}")
            }
            FlashError::Timeout => write!(f, "timeout"),
        }
    }
}
impl std::error::Error for FlashError {}

pub struct XvcFlasher {
    pub xvc: XvcConfig,
    pub jtag: JtagConfig,
    pub board: &'static BoardConfig,
}

impl XvcFlasher {
    pub fn new(xvc: XvcConfig, board: &'static BoardConfig) -> Self {
        Self {
            xvc,
            jtag: JtagConfig::default(),
            board,
        }
    }

    pub fn connect(&self) -> Result<XvcConnection> {
        let addr = format!("{}:{}", self.xvc.host, self.xvc.port);
        let stream = TcpStream::connect_timeout(
            &addr.parse().with_context(|| format!("parse address {addr}"))?,
            Duration::from_millis(self.xvc.timeout_ms),
        )
        .with_context(|| format!("connect to XVC at {addr}"))?;

        stream.set_read_timeout(Some(Duration::from_millis(self.xvc.timeout_ms)))?;
        stream.set_write_timeout(Some(Duration::from_millis(self.xvc.timeout_ms)))?;

        Ok(XvcConnection { stream })
    }

    pub fn verify_idcode(&self) -> Result<u32> {
        let mut conn = self.connect()?;
        let _info = conn.get_info().context("get XVC info")?;

        conn.tap_reset()?;
        conn.go_to_rti()?;
        let idcode = conn.read_dr(32)?;

        if idcode != self.board.idcode {
            bail!(FlashError::Verify {
                expected: self.board.idcode,
                got: idcode,
            });
        }
        Ok(idcode)
    }

    pub fn flash(&self, bitstream: &[u8]) -> Result<FlashResult> {
        let start = std::time::Instant::now();
        let mut conn = self.connect()?;
        let _info = conn.get_info().context("get XVC info")?;

        conn.tap_reset()?;
        conn.go_to_rti()?;

        let idcode = conn.read_dr(32)?;
        if idcode != self.board.idcode {
            bail!(FlashError::Verify {
                expected: self.board.idcode,
                got: idcode,
            });
        }

        conn.shift_ir(IR_JPROGRAM)?;

        let mut init_b = false;
        for _ in 0..500 {
            let capture = conn.shift_ir_capture(IR_BYPASS)?;
            if (capture & 0x10) != 0 {
                init_b = true;
                break;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        if !init_b {
            bail!("INIT_B timeout: FPGA config memory not cleared after 5s");
        }

        conn.rti_clocks(120_000)?;

        conn.shift_ir(IR_CFG_IN)?;

        conn.enter_shift_dr()?;
        let raw_data = Self::extract_bitstream_data(bitstream);
        let rev_data: Vec<u8> = raw_data.iter().map(|&b| REVERSE_BYTE[b as usize]).collect();
        let mut remaining: usize = rev_data.len();
        for chunk in rev_data.chunks(16384) {
            remaining -= chunk.len();
            let bits = (chunk.len() * 8) as u32;
            if remaining == 0 {
                conn.shift_dr_last(chunk, bits)?;
            } else {
                conn.shift_dr_continue(chunk, bits)?;
            }
        }
        conn.exit_to_rti()?;

        conn.shift_ir(IR_JSTART)?;
        conn.rti_clocks(2000)?;

        conn.tap_reset()?;
        conn.go_to_rti()?;
        let capture = conn.shift_ir_capture(IR_BYPASS)?;
        let done = (capture >> 5) & 1 == 1;

        Ok(FlashResult {
            bytes_written: raw_data.len(),
            idcode,
            elapsed: start.elapsed(),
            done,
        })
    }

    fn extract_bitstream_data(raw: &[u8]) -> &[u8] {
        for i in 0..raw.len().saturating_sub(5) {
            if raw[i] == 0x65 {
                let len = ((raw[i + 1] as usize) << 24)
                    | ((raw[i + 2] as usize) << 16)
                    | ((raw[i + 3] as usize) << 8)
                    | (raw[i + 4] as usize);
                let start = i + 5;
                if start + len <= raw.len() && len > 100_000 {
                    return &raw[start..start + len];
                }
            }
        }
        raw
    }

    pub fn flash_file(&self, path: &Path) -> Result<FlashResult> {
        let data = std::fs::read(path)
            .with_context(|| format!("read bitstream {}", path.display()))?;
        self.flash(&data)
    }

    pub fn status(&self) -> Result<DeviceStatus> {
        let mut conn = self.connect()?;
        let _info = conn.get_info().context("get XVC info")?;

        conn.tap_reset()?;
        conn.go_to_rti()?;
        let idcode = conn.read_dr(32)?;

        conn.shift_ir(IR_CFG_OUT)?;
        let raw = conn.read_dr(32)?;

        conn.shift_ir(IR_BYPASS)?;

        Ok(DeviceStatus {
            idcode,
            done: (raw >> 14) & 1 == 1,
            init_b: (raw >> 12) & 1 == 1,
            crc_error: (raw >> 5) & 1 == 1,
            id_error: (raw >> 4) & 1 == 1,
            raw,
        })
    }
}

#[derive(Debug)]
pub struct DeviceStatus {
    pub idcode: u32,
    pub done: bool,
    pub init_b: bool,
    pub crc_error: bool,
    pub id_error: bool,
    pub raw: u32,
}

impl std::fmt::Display for DeviceStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "STATUS: 0x{:08X}\n", self.raw)?;
        write!(f, "  IDCODE: 0x{:08X}\n", self.idcode)?;
        write!(f, "  DONE:   {}{}\n", if self.done { "1 (YES)" } else { "0 (NO)" }, if self.done { " ← configured!" } else { "" })?;
        write!(f, "  INIT_B: {}{}\n", if self.init_b { "1" } else { "0" }, if !self.init_b { " ← error!" } else { "" })?;
        write!(f, "  CRC:    {}{}\n", if self.crc_error { "1" } else { "0" }, if self.crc_error { " ← ERROR!" } else { "" })?;
        write!(f, "  ID:     {}{}\n", if self.id_error { "1" } else { "0" }, if self.id_error { " ← ERROR!" } else { "" })
    }
}

pub struct XvcConnection {
    stream: TcpStream,
}

#[derive(Debug)]
pub struct XvcInfo {
    pub version: String,
    pub max_bits: u32,
}

impl XvcConnection {
    pub fn get_info(&mut self) -> Result<XvcInfo> {
        self.stream.write_all(XVC_INFO_CMD)?;
        self.stream.flush()?;

        let mut buf = [0u8; 256];
        let n = self.stream.read(&mut buf)?;
        let resp = String::from_utf8_lossy(&buf[..n]);
        let parts: Vec<&str> = resp.split(':').collect();

        if parts.len() < 2 {
            bail!("invalid XVC info response: {resp}");
        }

        Ok(XvcInfo {
            version: parts[0].to_string(),
            max_bits: parts[1].trim().parse().unwrap_or(0),
        })
    }

    fn xvc_raw_shift(&mut self, bits: u32, tms: &[u8], tdi: &[u8]) -> Result<Vec<u8>> {
        let nbytes = bits.div_ceil(8) as usize;
        let mut cmd = Vec::with_capacity(6 + 4 + nbytes * 2);
        cmd.extend_from_slice(b"shift:");
        cmd.extend_from_slice(&bits.to_le_bytes());
        cmd.extend_from_slice(&tms[..nbytes]);
        cmd.extend_from_slice(&tdi[..nbytes]);
        self.stream.write_all(&cmd)?;
        self.stream.flush()?;

        let mut tdo = vec![0u8; nbytes];
        self.stream.read_exact(&mut tdo)?;
        Ok(tdo)
    }

    fn tap_reset(&mut self) -> Result<()> {
        let tms = [0x1Fu8];
        let tdi = [0x00u8];
        self.xvc_raw_shift(5, &tms, &tdi)?;
        Ok(())
    }

    fn go_to_rti(&mut self) -> Result<()> {
        let tms = [0x00u8];
        let tdi = [0x00u8];
        self.xvc_raw_shift(1, &tms, &tdi)?;
        Ok(())
    }

    fn shift_ir(&mut self, instruction: u8) -> Result<()> {
        let total = IR_WIDTH + 6;
        let total_bytes = total.div_ceil(8) as usize;
        let mut tms = vec![0u8; total_bytes];
        let mut tdi = vec![0u8; total_bytes];

        tms[0] = 0x03;

        for i in 0..IR_WIDTH as usize {
            let tdi_bit = (instruction >> i) & 1;
            let pos = 4 + i;
            tdi[pos / 8] |= tdi_bit << (pos % 8);
        }

        let last_data = (4 + IR_WIDTH - 1) as usize;
        tms[last_data / 8] |= 1 << (last_data % 8);

        let exit1 = (4 + IR_WIDTH) as usize;
        tms[exit1 / 8] |= 1 << (exit1 % 8);

        self.xvc_raw_shift(total, &tms, &tdi)?;
        Ok(())
    }

    fn shift_ir_capture(&mut self, instruction: u8) -> Result<u8> {
        let total = IR_WIDTH + 6;
        let total_bytes = total.div_ceil(8) as usize;
        let mut tms = vec![0u8; total_bytes];
        let mut tdi = vec![0u8; total_bytes];

        tms[0] = 0x03;

        for i in 0..IR_WIDTH as usize {
            let tdi_bit = (instruction >> i) & 1;
            let pos = 4 + i;
            tdi[pos / 8] |= tdi_bit << (pos % 8);
        }

        let last_data = (4 + IR_WIDTH - 1) as usize;
        tms[last_data / 8] |= 1 << (last_data % 8);

        let exit1 = (4 + IR_WIDTH) as usize;
        tms[exit1 / 8] |= 1 << (exit1 % 8);

        let tdo = self.xvc_raw_shift(total, &tms, &tdi)?;

        let mut capture = 0u8;
        for i in 0..IR_WIDTH as usize {
            let bp = 4 + i;
            if bp / 8 < tdo.len() {
                capture |= ((tdo[bp / 8] >> (bp % 8)) & 1) << i;
            }
        }
        Ok(capture)
    }

    fn read_dr(&mut self, bits: u32) -> Result<u32> {
        let total = bits + 5;
        let total_bytes = total.div_ceil(8) as usize;
        let mut tms = vec![0u8; total_bytes];
        let tdi = vec![0u8; total_bytes];

        tms[0] = 0x01;

        let last_data = (3 + bits - 1) as usize;
        tms[last_data / 8] |= 1 << (last_data % 8);

        let exit1 = (3 + bits) as usize;
        tms[exit1 / 8] |= 1 << (exit1 % 8);

        let tdo = self.xvc_raw_shift(total, &tms, &tdi)?;

        let data_start = 3 + TDO_DELAY;
        let mut result = 0u32;
        for i in 0..bits as usize {
            let bp = data_start + i;
            if bp / 8 < tdo.len() {
                result |= (((tdo[bp / 8] >> (bp % 8)) & 1) as u32) << i;
            }
        }
        Ok(result)
    }

    fn enter_shift_dr(&mut self) -> Result<()> {
        let tms = [0x01u8];
        let tdi = [0x00u8];
        self.xvc_raw_shift(3, &tms, &tdi)?;
        Ok(())
    }

    fn shift_dr_continue(&mut self, data: &[u8], bits: u32) -> Result<()> {
        let nbytes = bits.div_ceil(8) as usize;
        let tms = vec![0u8; nbytes];
        self.xvc_raw_shift(bits, &tms, &data[..nbytes])?;
        Ok(())
    }

    fn shift_dr_last(&mut self, data: &[u8], bits: u32) -> Result<()> {
        let nbytes = bits.div_ceil(8) as usize;
        let mut tms = vec![0u8; nbytes];
        let last_bit = (bits - 1) as usize;
        tms[last_bit / 8] |= 1 << (last_bit % 8);
        self.xvc_raw_shift(bits, &tms, &data[..nbytes])?;
        Ok(())
    }

    fn exit_to_rti(&mut self) -> Result<()> {
        let tms = [0x01u8];
        let tdi = [0x00u8];
        self.xvc_raw_shift(2, &tms, &tdi)?;
        Ok(())
    }

    fn rti_clocks(&mut self, count: u32) -> Result<()> {
        let chunk_bits = 16384 * 8;
        let mut remaining = count;
        while remaining > 0 {
            let bits = remaining.min(chunk_bits);
            let nbytes = bits.div_ceil(8) as usize;
            let tms = vec![0u8; nbytes];
            let tdi = vec![0u8; nbytes];
            self.xvc_raw_shift(bits, &tms, &tdi)?;
            remaining -= bits;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use trios_fpga_fp00::ARTIX7_200T;

    #[test]
    fn flasher_creation() {
        let xvc = XvcConfig::default();
        let flasher = XvcFlasher::new(xvc, &ARTIX7_200T);
        assert_eq!(flasher.board.idcode, 0x13636093);
        assert_eq!(flasher.xvc.port, 2542);
    }

    // NOTE: this test was previously broken because DeviceStatus gained new fields
    // (init_b, crc_error, id_error, raw) but the test initializer was not updated.
    // Fixed here so the struct is fully initialized.
    #[test]
    fn device_status_display() {
        let status = DeviceStatus {
            idcode: 0x13636093,
            done: true,
            init_b: true,
            crc_error: false,
            id_error: false,
            raw: 0x00004000,
        };
        assert!(status.done);
        assert_eq!(status.idcode, 0x13636093);
    }

    #[test]
    fn flash_error_display() {
        let err = FlashError::Verify {
            expected: 0x13636093,
            got: 0xDEAD,
        };
        let msg = format!("{err}");
        assert!(msg.contains("13636093"));
        assert!(msg.contains("0000DEAD"));
    }

    #[test]
    fn jtag_config_defaults() {
        let cfg = JtagConfig::default();
        assert_eq!(cfg.chain_speed_khz, 15_000);
        assert_eq!(cfg.retry_count, 3);
    }
}
