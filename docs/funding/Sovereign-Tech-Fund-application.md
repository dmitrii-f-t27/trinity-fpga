# Sovereign Tech Fund — Grant Application
## Trinity GF16 Open Source Hardware Toolchain
### URL: https://sovereigntechfund.de/en/programs/
### Amount: €100,000–€250,000
### Programme: Sovereign Tech Fund Invest

---

## ABOUT STF

Sovereign Tech Fund (Germany, funded by BMBF) invests in open-source digital infrastructure.
Past recipients: curl ($150K), OpenSSL ($900K), Sequoia PGP ($290K), WireGuard ($500K).

Trinity Stack = open-source silicon infrastructure = a fit.

---

## APPLICATION SUMMARY

**Project:** Trinity GF16 Open ASIC Toolchain

**Requested:** €150,000

**What it is:**
Open-source toolchain for ternary neural network inference on FPGA and ASIC:
- Rust CLI (`trios-fpga`) — synthesis, flash, bench
- RTL (`vsa_matmul.v`) — ternary matmul, 0 multipliers
- GF16 quantization library (`phi_numbers::gf16`)
- IHP SG13G2 tapeout pipeline

**Why it matters for digital sovereignty:**
- An alternative to proprietary AI chips (Nvidia, Qualcomm)
- Runs on $30 hardware, accessible to everyone
- Fully reproducible: open RTL + open PDK + open toolchain
- dePIN architecture — decentralized AI without Big Tech

**Deliverables:**
1. OpenLane2 flow for vsa_matmul.v (IHP SG13G2)
2. First Trinity silicon (130nm)
3. Published benchmarks + arXiv
4. Documentation for reproducibility

**Contact:** https://sovereigntechfund.de/en/contact/

*trinity-fpga/docs/funding/Sovereign-Tech-Fund-application.md*
