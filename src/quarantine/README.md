# Quarantine

These modules do NOT compile (Zig 0.16 API drift, 17+ errors each).

## token_ffi.zig
- keccak256() actually runs SHA256 (security-critical bug)
- 17 TODO stubs: getNonce, estimateGas, sendRawTransaction, ECDSA, RLP — none implemented
- Mixed ArrayList API (managed vs unmanaged) — compiles on neither 0.13 nor 0.14

## wallet_commands.zig
- 10+ compile errors: defer-return, @memset 3-args, undefined parseAddress
- Calls nonexistent free functions
- Fundamentally broken Zig — not salvageable without rewrite

Do NOT import from production code.
