//! TRI-NET wire protocol — ternary compute jobs and verifiable receipts.
//!
//! This module is the single Zig-side definition of the bytes that travel
//! between a TRI-NET coordinator and a node. It mirrors, byte for byte, what
//! `fpga/vivado/trinet_mac32_ax7203.v` implements in silicon and what
//! `conformance/trinet_mac32_conformance_ax7203.py` checks over UART.
//!
//! The unit of work is one 32-wide ternary dot product:
//!
//!     y = sum_{i=0..31} w[i] * x[i],   w[i], x[i] in {-1, 0, +1}
//!
//! chosen because it is exactly one row of a ternary-weight matrix multiply,
//! so a model's forward pass decomposes into these jobs without remainder.
//!
//! WHAT A RECEIPT PROVES, AND WHAT IT DOES NOT.
//! The CRC-32 tag binds the answer to the job bytes, the nonce and the node
//! identity, so a node cannot return a stale answer, answer a different job,
//! or claim another node's identity without detection. It is a checksum, not
//! a signature: any party who knows the scheme can compute the same tag, so
//! the tag alone does not prove the work happened on the claimed silicon.
//! Unforgeability and physical binding are separate layers — see
//! `ledger.zig` for what the settlement layer actually relies on.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");

pub const n_trits = 32;
pub const n_bytes = n_trits / 4; // two bits per trit
pub const request_len = 24;
pub const response_len = 15;
/// v2 carries a 64-bit keyed tag instead of a 32-bit CRC.
pub const response_len_v2 = 19;
pub const preimage_len = 26;

pub const magic_req = [2]u8{ 0xAA, 0x55 };
pub const magic_resp: u8 = 0xA5;
pub const op_mac32: u8 = 0x01;
pub const status_ok: u8 = 0x01;

/// Default synthesised identity, the ASCII bytes "TRIN" read little-endian.
pub const default_node_id: u32 = 0x5452_494E;

/// Trit codes as they sit in the packed representation.
pub const TritCode = enum(u2) {
    zero = 0b00,
    plus = 0b01,
    minus = 0b10,
    reserved = 0b11, // canonicalised to zero, both here and in the RTL

    pub fn value(self: TritCode) i8 {
        return switch (self) {
            .zero, .reserved => 0,
            .plus => 1,
            .minus => -1,
        };
    }

    pub fn fromValue(v: i8) TritCode {
        return switch (v) {
            1 => .plus,
            -1 => .minus,
            else => .zero,
        };
    }
};

pub const Trits = [n_trits]i8;
pub const Packed = [n_bytes]u8;

/// Pack 32 values in {-1, 0, +1} into 8 bytes, four trits per byte, the
/// lowest-indexed trit in the least significant bit pair of byte 0.
pub fn pack(trits: Trits) Packed {
    var out: Packed = @splat(0);
    for (trits, 0..) |t, i| {
        const code: u8 = @intFromEnum(TritCode.fromValue(t));
        out[i / 4] |= code << @intCast(2 * (i % 4));
    }
    return out;
}

/// Inverse of `pack`. The reserved code 0b11 decodes to zero.
pub fn unpack(bytes: Packed) Trits {
    var out: Trits = @splat(0);
    for (&out, 0..) |*t, i| {
        const raw: u2 = @truncate(bytes[i / 4] >> @intCast(2 * (i % 4)));
        t.* = @as(TritCode, @enumFromInt(raw)).value();
    }
    return out;
}

/// Exact integer ternary dot product. Range [-32, +32], so it fits i8.
pub fn dot(w: Packed, x: Packed) i8 {
    const wt = unpack(w);
    const xt = unpack(x);
    var acc: i32 = 0;
    for (wt, xt) |a, b| acc += @as(i32, a) * @as(i32, b);
    return @intCast(acc);
}

pub const Job = struct {
    op: u8 = op_mac32,
    nonce: [4]u8,
    w: Packed,
    x: Packed,

    pub fn nonceValue(self: Job) u32 {
        return std.mem.readInt(u32, &self.nonce, .little);
    }

    pub fn withNonce(n: u32, w: Packed, x: Packed) Job {
        var nb: [4]u8 = undefined;
        std.mem.writeInt(u32, &nb, n, .little);
        return .{ .nonce = nb, .w = w, .x = x };
    }
};

/// How a receipt's tag was produced. The two are not interchangeable, and the
/// verifier must know which law to apply — a keyed tag checked as a CRC would
/// pass nothing, and a CRC checked as keyed would pass everything.
pub const TagKind = enum { crc32, siphash24 };

pub const Receipt = struct {
    y: i8,
    status: u8,
    nonce: [4]u8,
    node_id: u32,
    /// CRC-32 occupies the low 32 bits; SipHash-2-4 uses all 64.
    tag: u64,
    kind: TagKind = .crc32,
};

/// The exact 26 bytes the RTL feeds through its CRC engine.
pub fn preimage(job: Job, y: i8, node_id: u32) [preimage_len]u8 {
    var buf: [preimage_len]u8 = undefined;
    buf[0] = job.op;
    @memcpy(buf[1..5], &job.nonce);
    @memcpy(buf[5..13], &job.w);
    @memcpy(buf[13..21], &job.x);
    buf[21] = @bitCast(y);
    std.mem.writeInt(u32, buf[22..26], node_id, .little);
    return buf;
}

/// CRC-32 (IEEE 802.3, reflected) — identical to Python `zlib.crc32` and to
/// the LFSR in the RTL.
pub fn receiptTag(job: Job, y: i8, node_id: u32) u32 {
    return std.hash.Crc32.hash(&preimage(job, y, node_id));
}

/// Keyed receipt tag — SipHash-2-4 over the same preimage.
///
/// The difference from `receiptTag` is the whole point: a CRC can be computed
/// by anyone, so it proves a response is self-consistent and nothing more. A
/// keyed tag can only be produced by a key holder, which is what makes a
/// receipt evidence rather than arithmetic.
///
/// It does not make a receipt unforgeable by the party that holds the key. A
/// node operator has their own bitstream and therefore their own key; this
/// stops third parties forging on their behalf, and with per-node keys it stops
/// one operator forging for another. See `fpga/openxc7-synth/trinet_siphash24.v`
/// for what closing the remaining gap requires.
pub fn receiptTagKeyed(job: Job, y: i8, node_id: u32, key: [16]u8) u64 {
    return std.hash.SipHash64(2, 4).toInt(&preimage(job, y, node_id), &key);
}

pub fn encodeRequest(job: Job) [request_len]u8 {
    var buf: [request_len]u8 = undefined;
    buf[0] = magic_req[0];
    buf[1] = magic_req[1];
    buf[2] = job.op;
    @memcpy(buf[3..7], &job.nonce);
    @memcpy(buf[7..15], &job.w);
    @memcpy(buf[15..23], &job.x);
    buf[23] = 0x00; // TRIG
    return buf;
}

pub fn encodeResponse(r: Receipt) [response_len]u8 {
    var buf: [response_len]u8 = undefined;
    buf[0] = magic_resp;
    buf[1] = @bitCast(r.y);
    buf[2] = r.status;
    @memcpy(buf[3..7], &r.nonce);
    std.mem.writeInt(u32, buf[7..11], r.node_id, .little);
    std.mem.writeInt(u32, buf[11..15], @truncate(r.tag), .little);
    return buf;
}

pub fn decodeResponse(raw: []const u8) ?Receipt {
    if (raw.len < response_len or raw[0] != magic_resp) return null;
    return .{
        .y = @bitCast(raw[1]),
        .status = raw[2],
        .nonce = raw[3..7].*,
        .node_id = std.mem.readInt(u32, raw[7..11], .little),
        .tag = std.mem.readInt(u32, raw[11..15], .little),
        .kind = .crc32,
    };
}

pub fn decodeResponseV2(raw: []const u8) ?Receipt {
    if (raw.len < response_len_v2 or raw[0] != magic_resp) return null;
    return .{
        .y = @bitCast(raw[1]),
        .status = raw[2],
        .nonce = raw[3..7].*,
        .node_id = std.mem.readInt(u32, raw[7..11], .little),
        .tag = std.mem.readInt(u64, raw[11..19], .little),
        .kind = .siphash24,
    };
}

pub fn encodeResponseV2(r: Receipt) [response_len_v2]u8 {
    var buf: [response_len_v2]u8 = undefined;
    buf[0] = magic_resp;
    buf[1] = @bitCast(r.y);
    buf[2] = r.status;
    @memcpy(buf[3..7], &r.nonce);
    std.mem.writeInt(u32, buf[7..11], r.node_id, .little);
    std.mem.writeInt(u64, buf[11..19], r.tag, .little);
    return buf;
}

/// Honest local execution producing a keyed receipt.
pub fn executeKeyed(job: Job, node_id: u32, key: [16]u8) Receipt {
    const y = dot(job.w, job.x);
    return .{
        .y = y,
        .status = status_ok,
        .nonce = job.nonce,
        .node_id = node_id,
        .tag = receiptTagKeyed(job, y, node_id, key),
        .kind = .siphash24,
    };
}

pub const Verdict = enum {
    ok,
    bad_status,
    nonce_mismatch,
    /// A wrong answer carrying a tag that is VALID for it. Only a key holder
    /// can produce that, so the node computed nothing and signed the guess.
    wrong_result,
    /// The response is not self-consistent: the tag matches neither the correct
    /// answer nor the one returned. A node with the key cannot produce this on
    /// purpose, so it is a damaged frame rather than a lie.
    corrupt,

    pub fn accepted(self: Verdict) bool {
        return self == .ok;
    }

    /// Whether this verdict is evidence of dishonesty, as opposed to a link
    /// that dropped bits. The distinction decides whether an operator loses
    /// stake, so it must not be guessed at.
    pub fn indictsTheNode(self: Verdict) bool {
        return switch (self) {
            .ok, .corrupt => false,
            .bad_status, .nonce_mismatch, .wrong_result => true,
        };
    }

    pub fn reason(self: Verdict) []const u8 {
        return switch (self) {
            .ok => "ok",
            .bad_status => "node reported a non-ok status",
            .nonce_mismatch => "nonce does not match the job (replay or crossed response)",
            .wrong_result => "wrong answer, correctly tagged — the node had the key and signed a guess",
            .corrupt => "response is not self-consistent — a damaged frame, not a lie",
        };
    }
};

/// The check the settlement layer runs before crediting any work.
///
/// It recomputes the answer from the job, which is cheap here because the unit
/// of work is small. For work units where recomputation is not cheap, this is
/// where a sampling or quorum policy belongs instead — see `mesh.zig`.
pub fn verify(job: Job, r: Receipt) Verdict {
    return verifyWithKey(job, r, null);
}

/// The same check, with the key a keyed receipt needs.
///
/// Passing the wrong kind of key is a caller error worth failing loudly on: a
/// keyed receipt verified without a key would be accepted on a CRC that was
/// never computed, which is the one mistake that would silently undo the whole
/// point of keying the tag.
pub fn verifyWithKey(job: Job, r: Receipt, key: ?[16]u8) Verdict {
    if (r.status != status_ok) return .bad_status;

    if (!std.mem.eql(u8, &r.nonce, &job.nonce)) {
        // A replayed receipt is tagged over the OLD job, so it fits nothing we
        // can reconstruct. A request whose nonce was damaged in transit makes
        // the node tag over the nonce it actually received, with our operands
        // — reconstructable exactly. Checking that separates a replay attack
        // from a corrupted request, and only one of them should cost stake.
        const as_received: Job = .{ .op = job.op, .nonce = r.nonce, .w = job.w, .x = job.x };
        const fits_damaged_request = switch (r.kind) {
            .crc32 => r.tag == receiptTag(as_received, r.y, r.node_id),
            .siphash24 => if (key) |k| r.tag == receiptTagKeyed(as_received, r.y, r.node_id, k) else false,
        };
        return if (fits_damaged_request) .corrupt else .nonce_mismatch;
    }

    // Does the tag match the answer the node actually returned? Only something
    // holding the key can make that true, so it separates a lie from a damaged
    // frame — and that separation decides whether an operator loses stake.
    const tag_fits_response = switch (r.kind) {
        .crc32 => r.tag == receiptTag(job, r.y, r.node_id),
        .siphash24 => if (key) |k| r.tag == receiptTagKeyed(job, r.y, r.node_id, k) else false,
    };

    if (r.y != dot(job.w, job.x)) {
        // Wrong answer. Correctly tagged means the node had the key and signed
        // a guess; incorrectly tagged means bits were lost on the way.
        return if (tag_fits_response) .wrong_result else .corrupt;
    }
    // Right answer with a tag that does not fit it can only be corruption: a
    // node that computed correctly has no reason to mis-tag, and an attacker
    // gains nothing by breaking a receipt that was going to be accepted.
    return if (tag_fits_response) .ok else .corrupt;
}

/// Honest local execution of a job — what an emulated node runs, and what a
/// verifier uses as its oracle.
pub fn execute(job: Job, node_id: u32) Receipt {
    const y = dot(job.w, job.x);
    return .{
        .y = y,
        .status = status_ok,
        .nonce = job.nonce,
        .node_id = node_id,
        .tag = receiptTag(job, y, node_id),
        .kind = .crc32,
    };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test "trit pack round trip including the reserved code" {
    var trits: Trits = @splat(0);
    for (&trits, 0..) |*t, i| t.* = switch (i % 3) {
        0 => 0,
        1 => 1,
        else => -1,
    };
    try std.testing.expectEqual(trits, unpack(pack(trits)));

    // 0b11 in every slot must read back as all zeros.
    const all_reserved: Packed = @splat(0xFF);
    try std.testing.expectEqual(@as(Trits, @splat(0)), unpack(all_reserved));
}

test "dot product corners" {
    const zeros = pack(@as(Trits, @splat(0)));
    const ones = pack(@as(Trits, @splat(1)));
    const minus = pack(@as(Trits, @splat(-1)));
    var altv: Trits = @splat(0);
    for (&altv, 0..) |*t, i| t.* = if (i % 2 == 0) 1 else -1;
    const alt = pack(altv);

    try std.testing.expectEqual(@as(i8, 32), dot(ones, ones));
    try std.testing.expectEqual(@as(i8, -32), dot(ones, minus));
    try std.testing.expectEqual(@as(i8, 32), dot(minus, minus));
    try std.testing.expectEqual(@as(i8, 0), dot(zeros, ones));
    try std.testing.expectEqual(@as(i8, 32), dot(alt, alt));
    try std.testing.expectEqual(@as(i8, 0), dot(alt, ones));
}

test "receipt tag matches the value the RTL and Python golden agree on" {
    // Vector 0 from conformance/trinet_mac32_conformance_ax7203.py: an
    // all-zero job under the default node id. The RTL produced this tag on the
    // first simulation run, and zlib.crc32 produces it in Python.
    const job: Job = .{
        .op = op_mac32,
        .nonce = .{ 0, 0, 0, 0 },
        .w = @splat(0),
        .x = @splat(0),
    };
    try std.testing.expectEqual(@as(u32, 0xa8fa2bdf), receiptTag(job, 0, default_node_id));
}

test "verifier accepts honest work and rejects each tampering" {
    var wv: Trits = @splat(0);
    var xv: Trits = @splat(0);
    for (&wv, 0..) |*t, i| t.* = if (i % 3 == 0) 1 else if (i % 3 == 1) -1 else 0;
    for (&xv, 0..) |*t, i| t.* = if (i % 2 == 0) 1 else -1;

    const job = Job.withNonce(0xDEADBEEF, pack(wv), pack(xv));
    const good = execute(job, default_node_id);
    try std.testing.expectEqual(Verdict.ok, verify(job, good));

    // A node that skips the work still holds the key, so it signs its guess:
    // wrong answer, tag VALID for that answer. That is dishonesty.
    var lied = good;
    lied.y +%= 1;
    lied.tag = receiptTag(job, lied.y, lied.node_id);
    try std.testing.expectEqual(Verdict.wrong_result, verify(job, lied));
    try std.testing.expect(Verdict.wrong_result.indictsTheNode());

    // The same wrong answer with the ORIGINAL tag is what a damaged frame
    // looks like — nothing holding the key would produce that pair.
    var damaged_result = good;
    damaged_result.y +%= 1;
    try std.testing.expectEqual(Verdict.corrupt, verify(job, damaged_result));

    // A flipped tag bit over a correct answer is what a damaged frame looks
    // like, and it must not be charged as dishonesty.
    var damaged_tag = good;
    damaged_tag.tag ^= 1;
    try std.testing.expectEqual(Verdict.corrupt, verify(job, damaged_tag));
    try std.testing.expect(!Verdict.corrupt.indictsTheNode());

    // A replay carries a tag over the OLD job, which fits nothing we can
    // reconstruct — that is an attack.
    var replayed = good;
    replayed.nonce = .{ 1, 2, 3, 4 };
    try std.testing.expectEqual(Verdict.nonce_mismatch, verify(job, replayed));
    try std.testing.expect(Verdict.nonce_mismatch.indictsTheNode());

    // A request whose nonce was damaged in transit makes the node tag over the
    // nonce it actually received, with our operands. That is reconstructable,
    // and it must not be charged as a replay.
    const seen: Job = .{ .op = job.op, .nonce = .{ 9, 9, 9, 9 }, .w = job.w, .x = job.x };
    const honest_on_damaged = execute(seen, default_node_id);
    try std.testing.expectEqual(Verdict.corrupt, verify(job, honest_on_damaged));

    var impersonated = good;
    impersonated.node_id +%= 7;
    try std.testing.expectEqual(Verdict.corrupt, verify(job, impersonated));

    var bad_status = good;
    bad_status.status = 0x00;
    try std.testing.expectEqual(Verdict.bad_status, verify(job, bad_status));
}

test "the keyed tag matches the RTL and depends on the key" {
    // Reference vector shared with formal/trinet_siphash24_tb.v: the preimage
    // bytes 0x00..0x19 under key bytes 0x00..0x0f. The RTL reproduces it, so
    // this pins the Zig side to the same law.
    var key: [16]u8 = undefined;
    for (&key, 0..) |*k, i| k.* = @intCast(i);
    var msg: [preimage_len]u8 = undefined;
    for (&msg, 0..) |*m, i| m.* = @intCast(i);
    try std.testing.expectEqual(
        @as(u64, 0x17d835b85bbb15f3),
        std.hash.SipHash64(2, 4).toInt(&msg, &key),
    );

    // And on a real job: a different key must give a different tag, or the key
    // is not reaching the state.
    const job = Job.withNonce(0xC0FFEE, @splat(0x55), @splat(0xAA));
    const y = dot(job.w, job.x);
    const t1 = receiptTagKeyed(job, y, default_node_id, key);
    const t2 = receiptTagKeyed(job, y, default_node_id, @splat(0xA5));
    try std.testing.expect(t1 != t2);

    // Sensitive to the result and the node, exactly like the unkeyed tag.
    try std.testing.expect(t1 != receiptTagKeyed(job, y +% 1, default_node_id, key));
    try std.testing.expect(t1 != receiptTagKeyed(job, y, default_node_id +% 1, key));
}

test "wire encoding round trip" {
    const job = Job.withNonce(0x01020304, @splat(0x55), @splat(0xAA));
    const req = encodeRequest(job);
    try std.testing.expectEqual(@as(u8, 0xAA), req[0]);
    try std.testing.expectEqual(@as(u8, 0x55), req[1]);
    try std.testing.expectEqual(op_mac32, req[2]);
    try std.testing.expectEqualSlices(u8, &job.nonce, req[3..7]);
    try std.testing.expectEqualSlices(u8, &job.w, req[7..15]);
    try std.testing.expectEqualSlices(u8, &job.x, req[15..23]);

    const r = execute(job, 0x12345678);
    const wire = encodeResponse(r);
    const back = decodeResponse(&wire).?;
    try std.testing.expectEqual(r.y, back.y);
    try std.testing.expectEqual(r.node_id, back.node_id);
    try std.testing.expectEqual(r.tag, back.tag);
    try std.testing.expectEqual(Verdict.ok, verify(job, back));
}

test "a node that recomputes honestly always passes, whatever the inputs" {
    var prng: std.Random.DefaultPrng = .init(0x7213);
    const rand = prng.random();
    for (0..2000) |i| {
        var wv: Trits = @splat(0);
        var xv: Trits = @splat(0);
        for (&wv) |*t| t.* = rand.intRangeAtMost(i8, -1, 1);
        for (&xv) |*t| t.* = rand.intRangeAtMost(i8, -1, 1);
        const job = Job.withNonce(@intCast(i), pack(wv), pack(xv));
        try std.testing.expectEqual(Verdict.ok, verify(job, execute(job, default_node_id)));
    }
}
