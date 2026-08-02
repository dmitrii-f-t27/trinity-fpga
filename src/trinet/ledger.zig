//! TRI settlement — turning verified ternary compute into credit, and making
//! cheating cost more than it pays.
//!
//! WHAT TRI IS HERE. A TRI unit in this ledger is an internal work credit: a
//! record that a node performed a verified unit of ternary compute. It is not
//! minted on a chain, it is not transferable between owners, and nothing in
//! this module issues a financial instrument. That is a deliberate scoping
//! choice, not an oversight — a network can bootstrap, measure contribution
//! and pay contributors out of a budget without ever issuing a token, and the
//! moment a transferable token exists the design question stops being
//! technical. Keeping the credit non-transferable is what lets the accounting
//! be built and tested now.
//!
//! THE ECONOMIC CONDITION. A compute market only works if the expected value
//! of cheating is negative. With an audit rate p, a reward r per accepted job
//! and a slash s per detected bad receipt, a free rider that skips the work
//! earns r per job and loses s with probability p, so honesty requires
//!
//!     p * s > r
//!
//! `Policy.isSound` checks exactly this, and `Ledger.init` refuses a policy
//! that fails it. Parameters that make cheating profitable are a bug, and this
//! is the one place they can be caught before a network runs on them.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const protocol = @import("protocol.zig");

/// Credits are tracked in milli-TRI so that per-job rewards stay integral.
pub const milli: u64 = 1000;

pub const Policy = struct {
    /// Credit granted for one accepted 32-wide ternary dot product.
    reward_per_job_mtri: u64 = 1,
    /// Taken from stake when a receipt is rejected.
    slash_per_bad_receipt_mtri: u64 = 200,
    /// Bond a node must post before it receives work.
    min_stake_mtri: u64 = 1000,
    /// Fraction of jobs whose result is independently recomputed, in percent.
    /// 100 means every job is checked, which is affordable for this work unit
    /// and is the honest default until the unit grows.
    audit_rate_percent: u8 = 100,
    /// Consecutive rejections before a node is suspended from dispatch.
    rejection_tolerance: u32 = 3,

    /// p * s > r, with p expressed in percent.
    pub fn isSound(self: Policy) bool {
        const expected_loss = @as(u64, self.audit_rate_percent) * self.slash_per_bad_receipt_mtri;
        const expected_gain = 100 * self.reward_per_job_mtri;
        return expected_loss > expected_gain;
    }

    /// How many jobs of honest work it takes to earn back one slash. A number
    /// far above the tolerance means a caught cheat is genuinely painful.
    pub fn slashInJobs(self: Policy) u64 {
        if (self.reward_per_job_mtri == 0) return std.math.maxInt(u64);
        return self.slash_per_bad_receipt_mtri / self.reward_per_job_mtri;
    }
};

pub const Status = enum {
    /// Bonded and receiving work.
    active,
    /// Recently rejected work; still dispatched but watched.
    probation,
    /// Stake exhausted or tolerance exceeded. Receives no further work.
    suspended,
};

pub const Account = struct {
    node_id: u32,
    /// The developer who attached the board. Payouts are owed to this handle.
    owner: []const u8,
    /// Whether this node's arithmetic happens in silicon or in software. The
    /// ledger records it because a network claiming hardware compute must be
    /// able to say how much of its work was actually hardware.
    physical: bool,
    stake_mtri: u64,
    credit_mtri: u64 = 0,
    slashed_mtri: u64 = 0,
    accepted: u64 = 0,
    rejected: u64 = 0,
    consecutive_rejections: u32 = 0,
    /// Damaged responses. Tracked separately from rejections because it is a
    /// link-quality signal about the operator's wiring, not about their honesty.
    corrupted: u64 = 0,
    status: Status = .active,

    pub fn reputation(self: Account) f64 {
        const total = self.accepted + self.rejected;
        if (total == 0) return 1.0;
        return @as(f64, @floatFromInt(self.accepted)) / @as(f64, @floatFromInt(total));
    }
};

pub const Outcome = enum {
    credited,
    /// Result or tag did not verify.
    rejected_and_slashed,
    /// The response was damaged in transit. Not credited, and NOT slashed:
    /// stake is the price of dishonesty, not of a marginal cable.
    corrupt_not_charged,
    /// The receipt claimed an identity other than the node we dispatched to.
    identity_mismatch,
    /// Node is suspended and should not have been dispatched to.
    not_eligible,
};

pub const Settlement = struct {
    node_id: u32,
    outcome: Outcome,
    credit_delta_mtri: u64 = 0,
    slash_delta_mtri: u64 = 0,
    detail: []const u8 = "",
};

pub const Error = error{
    UnsoundPolicy,
    UnknownNode,
    DuplicateNode,
    InsufficientStake,
    OutOfMemory,
};

pub const Ledger = struct {
    gpa: std.mem.Allocator,
    policy: Policy,
    accounts: std.AutoHashMapUnmanaged(u32, Account) = .empty,
    /// Nonces already settled, so a receipt cannot be paid for twice.
    spent_nonces: std.AutoHashMapUnmanaged(u64, void) = .empty,
    total_credited_mtri: u64 = 0,
    total_slashed_mtri: u64 = 0,
    total_corrupted: u64 = 0,
    jobs_on_silicon: u64 = 0,

    pub fn init(gpa: std.mem.Allocator, policy: Policy) Error!Ledger {
        if (!policy.isSound()) return Error.UnsoundPolicy;
        return .{ .gpa = gpa, .policy = policy };
    }

    pub fn deinit(self: *Ledger) void {
        self.accounts.deinit(self.gpa);
        self.spent_nonces.deinit(self.gpa);
    }

    /// A developer attaches a node and bonds a stake. This is the whole
    /// onboarding step: an identity, an owner, and something to lose.
    pub fn register(self: *Ledger, node_id: u32, owner: []const u8, physical: bool, stake_mtri: u64) Error!void {
        if (self.accounts.contains(node_id)) return Error.DuplicateNode;
        if (stake_mtri < self.policy.min_stake_mtri) return Error.InsufficientStake;
        try self.accounts.put(self.gpa, node_id, .{
            .node_id = node_id,
            .owner = owner,
            .physical = physical,
            .stake_mtri = stake_mtri,
        });
    }

    pub fn get(self: *Ledger, node_id: u32) ?*Account {
        return self.accounts.getPtr(node_id);
    }

    pub fn isEligible(self: *Ledger, node_id: u32) bool {
        const a = self.accounts.get(node_id) orelse return false;
        return a.status != .suspended;
    }

    /// Settle one dispatched job.
    ///
    /// `dispatched_to` is the node the coordinator actually sent the job to.
    /// `receipt.node_id` is the identity the response claims. When they differ
    /// the work is not credited to either party: the claim is unattributable,
    /// and paying it out is how one operator drains another's earnings.
    pub fn settle(
        self: *Ledger,
        dispatched_to: u32,
        job: protocol.Job,
        receipt: protocol.Receipt,
        verdict: protocol.Verdict,
    ) Error!Settlement {
        const acct = self.accounts.getPtr(dispatched_to) orelse return Error.UnknownNode;

        if (acct.status == .suspended) {
            return .{ .node_id = dispatched_to, .outcome = .not_eligible, .detail = "node is suspended" };
        }

        if (receipt.node_id != dispatched_to) {
            const slash = @min(acct.stake_mtri, self.policy.slash_per_bad_receipt_mtri);
            acct.stake_mtri -= slash;
            acct.slashed_mtri += slash;
            acct.rejected += 1;
            acct.consecutive_rejections += 1;
            self.total_slashed_mtri += slash;
            self.applyStatus(acct);
            return .{
                .node_id = dispatched_to,
                .outcome = .identity_mismatch,
                .slash_delta_mtri = slash,
                .detail = "receipt claims an identity we did not dispatch to",
            };
        }

        // A damaged frame is not evidence about the operator. Measured on real
        // hardware: at ~2.4 Mbaud one of three boards returned a few percent of
        // responses corrupted, and the ledger slashed it for a cable. Charging
        // stake for that drives honest operators off a network faster than any
        // fraud does.
        if (verdict == .corrupt) {
            acct.corrupted += 1;
            self.total_corrupted += 1;
            return .{
                .node_id = dispatched_to,
                .outcome = .corrupt_not_charged,
                .detail = verdict.reason(),
            };
        }

        if (!verdict.accepted()) {
            const slash = @min(acct.stake_mtri, self.policy.slash_per_bad_receipt_mtri);
            acct.stake_mtri -= slash;
            acct.slashed_mtri += slash;
            acct.rejected += 1;
            acct.consecutive_rejections += 1;
            self.total_slashed_mtri += slash;
            self.applyStatus(acct);
            return .{
                .node_id = dispatched_to,
                .outcome = .rejected_and_slashed,
                .slash_delta_mtri = slash,
                .detail = verdict.reason(),
            };
        }

        // Pay once per nonce, per node. Without this a node can resubmit the
        // same verified receipt forever.
        const key = (@as(u64, dispatched_to) << 32) | job.nonceValue();
        if (self.spent_nonces.contains(key)) {
            return .{
                .node_id = dispatched_to,
                .outcome = .rejected_and_slashed,
                .detail = "receipt for an already-settled nonce",
            };
        }
        try self.spent_nonces.put(self.gpa, key, {});

        const reward = self.policy.reward_per_job_mtri;
        acct.credit_mtri += reward;
        acct.accepted += 1;
        acct.consecutive_rejections = 0;
        if (acct.status == .probation) acct.status = .active;
        self.total_credited_mtri += reward;
        if (acct.physical) self.jobs_on_silicon += 1;

        return .{
            .node_id = dispatched_to,
            .outcome = .credited,
            .credit_delta_mtri = reward,
            .detail = "verified",
        };
    }

    fn applyStatus(self: *Ledger, acct: *Account) void {
        if (acct.stake_mtri < self.policy.min_stake_mtri or
            acct.consecutive_rejections >= self.policy.rejection_tolerance)
        {
            acct.status = .suspended;
        } else {
            acct.status = .probation;
        }
    }

    /// What each developer is owed, aggregated across the nodes they run.
    pub fn payouts(self: *Ledger, gpa: std.mem.Allocator) !std.StringHashMapUnmanaged(u64) {
        var out: std.StringHashMapUnmanaged(u64) = .empty;
        var it = self.accounts.valueIterator();
        while (it.next()) |a| {
            const gop = try out.getOrPut(gpa, a.owner);
            if (!gop.found_existing) gop.value_ptr.* = 0;
            gop.value_ptr.* += a.credit_mtri;
        }
        return out;
    }
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

fn makeJob(n: u32) protocol.Job {
    var wv: protocol.Trits = @splat(0);
    for (&wv, 0..) |*t, i| t.* = if ((i + n) % 3 == 0) 1 else if ((i + n) % 3 == 1) -1 else 0;
    return protocol.Job.withNonce(n, protocol.pack(wv), protocol.pack(wv));
}

test "a damaged frame costs the operator nothing, a lie costs them stake" {
    var l = try Ledger.init(std.testing.allocator, .{});
    defer l.deinit();
    try l.register(0x8008, "honest-but-badly-cabled", true, 5000);

    // Measured on hardware: at ~2.4 Mbaud one of three boards returned a few
    // percent of its responses damaged, and the ledger charged it as fraud.
    // An honest operator losing stake to a marginal cable drives people off a
    // network faster than any cheat does.
    const j = makeJob(1);
    var damaged = protocol.execute(j, 0x8008);
    damaged.tag ^= 0x40; // one flipped bit on the wire

    const s1 = try l.settle(0x8008, j, damaged, protocol.verify(j, damaged));
    try std.testing.expectEqual(Outcome.corrupt_not_charged, s1.outcome);
    try std.testing.expectEqual(@as(u64, 5000), l.get(0x8008).?.stake_mtri);
    try std.testing.expectEqual(@as(u64, 0), l.get(0x8008).?.slashed_mtri);
    try std.testing.expectEqual(@as(u64, 1), l.get(0x8008).?.corrupted);
    // Not credited either — a damaged receipt is not evidence of work.
    try std.testing.expectEqual(@as(u64, 0), l.get(0x8008).?.credit_mtri);
    // And it is not counted against the node's reputation.
    try std.testing.expectEqual(@as(u64, 0), l.get(0x8008).?.rejected);

    // A node that signs a wrong answer had the key and used it. That is a lie.
    const j2 = makeJob(2);
    const wrong_y = protocol.dot(j2.w, j2.x) +% 1;
    const lied: protocol.Receipt = .{
        .y = wrong_y,
        .status = protocol.status_ok,
        .nonce = j2.nonce,
        .node_id = 0x8008,
        .tag = protocol.receiptTag(j2, wrong_y, 0x8008),
        .kind = .crc32,
    };
    const s2 = try l.settle(0x8008, j2, lied, protocol.verify(j2, lied));
    try std.testing.expectEqual(Outcome.rejected_and_slashed, s2.outcome);
    try std.testing.expect(l.get(0x8008).?.slashed_mtri > 0);
}

test "a policy where cheating pays is refused" {
    const bad: Policy = .{
        .reward_per_job_mtri = 10,
        .slash_per_bad_receipt_mtri = 5,
        .audit_rate_percent = 100,
    };
    try std.testing.expect(!bad.isSound());
    try std.testing.expectError(Error.UnsoundPolicy, Ledger.init(std.testing.allocator, bad));

    // Sampling makes an otherwise fine slash too small.
    const sampled: Policy = .{
        .reward_per_job_mtri = 1,
        .slash_per_bad_receipt_mtri = 50,
        .audit_rate_percent = 1,
    };
    try std.testing.expect(!sampled.isSound());

    const good: Policy = .{
        .reward_per_job_mtri = 1,
        .slash_per_bad_receipt_mtri = 200,
        .audit_rate_percent = 100,
    };
    try std.testing.expect(good.isSound());
}

test "honest work accrues credit and stake is untouched" {
    var l = try Ledger.init(std.testing.allocator, .{});
    defer l.deinit();
    try l.register(0x1001, "alice", true, 5000);

    for (0..100) |i| {
        const j = makeJob(@intCast(i));
        const r = protocol.execute(j, 0x1001);
        const s = try l.settle(0x1001, j, r, protocol.verify(j, r));
        try std.testing.expectEqual(Outcome.credited, s.outcome);
    }
    const a = l.get(0x1001).?;
    try std.testing.expectEqual(@as(u64, 100), a.accepted);
    try std.testing.expectEqual(@as(u64, 100), a.credit_mtri);
    try std.testing.expectEqual(@as(u64, 5000), a.stake_mtri);
    try std.testing.expectEqual(Status.active, a.status);
    try std.testing.expectEqual(@as(u64, 100), l.jobs_on_silicon);
}

test "a free rider is suspended before it can earn more than it loses" {
    var l = try Ledger.init(std.testing.allocator, .{});
    defer l.deinit();
    try l.register(0x2002, "mallory", false, 5000);

    var credited: u64 = 0;
    var slashed: u64 = 0;
    for (0..50) |i| {
        const j = makeJob(@intCast(i));
        if (!l.isEligible(0x2002)) break;
        // Always wrong, always correctly tagged.
        const wrong: protocol.Receipt = .{
            .y = protocol.dot(j.w, j.x) +% 1,
            .status = protocol.status_ok,
            .nonce = j.nonce,
            .node_id = 0x2002,
            .tag = protocol.receiptTag(j, protocol.dot(j.w, j.x) +% 1, 0x2002),
            .kind = .crc32,
        };
        const s = try l.settle(0x2002, j, wrong, protocol.verify(j, wrong));
        credited += s.credit_delta_mtri;
        slashed += s.slash_delta_mtri;
    }
    const a = l.get(0x2002).?;
    try std.testing.expectEqual(Status.suspended, a.status);
    try std.testing.expectEqual(@as(u64, 0), credited);
    try std.testing.expect(slashed > 0);
    try std.testing.expect(a.reputation() == 0.0);
}

test "credit for another node's identity is not paid to anyone" {
    var l = try Ledger.init(std.testing.allocator, .{});
    defer l.deinit();
    try l.register(0x3003, "victim", true, 5000);
    try l.register(0x4004, "thief", false, 5000);

    const j = makeJob(7);
    // The thief computes honestly but signs as the victim.
    const stolen = protocol.execute(j, 0x3003);
    const s = try l.settle(0x4004, j, stolen, protocol.verify(j, stolen));

    try std.testing.expectEqual(Outcome.identity_mismatch, s.outcome);
    try std.testing.expectEqual(@as(u64, 0), l.get(0x3003).?.credit_mtri);
    try std.testing.expectEqual(@as(u64, 0), l.get(0x4004).?.credit_mtri);
    try std.testing.expect(l.get(0x4004).?.slashed_mtri > 0);
}

test "the same receipt cannot be settled twice" {
    var l = try Ledger.init(std.testing.allocator, .{});
    defer l.deinit();
    try l.register(0x5005, "carol", true, 5000);

    const j = makeJob(42);
    const r = protocol.execute(j, 0x5005);
    const first = try l.settle(0x5005, j, r, protocol.verify(j, r));
    try std.testing.expectEqual(Outcome.credited, first.outcome);

    const second = try l.settle(0x5005, j, r, protocol.verify(j, r));
    try std.testing.expectEqual(Outcome.rejected_and_slashed, second.outcome);
    try std.testing.expectEqual(@as(u64, 1), l.get(0x5005).?.credit_mtri);
}

test "a node must bond a stake before it receives work" {
    var l = try Ledger.init(std.testing.allocator, .{});
    defer l.deinit();
    try std.testing.expectError(Error.InsufficientStake, l.register(0x6006, "dave", true, 10));
    try l.register(0x6006, "dave", true, 1000);
    try std.testing.expectError(Error.DuplicateNode, l.register(0x6006, "dave", true, 1000));
}

test "payouts aggregate across the nodes one developer runs" {
    var l = try Ledger.init(std.testing.allocator, .{});
    defer l.deinit();
    try l.register(0x7001, "erin", true, 2000);
    try l.register(0x7002, "erin", false, 2000);
    try l.register(0x7003, "frank", false, 2000);

    for ([_]u32{ 0x7001, 0x7002, 0x7003 }, 0..) |id, k| {
        for (0..(k + 1) * 10) |i| {
            const j = makeJob(@intCast(i));
            const r = protocol.execute(j, id);
            _ = try l.settle(id, j, r, protocol.verify(j, r));
        }
    }

    var p = try l.payouts(std.testing.allocator);
    defer p.deinit(std.testing.allocator);
    try std.testing.expectEqual(@as(u64, 30), p.get("erin").?); // 10 + 20
    try std.testing.expectEqual(@as(u64, 30), p.get("frank").?);
}
