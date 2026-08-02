//! A TRI-NET node — something that accepts a ternary compute job and returns a
//! receipt. Three backends, one interface:
//!
//!   .fpga      a physical board over serial. The arithmetic happens in LUTs.
//!   .remote    another operator's node over TCP. Same 24/15-byte framing.
//!   .emulated  software. Used to fill out a mesh before the boards exist, and
//!              to run adversaries against the verifier.
//!
//! The emulated backend can be told to misbehave. That is deliberate: a
//! settlement layer that has never been shown rejecting a cheat is not known
//! to work, and the cheapest way to demonstrate the rejection is to build the
//! cheat and point it at the verifier.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const protocol = @import("protocol.zig");
const serial = @import("serial.zig");
const net = @import("net.zig");

pub const Error = error{
    Unreachable,
    MalformedResponse,
    Timeout,
};

/// How an emulated node behaves. Everything except `.honest` is an attack that
/// the verifier is expected to catch.
pub const Behaviour = enum {
    /// Computes the dot product and tags it correctly.
    honest,
    /// Returns a plausible but wrong answer without doing the work. This is
    /// the free-rider: the failure mode that destroys a compute network's
    /// value if it goes undetected.
    lazy,
    /// Answers with a previous job's nonce — a replayed receipt.
    replay,
    /// Computes honestly but claims a different node's identity, trying to
    /// have the credit land in someone else's account.
    impersonator,
    /// Drops the job entirely, as an offline or overloaded node would.
    dead,
};

pub const Stats = struct {
    dispatched: u64 = 0,
    accepted: u64 = 0,
    rejected: u64 = 0,
    unreachable_count: u64 = 0,

    pub fn successRate(self: Stats) f64 {
        if (self.dispatched == 0) return 0;
        return @as(f64, @floatFromInt(self.accepted)) / @as(f64, @floatFromInt(self.dispatched));
    }
};

pub const Backend = union(enum) {
    fpga: serial.Port,
    remote: RemoteEndpoint,
    emulated: Emulated,
};

pub const RemoteEndpoint = struct {
    ip: []const u8,
    port: u16,
};

pub const Emulated = struct {
    behaviour: Behaviour = .honest,
    /// Identity actually claimed on the wire; for `.impersonator` this differs
    /// from the node's registered id.
    claimed_id: ?u32 = null,
    last_nonce: [4]u8 = .{ 0, 0, 0, 0 },
    prng: std.Random.DefaultPrng = .init(0xA11CE),
};

pub const Node = struct {
    /// Registered identity. The mesh credits work to this id, and a receipt
    /// that claims a different id is not credited here.
    id: u32,
    name: []const u8,
    backend: Backend,
    stats: Stats = .{},
    /// Set when this node runs the v2 cell, whose receipts carry a keyed tag
    /// and a 19-byte response instead of a CRC and 15. The key is what the
    /// coordinator needs to verify them; the node holds its own copy in its
    /// bitstream.
    key: ?[16]u8 = null,

    pub fn withKey(self: Node, k: [16]u8) Node {
        var n = self;
        n.key = k;
        return n;
    }

    pub fn initEmulated(id: u32, name: []const u8, behaviour: Behaviour) Node {
        return .{
            .id = id,
            .name = name,
            .backend = .{ .emulated = .{ .behaviour = behaviour } },
        };
    }

    pub fn initFpga(id: u32, name: []const u8, path: [:0]const u8, baud: u32) !Node {
        var port = try serial.Port.open(path, baud);
        port.flushInput();
        return .{ .id = id, .name = name, .backend = .{ .fpga = port } };
    }

    pub fn initRemote(id: u32, name: []const u8, ip: []const u8, port: u16) Node {
        return .{
            .id = id,
            .name = name,
            .backend = .{ .remote = .{ .ip = ip, .port = port } },
        };
    }

    pub fn deinit(self: *Node) void {
        switch (self.backend) {
            .fpga => |*p| p.close(),
            else => {},
        }
    }

    pub fn isPhysical(self: Node) bool {
        return self.backend == .fpga;
    }

    pub fn kindName(self: Node) []const u8 {
        return switch (self.backend) {
            .fpga => "fpga",
            .remote => "remote",
            .emulated => "emulated",
        };
    }

    /// Send one job and return whatever the node claims. No verification
    /// happens here on purpose — a node is untrusted, and mixing execution
    /// with judgement is how untrusted results get accidentally believed.
    pub fn execute(self: *Node, job: protocol.Job) Error!protocol.Receipt {
        self.stats.dispatched += 1;
        return switch (self.backend) {
            .fpga => |*port| self.executeSerial(port, job),
            .remote => |ep| self.executeRemote(ep, job),
            .emulated => |*emu| self.executeEmulated(emu, job),
        };
    }

    fn executeSerial(self: *Node, port: *serial.Port, job: protocol.Job) Error!protocol.Receipt {
        const req = protocol.encodeRequest(job);
        port.writeAll(&req) catch {
            self.stats.unreachable_count += 1;
            return Error.Unreachable;
        };
        // The response width is set by which cell is flashed, so it follows the
        // key: a keyed node answers 19 bytes, an unkeyed one 15. Reading the
        // wrong width would desynchronise the stream for every later job.
        if (self.key != null) {
            var raw: [protocol.response_len_v2]u8 = undefined;
            port.readExact(&raw) catch {
                self.stats.unreachable_count += 1;
                return Error.Timeout;
            };
            return protocol.decodeResponseV2(&raw) orelse Error.MalformedResponse;
        }
        var raw: [protocol.response_len]u8 = undefined;
        port.readExact(&raw) catch {
            self.stats.unreachable_count += 1;
            return Error.Timeout;
        };
        return protocol.decodeResponse(&raw) orelse Error.MalformedResponse;
    }

    fn executeRemote(self: *Node, ep: RemoteEndpoint, job: protocol.Job) Error!protocol.Receipt {
        var stream = net.connect(ep.ip, ep.port) catch {
            self.stats.unreachable_count += 1;
            return Error.Unreachable;
        };
        defer stream.close();
        const req = protocol.encodeRequest(job);
        stream.writeAll(&req) catch return Error.Unreachable;
        var raw: [protocol.response_len]u8 = undefined;
        stream.readExact(&raw) catch return Error.Timeout;
        return protocol.decodeResponse(&raw) orelse Error.MalformedResponse;
    }

    fn executeEmulated(self: *Node, emu: *Emulated, job: protocol.Job) Error!protocol.Receipt {
        const claimed = emu.claimed_id orelse self.id;
        switch (emu.behaviour) {
            .honest => {
                emu.last_nonce = job.nonce;
                if (self.key) |k| return protocol.executeKeyed(job, claimed, k);
                return protocol.execute(job, claimed);
            },
            .lazy => {
                // Guess without doing the work, then tag the guess correctly.
                // A verifier that only checked the tag would accept this.
                const guess: i8 = emu.prng.random().intRangeAtMost(i8, -32, 32);
                return .{
                    .y = guess,
                    .status = protocol.status_ok,
                    .nonce = job.nonce,
                    .node_id = claimed,
                    .tag = protocol.receiptTag(job, guess, claimed),
                    .kind = .crc32,
                };
            },
            .replay => {
                var stale = protocol.execute(job, claimed);
                stale.nonce = emu.last_nonce;
                emu.last_nonce = job.nonce;
                return stale;
            },
            .impersonator => {
                const victim = claimed +% 1;
                return protocol.execute(job, victim);
            },
            .dead => {
                self.stats.unreachable_count += 1;
                return Error.Unreachable;
            },
        }
    }
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

fn sampleJob(n: u32) protocol.Job {
    var wv: protocol.Trits = @splat(0);
    var xv: protocol.Trits = @splat(0);
    for (&wv, 0..) |*t, i| t.* = if ((i + n) % 3 == 0) 1 else if ((i + n) % 3 == 1) -1 else 0;
    for (&xv, 0..) |*t, i| t.* = if ((i + n) % 2 == 0) 1 else -1;
    return protocol.Job.withNonce(n, protocol.pack(wv), protocol.pack(xv));
}

test "an honest emulated node always passes verification" {
    var node = Node.initEmulated(1, "honest", .honest);
    for (0..200) |i| {
        const job = sampleJob(@intCast(i));
        const r = try node.execute(job);
        try std.testing.expectEqual(protocol.Verdict.ok, protocol.verify(job, r));
    }
}

test "the free rider is caught even though its tag is well formed" {
    var node = Node.initEmulated(2, "lazy", .lazy);
    var caught: usize = 0;
    var slipped: usize = 0;
    for (0..500) |i| {
        const job = sampleJob(@intCast(i));
        const r = try node.execute(job);
        // The tag itself is correct for the value returned — a tag-only check
        // would accept every one of these.
        try std.testing.expectEqual(@as(u64, protocol.receiptTag(job, r.y, r.node_id)), r.tag);
        switch (protocol.verify(job, r)) {
            .ok => slipped += 1, // only when the guess happens to be right
            .wrong_result => caught += 1,
            else => unreachable,
        }
    }
    try std.testing.expect(caught > 450);
    // A lucky guess is possible: the answer space is only 65 wide. That is a
    // property of this work unit, and it is why the ledger scores a node over
    // many jobs rather than trusting any single one.
    try std.testing.expect(slipped < 50);
}

test "replayed and impersonated receipts are rejected" {
    var replayer = Node.initEmulated(3, "replay", .replay);
    _ = try replayer.execute(sampleJob(0)); // prime the stale nonce
    const job = sampleJob(1);
    const r = try replayer.execute(job);
    try std.testing.expectEqual(protocol.Verdict.nonce_mismatch, protocol.verify(job, r));

    var faker = Node.initEmulated(4, "impersonator", .impersonator);
    const job2 = sampleJob(2);
    const r2 = try faker.execute(job2);
    try std.testing.expect(r2.node_id != faker.id);
    // The tag is valid for the identity it claims, so the protocol verifier
    // passes it; catching the theft is the ledger's job, not the tag's.
    try std.testing.expectEqual(protocol.Verdict.ok, protocol.verify(job2, r2));
}

test "a dead node surfaces as unreachable rather than hanging" {
    var node = Node.initEmulated(5, "dead", .dead);
    try std.testing.expectError(Error.Unreachable, node.execute(sampleJob(0)));
    try std.testing.expectEqual(@as(u64, 1), node.stats.unreachable_count);
}
