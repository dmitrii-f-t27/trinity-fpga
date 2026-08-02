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
    /// Highest nonce ever dispatched to this node. A response carrying a nonce
    /// at or below it is one we really did ask for, so the stream is out of
    /// step; a nonce above it was never issued and is fabrication.
    highest_nonce_issued: u32 = 0,
    /// How many jobs this node is currently trusted with per round trip.
    ///
    /// A fleet is only as fast as its worst link if every node is handed the
    /// same batch. Measured: one board sustains 32 per trip at 3785 jobs/s
    /// while another loses most of a batch and manages 50. Batching is an
    /// optimisation for a healthy link and a liability on a lossy one, so it
    /// is earned rather than assumed — halved on a short batch, grown back on
    /// a clean one.
    batch_limit: usize = 32,
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

        // Resynchronise the CELL, not just the host buffer.
        //
        // The frame parser lives in the FPGA and holds state across host
        // processes: a batch cut short by a lost response leaves it partway
        // through a request, so the next run's first bytes finish somebody
        // else's frame and every job after that is shifted. Flushing the host
        // buffer does nothing about it — measured as runs that started clean at
        // 3002 jobs/s and degraded to 52 over three invocations.
        //
        // A full request's worth of padding completes whatever fragment is in
        // flight and returns the parser to its magic-hunt state. The worst it
        // costs is one spurious all-zero job, whose answer is then discarded.
        const resync: [protocol.request_len]u8 = @splat(0x00);
        port.writeAll(&resync) catch {};
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
        // Deliberately NOT flushing here. Draining before each request was
        // tried against a marginal board and measured worse on every count —
        // more unreachable, more misclassified — because it can discard a
        // response that is still arriving. The desync is real; the fix belongs
        // in how a stale nonce is judged, not in throwing bytes away.
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

    /// Send several jobs before reading any answer.
    ///
    /// One job per round trip costs a USB frame interval — measured at ~1.17 ms
    /// on this board, which caps a serial node near 850 jobs/s no matter how
    /// fast the line is. Writing a run of requests and then reading the run of
    /// responses amortises that latency, and a model layer is naturally a run:
    /// one job per output neuron.
    ///
    /// Safe against the cell overrunning its own transmitter because a request
    /// is 24 bytes and a response 19, so answer N is on the wire before request
    /// N+1 has finished arriving. A wider response than the request would need
    /// flow control instead.
    pub fn executeBatch(
        self: *Node,
        jobs: []const protocol.Job,
        out: []protocol.Receipt,
    ) Error!usize {
        std.debug.assert(out.len >= jobs.len);
        switch (self.backend) {
            .fpga => |*port| {
                self.stats.dispatched += jobs.len;
                for (jobs) |j| {
                    port.writeAll(&protocol.encodeRequest(j)) catch {
                        self.stats.unreachable_count += 1;
                        return Error.Unreachable;
                    };
                }
                const width: usize = if (self.key != null) protocol.response_len_v2 else protocol.response_len;
                const asked = jobs.len;
                var got: usize = 0;
                var buf: [protocol.response_len_v2]u8 = undefined;
                while (got < jobs.len) : (got += 1) {
                    // Stop at the first gap rather than erroring out. A batch
                    // that lost a response has lost every later one too, and
                    // the caller retries the remainder one at a time — waiting
                    // for answers that are not coming just adds a timeout per
                    // missing job.
                    port.readExact(buf[0..width]) catch break;
                    out[got] = (if (self.key != null)
                        protocol.decodeResponseV2(buf[0..width])
                    else
                        protocol.decodeResponse(buf[0..width])) orelse break;
                }

                // Additive increase, multiplicative decrease — the same shape
                // congestion control uses, and for the same reason: back off
                // fast from a link that is dropping, probe back up slowly when
                // it is not.
                if (got < asked) {
                    self.batch_limit = @max(1, self.batch_limit / 2);
                } else if (self.batch_limit < 32) {
                    self.batch_limit += 1;
                }
                return got;
            },
            // Batching buys nothing without a round trip to amortise, so the
            // other backends fall back rather than growing a second code path
            // that could drift from the first.
            else => {
                for (jobs, 0..) |j, i| out[i] = try self.execute(j);
                return jobs.len;
            },
        }
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
