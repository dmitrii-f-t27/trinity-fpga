//! The TRI-NET coordinator — hands ternary jobs to nodes, judges what comes
//! back, and settles it.
//!
//! Three things are kept deliberately separate, because collapsing them is how
//! compute networks end up paying for work that never happened:
//!
//!   node.execute   produces an untrusted claim
//!   protocol.verify judges the claim against an independent recomputation
//!   ledger.settle  moves credit, and only ever on a judged claim
//!
//! The coordinator also carries the network's honesty counters: how many jobs
//! ran on real silicon versus software. A network that says it is hardware
//! compute should be able to answer that question from its own books.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const protocol = @import("protocol.zig");
const node_mod = @import("node.zig");
const ledger_mod = @import("ledger.zig");

pub const Node = node_mod.Node;
pub const Ledger = ledger_mod.Ledger;

pub const Error = error{
    NoEligibleNode,
    OutOfMemory,
    UnknownNode,
    DuplicateNode,
    InsufficientStake,
    UnsoundPolicy,
};

pub const JobOutcome = struct {
    node_id: u32,
    node_name: []const u8,
    physical: bool,
    y: i8,
    verdict: protocol.Verdict,
    settlement: ledger_mod.Settlement,
    /// Set when the node could not be reached at all.
    unreachable_node: bool = false,
};

pub const QuorumOutcome = struct {
    /// Value agreed by a strict majority of responding nodes, if any.
    agreed: ?i8,
    responses: u32,
    agreeing: u32,
    /// True when the majority answer is also the mathematically correct one.
    /// Recorded rather than assumed: a quorum protects against a minority of
    /// liars, not against a majority of them.
    majority_was_correct: bool,
};

pub const Stats = struct {
    dispatched: u64 = 0,
    accepted: u64 = 0,
    rejected: u64 = 0,
    unreachable_jobs: u64 = 0,
    /// Damaged frames. Separated from rejections because one is a statement
    /// about the operator's wiring and the other about their honesty.
    corrupt_jobs: u64 = 0,
    on_silicon: u64 = 0,
    in_software: u64 = 0,

    pub fn siliconShare(self: Stats) f64 {
        const total = self.on_silicon + self.in_software;
        if (total == 0) return 0;
        return @as(f64, @floatFromInt(self.on_silicon)) / @as(f64, @floatFromInt(total));
    }
};

pub const Mesh = struct {
    gpa: std.mem.Allocator,
    nodes: std.ArrayList(Node) = .empty,
    ledger: Ledger,
    stats: Stats = .{},
    cursor: usize = 0,
    next_nonce: u32 = 1,

    pub fn init(gpa: std.mem.Allocator, policy: ledger_mod.Policy) Error!Mesh {
        return .{ .gpa = gpa, .ledger = try Ledger.init(gpa, policy) };
    }

    pub fn deinit(self: *Mesh) void {
        for (self.nodes.items) |*n| n.deinit();
        self.nodes.deinit(self.gpa);
        self.ledger.deinit();
    }

    /// Attach a node and bond its owner's stake. This is the join step a new
    /// developer performs; everything after it is automatic.
    pub fn join(self: *Mesh, n: Node, owner: []const u8, stake_mtri: u64) Error!void {
        try self.ledger.register(n.id, owner, n.isPhysical(), stake_mtri);
        try self.nodes.append(self.gpa, n);
    }

    pub fn nodeCount(self: Mesh) usize {
        return self.nodes.items.len;
    }

    pub fn physicalCount(self: Mesh) usize {
        var k: usize = 0;
        for (self.nodes.items) |n| {
            if (n.isPhysical()) k += 1;
        }
        return k;
    }

    pub fn freshNonce(self: *Mesh) u32 {
        const n = self.next_nonce;
        self.next_nonce +%= 1;
        return n;
    }

    fn pickEligible(self: *Mesh) ?*Node {
        const count = self.nodes.items.len;
        if (count == 0) return null;
        var tried: usize = 0;
        while (tried < count) : (tried += 1) {
            const idx = (self.cursor + tried) % count;
            const candidate = &self.nodes.items[idx];
            if (self.ledger.isEligible(candidate.id)) {
                self.cursor = (idx + 1) % count;
                return candidate;
            }
        }
        return null;
    }

    /// Send one job to the next eligible node, judge the answer, settle it.
    pub fn dispatch(self: *Mesh, job: protocol.Job) Error!JobOutcome {
        const n = self.pickEligible() orelse return Error.NoEligibleNode;
        return self.dispatchTo(n, job);
    }

    fn dispatchTo(self: *Mesh, n: *Node, job: protocol.Job) Error!JobOutcome {
        self.stats.dispatched += 1;

        const receipt = n.execute(job) catch {
            self.stats.unreachable_jobs += 1;
            return .{
                .node_id = n.id,
                .node_name = n.name,
                .physical = n.isPhysical(),
                .y = 0,
                .verdict = .bad_status,
                .settlement = .{ .node_id = n.id, .outcome = .not_eligible, .detail = "node unreachable" },
                .unreachable_node = true,
            };
        };

        if (job.nonceValue() > n.highest_nonce_issued) n.highest_nonce_issued = job.nonceValue();

        var verdict = protocol.verifyWithKey(job, receipt, n.key);

        // A nonce mismatch means either a replay attack or a stream that lost a
        // response and is now one behind. They are indistinguishable from a
        // single exchange, and one of them costs an honest operator their
        // stake — so use what the coordinator knows and the node does not: a
        // nonce we already issued is desync, a nonce we never issued is
        // fabrication.
        if (verdict == .nonce_mismatch) {
            const returned = std.mem.readInt(u32, &receipt.nonce, .little);
            if (returned <= n.highest_nonce_issued) verdict = .corrupt;
        }
        const settlement = try self.ledger.settle(n.id, job, receipt, verdict);

        if (settlement.outcome == .credited) {
            self.stats.accepted += 1;
            n.stats.accepted += 1;
            if (n.isPhysical()) self.stats.on_silicon += 1 else self.stats.in_software += 1;
        } else if (settlement.outcome == .corrupt_not_charged) {
            self.stats.corrupt_jobs += 1;
        } else {
            self.stats.rejected += 1;
            n.stats.rejected += 1;
        }

        return .{
            .node_id = n.id,
            .node_name = n.name,
            .physical = n.isPhysical(),
            .y = receipt.y,
            .verdict = verdict,
            .settlement = settlement,
        };
    }

    /// Send the same job to up to `k` distinct nodes and take the majority.
    ///
    /// For this work unit a quorum is not how correctness is established —
    /// recomputing a 32-wide dot product is cheaper than asking a second node.
    /// It is here because it is the mechanism that has to exist for work units
    /// where recomputation is NOT cheap, and because it is the honest way to
    /// measure whether independent nodes actually agree.
    pub fn dispatchQuorum(self: *Mesh, job: protocol.Job, k: usize) Error!QuorumOutcome {
        var votes: [16]i8 = undefined;
        var vote_count: usize = 0;
        const limit = @min(k, @min(self.nodes.items.len, votes.len));

        var tried: usize = 0;
        while (tried < self.nodes.items.len and vote_count < limit) : (tried += 1) {
            const idx = (self.cursor + tried) % self.nodes.items.len;
            const candidate = &self.nodes.items[idx];
            if (!self.ledger.isEligible(candidate.id)) continue;
            const out = try self.dispatchTo(candidate, job);
            if (out.unreachable_node) continue;
            votes[vote_count] = out.y;
            vote_count += 1;
        }
        self.cursor = (self.cursor + tried) % @max(self.nodes.items.len, 1);

        if (vote_count == 0) {
            return .{ .agreed = null, .responses = 0, .agreeing = 0, .majority_was_correct = false };
        }

        var best: i8 = votes[0];
        var best_n: u32 = 0;
        for (votes[0..vote_count]) |candidate| {
            var c: u32 = 0;
            for (votes[0..vote_count]) |v| {
                if (v == candidate) c += 1;
            }
            if (c > best_n) {
                best_n = c;
                best = candidate;
            }
        }

        const majority = best_n * 2 > @as(u32, @intCast(vote_count));
        const truth = protocol.dot(job.w, job.x);
        return .{
            .agreed = if (majority) best else null,
            .responses = @intCast(vote_count),
            .agreeing = best_n,
            .majority_was_correct = majority and best == truth,
        };
    }

    /// One ternary matrix-vector product, distributed across the mesh: each
    /// row of the weight matrix becomes one job. This is the operation a
    /// ternary-weight model's forward pass is made of, so a layer evaluated
    /// this way has its arithmetic physically spread over the network.
    pub fn matvec(
        self: *Mesh,
        rows: []const protocol.Packed,
        x: protocol.Packed,
        out: []i8,
        failures: ?*usize,
    ) Error!void {
        std.debug.assert(out.len >= rows.len);
        var fails: usize = 0;
        for (rows, 0..) |w, i| {
            const job = protocol.Job.withNonce(self.freshNonce(), w, x);
            const outcome = try self.dispatch(job);
            if (outcome.settlement.outcome == .credited) {
                out[i] = outcome.y;
            } else {
                // A rejected row is not silently accepted. The coordinator
                // falls back to its own recomputation so the layer still has a
                // correct value, and the node still does not get paid.
                out[i] = protocol.dot(w, x);
                fails += 1;
            }
        }
        if (failures) |f| f.* = fails;
    }

    pub fn report(self: *Mesh, writer: anytype) !void {
        try writer.print("nodes: {d} total, {d} physical\n", .{ self.nodeCount(), self.physicalCount() });
        for (self.nodes.items) |n| {
            const a = self.ledger.get(n.id) orelse continue;
            try writer.print(
                "  {s:<14} id={x:0>8} {s:<9} owner={s:<8} accepted={d:<6} rejected={d:<4} credit={d} mTRI stake={d} status={s}\n",
                .{ n.name, n.id, n.kindName(), a.owner, a.accepted, a.rejected, a.credit_mtri, a.stake_mtri, @tagName(a.status) },
            );
        }
        try writer.print(
            "jobs: {d} dispatched, {d} accepted, {d} rejected as dishonest, {d} damaged in transit, {d} unreachable\n",
            .{ self.stats.dispatched, self.stats.accepted, self.stats.rejected, self.stats.corrupt_jobs, self.stats.unreachable_jobs },
        );
        try writer.print(
            "compute location: {d} on silicon, {d} in software ({d:.1}% hardware)\n",
            .{ self.stats.on_silicon, self.stats.in_software, self.stats.siliconShare() * 100 },
        );
        try writer.print(
            "credit issued: {d} mTRI, slashed: {d} mTRI\n",
            .{ self.ledger.total_credited_mtri, self.ledger.total_slashed_mtri },
        );
    }
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

fn testJob(n: u32) protocol.Job {
    var wv: protocol.Trits = @splat(0);
    var xv: protocol.Trits = @splat(0);
    for (&wv, 0..) |*t, i| t.* = if ((i + n) % 3 == 0) 1 else if ((i + n) % 3 == 1) -1 else 0;
    for (&xv, 0..) |*t, i| t.* = if ((i + n) % 2 == 0) 1 else -1;
    return protocol.Job.withNonce(n, protocol.pack(wv), protocol.pack(xv));
}

test "an all-honest mesh credits every job" {
    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();
    try m.join(Node.initEmulated(1, "a", .honest), "alice", 2000);
    try m.join(Node.initEmulated(2, "b", .honest), "bob", 2000);
    try m.join(Node.initEmulated(3, "c", .honest), "carol", 2000);

    for (0..90) |i| {
        const o = try m.dispatch(testJob(@intCast(i)));
        try std.testing.expectEqual(ledger_mod.Outcome.credited, o.settlement.outcome);
    }
    try std.testing.expectEqual(@as(u64, 90), m.stats.accepted);
    // Round robin should spread work evenly across three nodes.
    for ([_]u32{ 1, 2, 3 }) |id| {
        try std.testing.expectEqual(@as(u64, 30), m.ledger.get(id).?.accepted);
    }
}

test "a free rider in the mesh is suspended and stops receiving work" {
    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();
    try m.join(Node.initEmulated(1, "honest-a", .honest), "alice", 2000);
    try m.join(Node.initEmulated(2, "cheat", .lazy), "mallory", 2000);
    try m.join(Node.initEmulated(3, "honest-b", .honest), "carol", 2000);

    for (0..120) |i| _ = try m.dispatch(testJob(@intCast(i)));

    const cheat = m.ledger.get(2).?;
    try std.testing.expectEqual(ledger_mod.Status.suspended, cheat.status);
    try std.testing.expect(cheat.slashed_mtri > 0);
    try std.testing.expect(!m.ledger.isEligible(2));

    // The honest nodes absorbed the work the cheat stopped receiving.
    try std.testing.expect(m.ledger.get(1).?.accepted > 30);
    try std.testing.expect(m.ledger.get(3).?.accepted > 30);
}

test "the mesh reports how much work actually ran on silicon" {
    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();
    // No physical node attached: the honest answer is zero percent hardware.
    try m.join(Node.initEmulated(1, "sim-a", .honest), "alice", 2000);
    try m.join(Node.initEmulated(2, "sim-b", .honest), "bob", 2000);
    for (0..20) |i| _ = try m.dispatch(testJob(@intCast(i)));
    try std.testing.expectEqual(@as(f64, 0.0), m.stats.siliconShare());
    try std.testing.expectEqual(@as(u64, 0), m.ledger.jobs_on_silicon);
}

test "a quorum outvotes a minority of liars but is not asked to beat a majority" {
    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();
    try m.join(Node.initEmulated(1, "h1", .honest), "alice", 2000);
    try m.join(Node.initEmulated(2, "h2", .honest), "bob", 2000);
    try m.join(Node.initEmulated(3, "liar", .lazy), "mallory", 2000);

    const job = testJob(11);
    const q = try m.dispatchQuorum(job, 3);
    try std.testing.expectEqual(@as(u32, 3), q.responses);
    try std.testing.expectEqual(protocol.dot(job.w, job.x), q.agreed.?);
    try std.testing.expect(q.majority_was_correct);
}

test "a matrix-vector product distributed over the mesh matches local arithmetic" {
    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();
    try m.join(Node.initEmulated(1, "a", .honest), "alice", 2000);
    try m.join(Node.initEmulated(2, "b", .honest), "bob", 2000);

    var rows: [16]protocol.Packed = undefined;
    var prng: std.Random.DefaultPrng = .init(0xBEEF);
    const rand = prng.random();
    for (&rows) |*r| {
        var tv: protocol.Trits = @splat(0);
        for (&tv) |*t| t.* = rand.intRangeAtMost(i8, -1, 1);
        r.* = protocol.pack(tv);
    }
    var xv: protocol.Trits = @splat(0);
    for (&xv) |*t| t.* = rand.intRangeAtMost(i8, -1, 1);
    const x = protocol.pack(xv);

    var out: [16]i8 = undefined;
    var fails: usize = 0;
    try m.matvec(&rows, x, &out, &fails);
    try std.testing.expectEqual(@as(usize, 0), fails);
    for (rows, out) |r, y| try std.testing.expectEqual(protocol.dot(r, x), y);
}

test "a layer still computes correctly when a node in the mesh is lying" {
    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();
    try m.join(Node.initEmulated(1, "honest", .honest), "alice", 5000);
    try m.join(Node.initEmulated(2, "liar", .lazy), "mallory", 5000);

    var rows: [32]protocol.Packed = undefined;
    var prng: std.Random.DefaultPrng = .init(0xC0DE);
    const rand = prng.random();
    for (&rows) |*r| {
        var tv: protocol.Trits = @splat(0);
        for (&tv) |*t| t.* = rand.intRangeAtMost(i8, -1, 1);
        r.* = protocol.pack(tv);
    }
    var xv: protocol.Trits = @splat(0);
    for (&xv) |*t| t.* = rand.intRangeAtMost(i8, -1, 1);
    const x = protocol.pack(xv);

    var out: [32]i8 = undefined;
    var fails: usize = 0;
    try m.matvec(&rows, x, &out, &fails);

    // Every output is right even though a node lied, and the liar was caught.
    for (rows, out) |r, y| try std.testing.expectEqual(protocol.dot(r, x), y);
    try std.testing.expect(fails > 0);
    try std.testing.expect(m.ledger.get(2).?.slashed_mtri > 0);
    try std.testing.expectEqual(@as(u64, 0), m.ledger.get(2).?.credit_mtri);
}

test "a node on the other end of a socket earns credit like any other" {
    const net = @import("net.zig");

    // This is the path a developer on another machine takes, so it is worth
    // exercising for real rather than asserting the types line up. Binding
    // before the server thread starts removes the accept/connect race without
    // a sleep.
    var listener = try net.listen("127.0.0.1", 39702);

    const Server = struct {
        fn run(l: *net.Listener) void {
            var backing = Node.initEmulated(0xBEEF0001, "peer", .honest);
            while (true) {
                var conn = l.accept() catch return;
                defer conn.close();
                while (true) {
                    var raw: [protocol.request_len]u8 = undefined;
                    conn.readExact(&raw) catch break;
                    const job: protocol.Job = .{
                        .op = raw[2],
                        .nonce = raw[3..7].*,
                        .w = raw[7..15].*,
                        .x = raw[15..23].*,
                    };
                    const r = backing.execute(job) catch break;
                    conn.writeAll(&protocol.encodeResponse(r)) catch break;
                }
            }
        }
    };
    const th = try std.Thread.spawn(.{}, Server.run, .{&listener});

    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();
    try m.join(Node.initRemote(0xBEEF0001, "over-tcp", "127.0.0.1", 39702), "remote-dev", 5000);

    for (0..25) |i| {
        const o = try m.dispatch(testJob(@intCast(i)));
        try std.testing.expectEqual(ledger_mod.Outcome.credited, o.settlement.outcome);
    }
    try std.testing.expectEqual(@as(u64, 25), m.ledger.get(0xBEEF0001).?.credit_mtri);

    listener.close();
    th.detach();
}

test "keyed nodes are verified with their own key, not each other's" {
    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();

    const key_a: [16]u8 = @splat(0xA1);
    const key_b: [16]u8 = @splat(0xB2);

    // A fleet gives each node its own key so a leak is confined to one board.
    // The coordinator therefore has to verify each node against its own key,
    // and getting that wrong is silent: node B's honest receipt would look
    // forged under node A's key.
    try m.join(Node.initEmulated(0xA000, "keyed-a", .honest).withKey(key_a), "alice", 5000);
    try m.join(Node.initEmulated(0xB000, "keyed-b", .honest).withKey(key_b), "bob", 5000);
    try m.join(Node.initEmulated(0xC000, "unkeyed", .honest), "carol", 5000);

    for (0..60) |i| {
        const o = try m.dispatch(testJob(@intCast(i)));
        try std.testing.expectEqual(ledger_mod.Outcome.credited, o.settlement.outcome);
    }
    for ([_]u32{ 0xA000, 0xB000, 0xC000 }) |id| {
        try std.testing.expectEqual(@as(u64, 20), m.ledger.get(id).?.accepted);
    }

    // Cross-checking is what would go unnoticed: an honest keyed receipt fails
    // under the wrong key, exactly as a forgery would.
    const job = testJob(99);
    const honest = protocol.executeKeyed(job, 0xA000, key_a);
    try std.testing.expectEqual(protocol.Verdict.ok, protocol.verifyWithKey(job, honest, key_a));
    try std.testing.expectEqual(protocol.Verdict.corrupt, protocol.verifyWithKey(job, honest, key_b));
    // And a keyed receipt with no key at all must never be waved through.
    try std.testing.expectEqual(protocol.Verdict.corrupt, protocol.verifyWithKey(job, honest, null));
}

test "a mesh with no eligible node fails loudly instead of silently faking work" {
    var m = try Mesh.init(std.testing.allocator, .{});
    defer m.deinit();
    try std.testing.expectError(Error.NoEligibleNode, m.dispatch(testJob(0)));
}
