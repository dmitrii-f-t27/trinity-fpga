//! `trinet` — command line for the ternary internet.
//!
//!   trinet selftest              exercise the whole stack and report honestly
//!   trinet probe [serial]        talk to a physical node and verify its receipts
//!   trinet demo [serial]         stand up a mesh, run the agent, print the books
//!   trinet agent "<task>"        run one agent task on a mesh
//!   trinet serve <port> [serial] expose a node over TCP so others can use it
//!   trinet join                  print what a new developer has to do
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const protocol = @import("protocol.zig");
const node_mod = @import("node.zig");
const mesh_mod = @import("mesh.zig");
const ledger_mod = @import("ledger.zig");
const model_mod = @import("model.zig");
const agent_mod = @import("agent.zig");
const net = @import("net.zig");

const default_serial = "/dev/cu.usbserial-1110";
const default_baud = 160000;

/// Writer that goes to stderr through std.debug, which is the one output path
/// that is stable across Zig releases.
const Out = struct {
    pub fn print(_: Out, comptime fmt: []const u8, args: anytype) !void {
        std.debug.print(fmt, args);
    }
};
const out: Out = .{};

fn line() void {
    std.debug.print("---------------------------------------------------------------\n", .{});
}

/// Zig 0.16 passes the process environment to main rather than exposing it
/// through globals; taking `Init.Minimal` is how a program reads its argv.
pub fn main(init: std.process.Init.Minimal) !void {
    var dbg: std.heap.DebugAllocator(.{}) = .init;
    defer _ = dbg.deinit();
    const gpa = dbg.allocator();

    var arena_state: std.heap.ArenaAllocator = .init(gpa);
    defer arena_state.deinit();
    const args = try init.args.toSlice(arena_state.allocator());

    const cmd = if (args.len > 1) args[1] else "selftest";

    if (std.mem.eql(u8, cmd, "selftest")) return selftest(gpa);
    if (std.mem.eql(u8, cmd, "probe")) return probe(gpa, if (args.len > 2) args[2] else default_serial);
    if (std.mem.eql(u8, cmd, "demo")) return demo(gpa, if (args.len > 2) args[2] else null);
    if (std.mem.eql(u8, cmd, "agent")) return runAgent(gpa, if (args.len > 2) args[2] else "fix the failing ternary build", if (args.len > 3) args[3] else null);
    if (std.mem.eql(u8, cmd, "serve")) return serve(gpa, args);
    if (std.mem.eql(u8, cmd, "join")) return joinHelp();

    std.debug.print("unknown command '{s}'\n", .{cmd});
    std.debug.print("try: selftest | probe | demo | agent | serve | join\n", .{});
    return error.UnknownCommand;
}

// ---------------------------------------------------------------------------

fn selftest(gpa: std.mem.Allocator) !void {
    std.debug.print("TRI-NET self-test\n", .{});
    line();

    // 1. Protocol agreement with the silicon's own arithmetic.
    const zero_job: protocol.Job = .{ .nonce = .{ 0, 0, 0, 0 }, .w = @splat(0), .x = @splat(0) };
    const tag = protocol.receiptTag(zero_job, 0, protocol.default_node_id);
    std.debug.print("receipt tag for the all-zero job : {x:0>8}", .{tag});
    if (tag == 0xa8fa2bdf) {
        std.debug.print("  matches RTL simulation and Python golden\n", .{});
    } else {
        std.debug.print("  MISMATCH — the three implementations have diverged\n", .{});
        return error.ProtocolDivergence;
    }

    // 2. Policy soundness.
    const policy: ledger_mod.Policy = .{};
    std.debug.print("settlement policy               : reward {d} mTRI/job, slash {d} mTRI, audit {d}%\n", .{ policy.reward_per_job_mtri, policy.slash_per_bad_receipt_mtri, policy.audit_rate_percent });
    std.debug.print("cheating is unprofitable        : {s} (a caught cheat costs {d} jobs of honest work)\n", .{ if (policy.isSound()) "yes" else "NO", policy.slashInJobs() });

    // 3. Adversaries against the verifier.
    line();
    std.debug.print("adversarial nodes vs the verifier\n", .{});
    const behaviours = [_]node_mod.Behaviour{ .honest, .lazy, .replay, .impersonator };
    for (behaviours) |b| {
        var m = try mesh_mod.Mesh.init(gpa, policy);
        defer m.deinit();
        try m.join(node_mod.Node.initEmulated(0xB0, @tagName(b), b), "test", 100000);

        var credited: u64 = 0;
        var caught: u64 = 0;
        for (0..200) |i| {
            var wv: protocol.Trits = @splat(0);
            for (&wv, 0..) |*t, k| t.* = @intCast(@as(i32, @intCast((i + k) % 3)) - 1);
            const job = protocol.Job.withNonce(@intCast(i + 1), protocol.pack(wv), protocol.pack(wv));
            const o = m.dispatch(job) catch break;
            if (o.settlement.outcome == .credited) credited += 1 else caught += 1;
        }
        std.debug.print("  {s:<14} credited {d:>3}/200, rejected {d:>3}\n", .{ @tagName(b), credited, caught });
    }

    line();
    std.debug.print("run `zig test src/trinet/agent.zig -lc` for the full 38-test suite\n", .{});
    std.debug.print("run `trinet probe` to check a physical board\n", .{});
}

// ---------------------------------------------------------------------------

fn probe(gpa: std.mem.Allocator, path: []const u8) !void {
    _ = gpa;
    std.debug.print("probing physical node on {s} at {d} baud\n", .{ path, default_baud });
    line();

    var buf: [256]u8 = undefined;
    const zpath = try std.fmt.bufPrintZ(&buf, "{s}", .{path});

    var n = node_mod.Node.initFpga(protocol.default_node_id, "ax7203", zpath, default_baud) catch |e| {
        std.debug.print("could not open the port: {s}\n", .{@errorName(e)});
        std.debug.print("the board may not be attached, or a bitstream that speaks this\n", .{});
        std.debug.print("protocol may not be loaded. Nothing here is a hardware result.\n", .{});
        return e;
    };
    defer n.deinit();

    var ok: usize = 0;
    var fail: usize = 0;
    var first_node_id: ?u32 = null;
    var reasons: [8][]const u8 = undefined;
    var n_reasons: usize = 0;

    var prng: std.Random.DefaultPrng = .init(0x7213);
    const rand = prng.random();

    for (0..64) |i| {
        var wv: protocol.Trits = @splat(0);
        var xv: protocol.Trits = @splat(0);
        if (i < 4) {
            // Structural corners first: they catch framing bugs immediately.
            const fills = [_]i8{ 0, 1, -1, 1 };
            for (&wv) |*t| t.* = fills[i];
            for (&xv) |*t| t.* = fills[(i + 1) % 4];
        } else {
            for (&wv) |*t| t.* = rand.intRangeAtMost(i8, -1, 1);
            for (&xv) |*t| t.* = rand.intRangeAtMost(i8, -1, 1);
        }
        const job = protocol.Job.withNonce(@intCast(i + 1), protocol.pack(wv), protocol.pack(xv));
        const r = n.execute(job) catch |e| {
            fail += 1;
            if (n_reasons < reasons.len) {
                reasons[n_reasons] = @errorName(e);
                n_reasons += 1;
            }
            continue;
        };
        if (first_node_id == null) first_node_id = r.node_id;
        const v = protocol.verify(job, r);
        if (v.accepted()) ok += 1 else {
            fail += 1;
            if (n_reasons < reasons.len) {
                reasons[n_reasons] = v.reason();
                n_reasons += 1;
            }
        }
    }

    std.debug.print("receipts verified: {d}/64\n", .{ok});
    if (first_node_id) |id| std.debug.print("node id reported : {x:0>8}\n", .{id});
    if (fail > 0) {
        std.debug.print("failures:\n", .{});
        for (reasons[0..n_reasons]) |r| std.debug.print("  {s}\n", .{r});
    }
    line();
    if (ok == 64) {
        std.debug.print("RESULT: this is a hardware-measured ternary compute node.\n", .{});
    } else {
        std.debug.print("RESULT: not a verified hardware node. Do not report this as silicon.\n", .{});
    }
}

// ---------------------------------------------------------------------------

/// Build a mesh: one physical node when a board answers, plus emulated peers.
/// The emulated peers are labelled as such everywhere, and the report says what
/// fraction of work actually touched silicon.
fn buildMesh(gpa: std.mem.Allocator, serial_path: ?[]const u8, buf: []u8) !mesh_mod.Mesh {
    var m = try mesh_mod.Mesh.init(gpa, .{});
    errdefer m.deinit();

    if (serial_path) |p| {
        const zpath = try std.fmt.bufPrintZ(buf, "{s}", .{p});
        if (node_mod.Node.initFpga(protocol.default_node_id, "ax7203-node0", zpath, default_baud)) |fpga| {
            try m.join(fpga, "operator", 100000);
            std.debug.print("node 0: physical AX7203 on {s}\n", .{p});
        } else |e| {
            std.debug.print("node 0: no board ({s}) — running without a physical node\n", .{@errorName(e)});
        }
    }

    try m.join(node_mod.Node.initEmulated(0x4E4F4431, "peer-1", .honest), "developer-1", 100000);
    try m.join(node_mod.Node.initEmulated(0x4E4F4432, "peer-2", .honest), "developer-2", 100000);
    return m;
}

fn demo(gpa: std.mem.Allocator, serial_path: ?[]const u8) !void {
    std.debug.print("TRI-NET demonstration\n", .{});
    line();

    var pathbuf: [256]u8 = undefined;
    var m = try buildMesh(gpa, serial_path orelse default_serial, &pathbuf);
    defer m.deinit();
    std.debug.print("mesh: {d} nodes, {d} physical\n\n", .{ m.nodeCount(), m.physicalCount() });

    const model = try model_mod.Model.synthetic(gpa, 3, 32, 0x1614);
    var agent = try agent_mod.Agent.init(gpa, "igla-coder", model);
    defer agent.deinit(gpa);

    const tasks = [_][]const u8{
        "the gf16 adder conformance test fails on hardware",
        "synthesise the ternary mac and flash it to the board",
        "document the receipt format for new node operators",
    };

    for (tasks) |t| {
        const o = try agent.run(&m, t);
        std.debug.print("task    : {s}\n", .{t});
        std.debug.print("action  : {s} (margin {d:.3} over {s})\n", .{
            o.decision.action.label(),
            o.decision.confidence - o.decision.runner_up_confidence,
            o.decision.runner_up.label(),
        });
        std.debug.print("compute : {d} jobs, {d} on silicon, {d} in software ({d:.1}% hardware)\n", .{
            o.proof.jobs, o.proof.on_silicon, o.proof.in_software, o.proof.siliconShare() * 100,
        });
        std.debug.print("integrity: mesh result {s} local recomputation, {d} rows rejected\n", .{
            if (o.matches_local) "equals" else "DIFFERS FROM", o.proof.rows_rejected,
        });
        std.debug.print("weights : {s}\n\n", .{o.proof.provenance.label()});
    }

    line();
    try m.report(out);
    line();
    std.debug.print("Every number above is measured by this run. The action choices are\n", .{});
    std.debug.print("not meaningful until trained weights are loaded — the arithmetic is.\n", .{});
}

fn runAgent(gpa: std.mem.Allocator, task: []const u8, serial_path: ?[]const u8) !void {
    var pathbuf: [256]u8 = undefined;
    var m = try buildMesh(gpa, serial_path orelse default_serial, &pathbuf);
    defer m.deinit();

    const model = try model_mod.Model.synthetic(gpa, 3, 32, 0x1614);
    var agent = try agent_mod.Agent.init(gpa, "igla-coder", model);
    defer agent.deinit(gpa);

    const o = try agent.run(&m, task);
    std.debug.print("task     : {s}\n", .{task});
    std.debug.print("action   : {s}\n", .{o.decision.action.label()});
    std.debug.print("confident: {s}\n", .{if (o.decision.isConfident()) "yes" else "no"});
    std.debug.print("jobs     : {d} ({d} on silicon)\n", .{ o.proof.jobs, o.proof.on_silicon });
    std.debug.print("credit   : {d} mTRI issued, {d} mTRI slashed\n", .{ o.proof.credit_issued_mtri, o.proof.slashed_mtri });
    std.debug.print("weights  : {s}\n", .{o.proof.provenance.label()});
}

// ---------------------------------------------------------------------------

/// Expose a node over TCP. A developer with a board runs this; a coordinator
/// anywhere on the same overlay can then send it work.
fn serve(gpa: std.mem.Allocator, args: []const [:0]const u8) !void {
    _ = gpa;
    const port: u16 = if (args.len > 2) try std.fmt.parseInt(u16, args[2], 10) else 9701;
    const serial_path: ?[]const u8 = if (args.len > 3) args[3] else null;

    var backing: ?node_mod.Node = null;
    var pathbuf: [256]u8 = undefined;
    if (serial_path) |p| {
        const zpath = try std.fmt.bufPrintZ(&pathbuf, "{s}", .{p});
        backing = node_mod.Node.initFpga(protocol.default_node_id, "ax7203", zpath, default_baud) catch |e| blk: {
            std.debug.print("no board on {s} ({s}); serving in software\n", .{ p, @errorName(e) });
            break :blk null;
        };
    }
    defer if (backing) |*b| b.deinit();

    var software = node_mod.Node.initEmulated(protocol.default_node_id, "software", .honest);

    var l = try net.listen("0.0.0.0", port);
    defer l.close();
    std.debug.print("TRI-NET node listening on port {d} ({s})\n", .{
        port, if (backing != null) "backed by an FPGA" else "software only",
    });

    while (true) {
        var conn = l.accept() catch continue;
        defer conn.close();
        while (true) {
            var raw: [protocol.request_len]u8 = undefined;
            conn.readExact(&raw) catch break;
            if (raw[0] != protocol.magic_req[0] or raw[1] != protocol.magic_req[1]) continue;
            const job: protocol.Job = .{
                .op = raw[2],
                .nonce = raw[3..7].*,
                .w = raw[7..15].*,
                .x = raw[15..23].*,
            };
            const target = if (backing) |*b| b else &software;
            const receipt = target.execute(job) catch protocol.execute(job, target.id);
            conn.writeAll(&protocol.encodeResponse(receipt)) catch break;
        }
    }
}

fn joinHelp() !void {
    std.debug.print(
        \\Joining TRI-NET
        \\===============
        \\
        \\What you need
        \\  - A Xilinx 7-series board. The reference target is an ALINX AX7203
        \\    (XC7A200T). Anything openXC7 can target will work with a rebuild.
        \\  - A USB serial link to the board and a JTAG programmer.
        \\
        \\Steps
        \\  1. Build the node bitstream, or take the artifact from the
        \\     `AX7203 TRI-NET MAC32 Node` CI workflow.
        \\  2. Pick a node id and rebuild with -DNODE_ID so your node is
        \\     distinguishable. Two nodes sharing an id cannot both be credited.
        \\  3. Flash the board, then run `trinet probe <serial>`. You are a node
        \\     when it reports 64/64 receipts verified.
        \\  4. Run `trinet serve <port> <serial>` and put the machine on the
        \\     coordinator's overlay network.
        \\  5. Register with the coordinator: node id, owner handle, stake.
        \\
        \\What you earn
        \\  Verified ternary compute accrues TRI credit against your handle.
        \\  Credit is an internal work record, not a transferable token: it
        \\  measures contribution so contributors can be paid, and deliberately
        \\  stops short of issuing a financial instrument.
        \\
        \\What loses it
        \\  A receipt that does not verify is slashed against your stake. The
        \\  parameters are set so that a caught cheat costs far more than the
        \\  work it skipped. Run `trinet selftest` to see the adversaries lose.
        \\
    , .{});
}
