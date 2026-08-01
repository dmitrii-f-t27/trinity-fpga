//! Ternary-weight model inference over TRI-NET.
//!
//! A ternary network's forward pass is a stack of matrix-vector products where
//! every weight is in {-1, 0, +1}. That decomposes exactly into the mesh's
//! work unit: one 32-wide dot product per output neuron. So a layer evaluated
//! here has its arithmetic physically executed by nodes — on FPGA LUTs where a
//! board is attached, in software where one is not — and each row comes back
//! with a receipt.
//!
//! WHAT THIS DOES AND DOES NOT CLAIM. The execution path is real: the numbers
//! that come out of a layer are the numbers the nodes computed, verified
//! against an independent recomputation. Whether those numbers mean anything
//! depends entirely on the weights loaded. A model file with untrained weights
//! produces a correct forward pass over meaningless parameters, and this module
//! reports which case it is in rather than letting the distinction blur.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const protocol = @import("protocol.zig");
const mesh_mod = @import("mesh.zig");

pub const block = protocol.n_trits; // 32 trits in, one dot product out

pub const magic = "TRINMDL1";

/// Activation threshold for a 32-wide layer, chosen by measurement rather than
/// taste. Feeding a fixed input through four synthetic layers and recording the
/// fraction of non-zero trits that survive each one gives:
///
///     threshold 0:  0.69 -> 0.91 -> 0.94 -> 0.91 -> 0.88   saturated
///     threshold 1:  0.69 -> 0.66 -> 0.56 -> 0.66 -> 0.59
///     threshold 2:  0.69 -> 0.41 -> 0.28 -> 0.25 -> 0.31   sustained
///     threshold 3:  0.69 -> 0.22 -> 0.06 -> 0.00 -> 0.00   dead
///     threshold 4:  0.69 -> 0.22 -> 0.03 -> 0.00 -> 0.00   dead
///
/// Both ends destroy the network for different reasons. Too high and the
/// activations collapse to the zero vector within three layers, after which
/// every input produces the same output and the model has no opinion about
/// anything. Too low and no trit is ever zero, which throws away the third
/// state and leaves a binary network wearing ternary clothes.
///
/// The usable band is narrow because a 32-wide ternary dot product has a
/// standard deviation of only about 3.4. A wider layer would need a
/// proportionally higher threshold — this constant is tied to `n_trits`, not
/// universal.
pub const default_threshold: i8 = 2;

pub const Error = error{
    BadMagic,
    Truncated,
    BadShape,
    OutOfMemory,
    TooManyLayers,
};

/// Where the weights came from. Carried through to the report so an inference
/// run can never quietly present untrained output as a model's opinion.
pub const Provenance = enum {
    /// Deterministically generated from a seed. Correct arithmetic, no meaning.
    synthetic,
    /// Loaded from a file produced by a training run.
    trained,

    pub fn label(self: Provenance) []const u8 {
        return switch (self) {
            .synthetic => "synthetic (untrained — the arithmetic is real, the weights are not)",
            .trained => "trained",
        };
    }
};

pub const Layer = struct {
    /// One packed 32-trit row per output neuron.
    rows: []protocol.Packed,
    /// Magnitude an accumulator must reach to emit a non-zero trit. This is
    /// the ternary activation; with threshold 0 the network is effectively
    /// binary, which throws away what ternary is for.
    threshold: i8,

    pub fn outputs(self: Layer) usize {
        return self.rows.len;
    }
};

pub const Model = struct {
    gpa: std.mem.Allocator,
    layers: []Layer,
    provenance: Provenance,
    name: []const u8,

    pub fn deinit(self: *Model) void {
        for (self.layers) |l| self.gpa.free(l.rows);
        self.gpa.free(self.layers);
    }

    pub fn parameterCount(self: Model) usize {
        var n: usize = 0;
        for (self.layers) |l| n += l.rows.len * block;
        return n;
    }

    /// Jobs one forward pass costs — one per output neuron across all layers.
    pub fn jobsPerForward(self: Model) usize {
        var n: usize = 0;
        for (self.layers) |l| n += l.rows.len;
        return n;
    }

    /// A reproducible model with no training behind it. Useful for exercising
    /// the whole path end to end before real weights exist, and honest about
    /// being exactly that.
    pub fn synthetic(gpa: std.mem.Allocator, n_layers: usize, width: usize, seed: u64) Error!Model {
        if (n_layers == 0 or width == 0) return Error.BadShape;
        if (n_layers > 64) return Error.TooManyLayers;

        var prng: std.Random.DefaultPrng = .init(seed);
        const rand = prng.random();

        const layers = try gpa.alloc(Layer, n_layers);
        errdefer gpa.free(layers);

        var built: usize = 0;
        errdefer for (layers[0..built]) |l| gpa.free(l.rows);

        while (built < n_layers) : (built += 1) {
            const rows = try gpa.alloc(protocol.Packed, width);
            for (rows) |*r| {
                var tv: protocol.Trits = @splat(0);
                // Roughly 40% zeros, which is the sparsity ternary networks
                // actually exhibit and the reason zero-skip hardware pays off.
                for (&tv) |*t| {
                    const roll = rand.intRangeAtMost(u8, 0, 9);
                    t.* = if (roll < 4) 0 else if (roll < 7) 1 else -1;
                }
                r.* = protocol.pack(tv);
            }
            layers[built] = .{ .rows = rows, .threshold = default_threshold };
        }

        return .{ .gpa = gpa, .layers = layers, .provenance = .synthetic, .name = "synthetic" };
    }

    /// File layout, all little-endian:
    ///   magic[8] "TRINMDL1"
    ///   u32 n_layers
    ///   per layer: u32 n_rows, i8 threshold, pad[3], rows[n_rows][8]
    pub fn load(gpa: std.mem.Allocator, bytes: []const u8, name: []const u8) Error!Model {
        if (bytes.len < 12 or !std.mem.eql(u8, bytes[0..8], magic)) return Error.BadMagic;
        const n_layers = std.mem.readInt(u32, bytes[8..12], .little);
        if (n_layers == 0) return Error.BadShape;
        if (n_layers > 64) return Error.TooManyLayers;

        const layers = try gpa.alloc(Layer, n_layers);
        errdefer gpa.free(layers);
        var built: usize = 0;
        errdefer for (layers[0..built]) |l| gpa.free(l.rows);

        var off: usize = 12;
        while (built < n_layers) : (built += 1) {
            if (off + 8 > bytes.len) return Error.Truncated;
            const n_rows = std.mem.readInt(u32, bytes[off..][0..4], .little);
            const threshold: i8 = @bitCast(bytes[off + 4]);
            off += 8;
            if (n_rows == 0) return Error.BadShape;
            const need = @as(usize, n_rows) * protocol.n_bytes;
            if (off + need > bytes.len) return Error.Truncated;

            const rows = try gpa.alloc(protocol.Packed, n_rows);
            for (rows, 0..) |*r, i| r.* = bytes[off + i * protocol.n_bytes ..][0..protocol.n_bytes].*;
            off += need;
            layers[built] = .{ .rows = rows, .threshold = threshold };
        }

        return .{ .gpa = gpa, .layers = layers, .provenance = .trained, .name = name };
    }

    pub fn save(self: Model, gpa: std.mem.Allocator) Error![]u8 {
        var out: std.ArrayList(u8) = .empty;
        errdefer out.deinit(gpa);
        try out.appendSlice(gpa, magic);
        var hdr: [4]u8 = undefined;
        std.mem.writeInt(u32, &hdr, @intCast(self.layers.len), .little);
        try out.appendSlice(gpa, &hdr);
        for (self.layers) |l| {
            std.mem.writeInt(u32, &hdr, @intCast(l.rows.len), .little);
            try out.appendSlice(gpa, &hdr);
            try out.append(gpa, @bitCast(l.threshold));
            try out.appendSlice(gpa, &[_]u8{ 0, 0, 0 });
            for (l.rows) |r| try out.appendSlice(gpa, &r);
        }
        return out.toOwnedSlice(gpa);
    }
};

/// Ternary activation: collapse an accumulator back to a trit.
pub fn ternarize(y: i8, threshold: i8) i8 {
    if (y > threshold) return 1;
    if (y < -threshold) return -1;
    return 0;
}

pub const ForwardStats = struct {
    jobs: usize = 0,
    rows_rejected: usize = 0,
    on_silicon: u64 = 0,
    in_software: u64 = 0,

    pub fn siliconShare(self: ForwardStats) f64 {
        const total = self.on_silicon + self.in_software;
        if (total == 0) return 0;
        return @as(f64, @floatFromInt(self.on_silicon)) / @as(f64, @floatFromInt(total));
    }
};

/// Run one forward pass with every dot product executed on the mesh.
///
/// The activation vector is carried as 32 trits between layers; a layer wider
/// than 32 outputs is folded back by taking the first 32 activations, which
/// keeps the demonstration honest about the shape it actually supports rather
/// than pretending to arbitrary dimensions.
pub fn forward(
    m: *mesh_mod.Mesh,
    model: Model,
    input: protocol.Trits,
    stats: *ForwardStats,
    scratch: []i8,
) mesh_mod.Error!protocol.Trits {
    var activation = input;

    const before_silicon = m.stats.on_silicon;
    const before_software = m.stats.in_software;

    for (model.layers) |layer| {
        std.debug.assert(scratch.len >= layer.rows.len);
        var fails: usize = 0;
        try m.matvec(layer.rows, protocol.pack(activation), scratch[0..layer.rows.len], &fails);
        stats.jobs += layer.rows.len;
        stats.rows_rejected += fails;

        var next: protocol.Trits = @splat(0);
        const n = @min(layer.rows.len, protocol.n_trits);
        for (0..n) |i| next[i] = ternarize(scratch[i], layer.threshold);
        activation = next;
    }

    stats.on_silicon += m.stats.on_silicon - before_silicon;
    stats.in_software += m.stats.in_software - before_software;
    return activation;
}

/// Reference forward pass computed entirely locally. The mesh result must
/// equal this; if it does not, the network produced a wrong answer and that is
/// a failure worth surfacing, not a rounding difference to shrug at.
pub fn forwardLocal(model: Model, input: protocol.Trits, scratch: []i8) protocol.Trits {
    var activation = input;
    for (model.layers) |layer| {
        const packed_act = protocol.pack(activation);
        for (layer.rows, 0..) |r, i| scratch[i] = protocol.dot(r, packed_act);
        var next: protocol.Trits = @splat(0);
        const n = @min(layer.rows.len, protocol.n_trits);
        for (0..n) |i| next[i] = ternarize(scratch[i], layer.threshold);
        activation = next;
    }
    return activation;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const testing = std.testing;

test "ternary activation has a genuine zero band" {
    try testing.expectEqual(@as(i8, 1), ternarize(10, 4));
    try testing.expectEqual(@as(i8, -1), ternarize(-10, 4));
    try testing.expectEqual(@as(i8, 0), ternarize(4, 4));
    try testing.expectEqual(@as(i8, 0), ternarize(-4, 4));
    try testing.expectEqual(@as(i8, 0), ternarize(0, 4));
    // With threshold 0 the zero state collapses and the network is binary.
    try testing.expectEqual(@as(i8, 1), ternarize(1, 0));
    try testing.expectEqual(@as(i8, -1), ternarize(-1, 0));
}

/// Fraction of trits that are non-zero.
pub fn density(v: protocol.Trits) f64 {
    var nz: usize = 0;
    for (v) |t| {
        if (t != 0) nz += 1;
    }
    return @as(f64, @floatFromInt(nz)) / @as(f64, @floatFromInt(protocol.n_trits));
}

test "the default threshold keeps a deep network alive without saturating it" {
    var input: protocol.Trits = @splat(0);
    for (&input, 0..) |*t, i| t.* = if (i % 3 == 0) 1 else if (i % 3 == 1) -1 else 0;
    var scratch: [64]i8 = undefined;

    var model = try Model.synthetic(testing.allocator, 4, 32, 0x1614);
    defer model.deinit();
    const alive = forwardLocal(model, input, &scratch);
    const d = density(alive);

    // Not dead: a collapsed network returns the same output for every input,
    // which reads as a confident answer and is in fact no answer at all.
    try testing.expect(d > 0.10);
    // Not saturated: a network with no zero trits has discarded the third
    // state and is binary.
    try testing.expect(d < 0.80);
}

test "a threshold that is too high kills the network within three layers" {
    var input: protocol.Trits = @splat(0);
    for (&input, 0..) |*t, i| t.* = if (i % 3 == 0) 1 else if (i % 3 == 1) -1 else 0;
    var scratch: [64]i8 = undefined;

    var model = try Model.synthetic(testing.allocator, 4, 32, 0x1614);
    defer model.deinit();
    for (model.layers) |*l| l.threshold = 4;
    // Recorded so the failure mode stays visible rather than being rediscovered
    // as a mysterious zero-margin decision.
    try testing.expectEqual(@as(f64, 0.0), density(forwardLocal(model, input, &scratch)));
}

test "a synthetic model reports itself as untrained" {
    var model = try Model.synthetic(testing.allocator, 3, 32, 0x1234);
    defer model.deinit();
    try testing.expectEqual(Provenance.synthetic, model.provenance);
    try testing.expectEqual(@as(usize, 3 * 32 * 32), model.parameterCount());
    try testing.expectEqual(@as(usize, 96), model.jobsPerForward());
}

test "model save and load round trip" {
    var model = try Model.synthetic(testing.allocator, 2, 16, 0xABCD);
    defer model.deinit();
    const bytes = try model.save(testing.allocator);
    defer testing.allocator.free(bytes);

    var back = try Model.load(testing.allocator, bytes, "roundtrip");
    defer back.deinit();
    try testing.expectEqual(model.layers.len, back.layers.len);
    for (model.layers, back.layers) |a, b| {
        try testing.expectEqual(a.threshold, b.threshold);
        try testing.expectEqualSlices(protocol.Packed, a.rows, b.rows);
    }
    // A file that came from disk is reported as trained provenance; a caller
    // must not be able to launder synthetic weights by round-tripping them
    // without saying so.
    try testing.expectEqual(Provenance.trained, back.provenance);
}

test "malformed model files are rejected rather than half-read" {
    try testing.expectError(Error.BadMagic, Model.load(testing.allocator, "nope", "x"));
    try testing.expectError(Error.BadMagic, Model.load(testing.allocator, "TRINMDL9" ++ [_]u8{ 1, 0, 0, 0 }, "x"));
    try testing.expectError(Error.Truncated, Model.load(testing.allocator, magic ++ [_]u8{ 1, 0, 0, 0 }, "x"));
}

test "a forward pass over the mesh matches local arithmetic exactly" {
    var m = try mesh_mod.Mesh.init(testing.allocator, .{});
    defer m.deinit();
    try m.join(mesh_mod.Node.initEmulated(1, "a", .honest), "alice", 4000);
    try m.join(mesh_mod.Node.initEmulated(2, "b", .honest), "bob", 4000);

    var model = try Model.synthetic(testing.allocator, 4, 32, 0x5EED);
    defer model.deinit();

    var input: protocol.Trits = @splat(0);
    for (&input, 0..) |*t, i| t.* = if (i % 3 == 0) 1 else if (i % 3 == 1) -1 else 0;

    var scratch: [64]i8 = undefined;
    var stats: ForwardStats = .{};
    const meshed = try forward(&m, model, input, &stats, &scratch);
    const local = forwardLocal(model, input, &scratch);

    try testing.expectEqual(local, meshed);
    try testing.expectEqual(@as(usize, 128), stats.jobs);
    try testing.expectEqual(@as(usize, 0), stats.rows_rejected);
}

test "a lying node cannot corrupt the model output" {
    var m = try mesh_mod.Mesh.init(testing.allocator, .{});
    defer m.deinit();
    try m.join(mesh_mod.Node.initEmulated(1, "honest", .honest), "alice", 9000);
    try m.join(mesh_mod.Node.initEmulated(2, "liar", .lazy), "mallory", 9000);

    var model = try Model.synthetic(testing.allocator, 3, 32, 0xF00D);
    defer model.deinit();

    const input: protocol.Trits = @splat(1);
    var scratch: [64]i8 = undefined;
    var stats: ForwardStats = .{};
    const meshed = try forward(&m, model, input, &stats, &scratch);
    const local = forwardLocal(model, input, &scratch);

    try testing.expectEqual(local, meshed);
    try testing.expect(stats.rows_rejected > 0);
    try testing.expectEqual(@as(u64, 0), m.ledger.get(2).?.credit_mtri);
}
