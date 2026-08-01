//! The IGLA CODER agent — an agent whose arithmetic happens on TRI-NET.
//!
//! The agent takes a task in text, encodes it into a ternary hypervector,
//! runs it through a ternary-weight model whose every dot product is executed
//! by mesh nodes, and reads an action out of the result. What comes back with
//! the answer is a proof bundle: how many jobs ran, on which nodes, how many
//! on real silicon, and how much credit that work earned.
//!
//! ON THE NAME. "IGLA CODER" in this repository's issue tracker refers to a
//! training programme (t27 #1037-#1041) whose deliverable is a code model. The
//! agent here is the *execution* half of that story: the substrate a ternary
//! code model would run on, with the model itself a loadable file. When no
//! trained weight file is supplied the agent runs synthetic weights and says
//! so in every report it produces. The distinction matters — a real inference
//! path over meaningless parameters is a real inference path, and calling it a
//! working code model would be a lie.
//!
//! ENCODING. Tasks are encoded the way this project encodes everything else:
//! vector-symbolic. Each token maps to a deterministic ternary hypervector,
//! the token vectors are bundled by majority, and position is bound in by
//! rotation so that word order carries information. This is a real VSA
//! encoder, not a placeholder.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const protocol = @import("protocol.zig");
const mesh_mod = @import("mesh.zig");
const model_mod = @import("model.zig");

pub const Error = mesh_mod.Error;

/// Actions a coder agent can select between. Deliberately small and concrete:
/// an action set that cannot be evaluated is not worth generating.
pub const Action = enum {
    read_code,
    write_test,
    fix_build,
    refactor,
    run_synthesis,
    flash_hardware,
    write_docs,
    ask_operator,

    pub fn label(self: Action) []const u8 {
        return switch (self) {
            .read_code => "read the code",
            .write_test => "write a test",
            .fix_build => "fix the build",
            .refactor => "refactor",
            .run_synthesis => "run synthesis",
            .flash_hardware => "flash hardware",
            .write_docs => "write documentation",
            .ask_operator => "ask the operator",
        };
    }
};

pub const action_count = @typeInfo(Action).@"enum".fields.len;

/// Deterministic ternary hypervector for an arbitrary string.
pub fn symbolVector(text: []const u8, salt: u64) protocol.Trits {
    var prng: std.Random.DefaultPrng = .init(std.hash.Wyhash.hash(salt, text));
    const rand = prng.random();
    var v: protocol.Trits = @splat(0);
    for (&v) |*t| {
        const roll = rand.intRangeAtMost(u8, 0, 9);
        // Sparse by construction: about 40% zeros, which keeps bundled
        // vectors from saturating.
        t.* = if (roll < 4) 0 else if (roll < 7) 1 else -1;
    }
    return v;
}

/// Rotate a hypervector by `n` positions — the VSA binding operation used
/// here to make position matter.
fn rotate(v: protocol.Trits, n: usize) protocol.Trits {
    var out: protocol.Trits = @splat(0);
    for (v, 0..) |t, i| out[(i + n) % protocol.n_trits] = t;
    return out;
}

/// Bundle token vectors into one hypervector by majority, position-bound.
pub fn encodeTask(text: []const u8) protocol.Trits {
    var acc: [protocol.n_trits]i32 = @splat(0);
    var it = std.mem.tokenizeAny(u8, text, " \t\n\r,.;:()[]{}\"'/\\-_");
    var pos: usize = 0;
    var seen = false;
    while (it.next()) |tok| : (pos += 1) {
        seen = true;
        var lower_buf: [64]u8 = undefined;
        const n = @min(tok.len, lower_buf.len);
        for (tok[0..n], 0..) |ch, i| lower_buf[i] = std.ascii.toLower(ch);
        const v = rotate(symbolVector(lower_buf[0..n], 0x1614_C0DE), pos % protocol.n_trits);
        for (v, 0..) |t, i| acc[i] += t;
    }
    if (!seen) return @splat(0);

    var out: protocol.Trits = @splat(0);
    for (acc, 0..) |a, i| out[i] = if (a > 0) 1 else if (a < 0) @as(i8, -1) else 0;
    return out;
}

/// Similarity between two ternary hypervectors, in [-1, 1].
pub fn similarity(a: protocol.Trits, b: protocol.Trits) f64 {
    var agree: i32 = 0;
    for (a, b) |x, y| agree += @as(i32, x) * @as(i32, y);
    return @as(f64, @floatFromInt(agree)) / @as(f64, @floatFromInt(protocol.n_trits));
}

pub const Decision = struct {
    action: Action,
    /// Similarity to the winning action prototype. Near zero means the model
    /// had no opinion, which is worth reporting rather than dressing up.
    confidence: f64,
    runner_up: Action,
    runner_up_confidence: f64,

    pub fn isConfident(self: Decision) bool {
        return self.confidence - self.runner_up_confidence > 0.15;
    }
};

/// Everything needed to check that an agent run really happened on the network.
pub const ProofBundle = struct {
    jobs: usize,
    rows_rejected: usize,
    on_silicon: u64,
    in_software: u64,
    credit_issued_mtri: u64,
    slashed_mtri: u64,
    nodes_used: usize,
    physical_nodes: usize,
    provenance: model_mod.Provenance,

    pub fn siliconShare(self: ProofBundle) f64 {
        const total = self.on_silicon + self.in_software;
        if (total == 0) return 0;
        return @as(f64, @floatFromInt(self.on_silicon)) / @as(f64, @floatFromInt(total));
    }
};

pub const Outcome = struct {
    decision: Decision,
    proof: ProofBundle,
    /// True when the mesh's answer equals a local recomputation of the same
    /// forward pass. False here means the network returned a wrong answer,
    /// which is a failure, not a nuance.
    matches_local: bool,
};

pub const Agent = struct {
    name: []const u8,
    model: model_mod.Model,
    scratch: []i8,
    prototypes: [action_count]protocol.Trits,

    pub fn init(gpa: std.mem.Allocator, name: []const u8, model: model_mod.Model) !Agent {
        var max_rows: usize = protocol.n_trits;
        for (model.layers) |l| max_rows = @max(max_rows, l.rows.len);
        const scratch = try gpa.alloc(i8, max_rows);

        var prototypes: [action_count]protocol.Trits = undefined;
        inline for (@typeInfo(Action).@"enum".fields, 0..) |f, i| {
            prototypes[i] = symbolVector("action:" ++ f.name, 0xAC7104);
        }
        return .{ .name = name, .model = model, .scratch = scratch, .prototypes = prototypes };
    }

    pub fn deinit(self: *Agent, gpa: std.mem.Allocator) void {
        gpa.free(self.scratch);
        self.model.deinit();
    }

    fn decide(self: Agent, output: protocol.Trits) Decision {
        var best: usize = 0;
        var best_s: f64 = -2;
        var second: usize = 0;
        var second_s: f64 = -2;
        for (self.prototypes, 0..) |p, i| {
            const s = similarity(output, p);
            if (s > best_s) {
                second = best;
                second_s = best_s;
                best = i;
                best_s = s;
            } else if (s > second_s) {
                second = i;
                second_s = s;
            }
        }
        return .{
            .action = @enumFromInt(best),
            .confidence = best_s,
            .runner_up = @enumFromInt(second),
            .runner_up_confidence = second_s,
        };
    }

    /// Run one task end to end on the mesh.
    pub fn run(self: *Agent, m: *mesh_mod.Mesh, task: []const u8) Error!Outcome {
        const input = encodeTask(task);

        const credit_before = m.ledger.total_credited_mtri;
        const slashed_before = m.ledger.total_slashed_mtri;

        var stats: model_mod.ForwardStats = .{};
        const output = try model_mod.forward(m, self.model, input, &stats, self.scratch);
        const local = model_mod.forwardLocal(self.model, input, self.scratch);

        return .{
            .decision = self.decide(output),
            .matches_local = std.mem.eql(i8, &output, &local),
            .proof = .{
                .jobs = stats.jobs,
                .rows_rejected = stats.rows_rejected,
                .on_silicon = stats.on_silicon,
                .in_software = stats.in_software,
                .credit_issued_mtri = m.ledger.total_credited_mtri - credit_before,
                .slashed_mtri = m.ledger.total_slashed_mtri - slashed_before,
                .nodes_used = m.nodeCount(),
                .physical_nodes = m.physicalCount(),
                .provenance = self.model.provenance,
            },
        };
    }
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const testing = std.testing;

test "task encoding is deterministic and order sensitive" {
    const a = encodeTask("fix the failing build");
    const b = encodeTask("fix the failing build");
    try testing.expectEqual(a, b);

    const c = encodeTask("build failing the fix");
    try testing.expect(!std.mem.eql(i8, &a, &c));

    // Empty input encodes to the zero vector rather than to noise.
    try testing.expectEqual(@as(protocol.Trits, @splat(0)), encodeTask("   "));
}

test "similar tasks encode more similarly than unrelated ones" {
    const base = encodeTask("run synthesis for the ternary core");
    const near = encodeTask("run synthesis for the ternary node");
    const far = encodeTask("write documentation about the token ledger");
    try testing.expect(similarity(base, near) > similarity(base, far));
}

test "self-similarity equals density, which is what ternary zeros mean" {
    const v = encodeTask("flash the bitstream to the board");
    var nonzero: usize = 0;
    for (v) |t| {
        if (t != 0) nonzero += 1;
    }
    const density = @as(f64, @floatFromInt(nonzero)) / @as(f64, @floatFromInt(protocol.n_trits));

    // A zero trit contributes nothing to agreement, so a sparse vector is not
    // fully similar even to itself. That is the point of the third state: it
    // encodes "no opinion on this dimension" rather than a forced sign.
    try testing.expectApproxEqAbs(density, similarity(v, v), 1e-9);
    try testing.expect(density < 1.0);

    var neg: protocol.Trits = undefined;
    for (v, 0..) |t, i| neg[i] = -t;
    try testing.expectApproxEqAbs(-density, similarity(v, neg), 1e-9);

    // A fully dense vector does reach 1.
    const dense: protocol.Trits = @splat(1);
    try testing.expectApproxEqAbs(@as(f64, 1.0), similarity(dense, dense), 1e-9);
}

test "an agent run over the mesh matches local inference and reports its provenance" {
    var m = try mesh_mod.Mesh.init(testing.allocator, .{});
    defer m.deinit();
    try m.join(mesh_mod.Node.initEmulated(1, "a", .honest), "alice", 9000);
    try m.join(mesh_mod.Node.initEmulated(2, "b", .honest), "bob", 9000);

    const model = try model_mod.Model.synthetic(testing.allocator, 3, 32, 0x1614);
    var agent = try Agent.init(testing.allocator, "igla-coder", model);
    defer agent.deinit(testing.allocator);

    const out = try agent.run(&m, "the gf16 adder test is failing after the last commit");
    try testing.expect(out.matches_local);
    try testing.expectEqual(@as(usize, 96), out.proof.jobs);
    try testing.expectEqual(@as(usize, 0), out.proof.rows_rejected);
    try testing.expectEqual(@as(u64, 96), out.proof.credit_issued_mtri);
    // No board attached in this test, so the honest silicon share is zero.
    try testing.expectEqual(@as(f64, 0.0), out.proof.siliconShare());
    try testing.expectEqual(model_mod.Provenance.synthetic, out.proof.provenance);
}

test "an agent still returns the correct inference when a node lies" {
    var m = try mesh_mod.Mesh.init(testing.allocator, .{});
    defer m.deinit();
    try m.join(mesh_mod.Node.initEmulated(1, "honest", .honest), "alice", 20000);
    try m.join(mesh_mod.Node.initEmulated(2, "liar", .lazy), "mallory", 20000);

    const model = try model_mod.Model.synthetic(testing.allocator, 2, 32, 7);
    var agent = try Agent.init(testing.allocator, "igla-coder", model);
    defer agent.deinit(testing.allocator);

    const out = try agent.run(&m, "synthesise the ternary mac and flash it");
    try testing.expect(out.matches_local);
    try testing.expect(out.proof.slashed_mtri > 0);
    try testing.expectEqual(@as(u64, 0), m.ledger.get(2).?.credit_mtri);
}

test "a decision reports low confidence rather than pretending to certainty" {
    var m = try mesh_mod.Mesh.init(testing.allocator, .{});
    defer m.deinit();
    try m.join(mesh_mod.Node.initEmulated(1, "a", .honest), "alice", 9000);

    const model = try model_mod.Model.synthetic(testing.allocator, 2, 32, 99);
    var agent = try Agent.init(testing.allocator, "igla-coder", model);
    defer agent.deinit(testing.allocator);

    const out = try agent.run(&m, "anything at all");
    // With synthetic weights the margin between actions carries no meaning.
    // The value is reported so a caller can see that for itself.
    try testing.expect(out.decision.confidence >= -1.0 and out.decision.confidence <= 1.0);
    try testing.expect(out.decision.action != out.decision.runner_up);
}
