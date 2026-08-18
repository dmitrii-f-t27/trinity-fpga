//! The `vsa` module, restored to what still exists.
//!
//! This file supplied the named module `vsa` to the `tri` build. It was
//! deleted by 9da363bc5 ("extract zig-hdc (Hyperdimensional Computing) to
//! separate repository") along with the whole `src/vsa/` directory, and the
//! build definition that referenced it was deleted separately -- so nothing
//! reported the break until the CLI was compiled again.
//!
//! The original re-exported seven siblings: common, core, encoding, storage,
//! concurrency, agent, hrr. Six went to zig-hdc and are not restored here;
//! re-vendoring code that was deliberately extracted would undo that work.
//! `hrr.zig` is restored because it is the only one anything in this tree
//! still uses -- `src/tri/tri_vsa.zig` and `src/tri/clara/verification.zig`
//! reach for `HRR` and nothing else -- and because it depends on `std` alone,
//! so it costs no submodule.
//!
//! If a future caller needs `core`, `encoding` or the rest, take them from
//! zig-hdc as a dependency rather than copying them back.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

pub const HRR = @import("vsa/hrr.zig").HRR;

test {
    // Force the re-export to compile, so a break in hrr.zig surfaces here
    // rather than at the first caller.
    _ = HRR;
}
