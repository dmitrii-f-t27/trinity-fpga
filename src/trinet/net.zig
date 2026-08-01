//! Minimal TCP transport for TRI-NET, written straight onto libc sockets.
//!
//! This is deliberately small. A node that lives on someone else's desk is
//! reached the same way as a local one: a stream that carries the same 24-byte
//! request and 15-byte response the FPGA speaks over UART. Keeping the framing
//! identical across transports is what lets a developer attach a board and
//! join the network without any protocol negotiation.
//!
//! NAT traversal is intentionally NOT solved here. A node behind a home router
//! is expected to sit on an overlay (headscale/Tailscale, Nebula or WireGuard)
//! and present a routable address to the coordinator. Re-implementing hole
//! punching would be the wrong thing to own.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const c = std.c;

pub const Error = error{
    SocketFailed,
    BindFailed,
    ListenFailed,
    AcceptFailed,
    ConnectFailed,
    BadAddress,
    ReadFailed,
    WriteFailed,
    Closed,
};

const builtin = @import("builtin");
const is_bsd = builtin.os.tag.isDarwin();

const AF_INET: c_int = 2;
const SOCK_STREAM: c_int = 1;
// SOL_SOCKET and SO_REUSEADDR are not the same numbers on BSD and Linux.
const SOL_SOCKET: c_int = if (is_bsd) 0xffff else 1;
const SO_REUSEADDR: c_int = if (is_bsd) 0x0004 else 2;

/// BSD carries a leading length byte where Linux widens the family field.
const sockaddr_in = if (is_bsd) extern struct {
    len: u8 = 16,
    family: u8 = @intCast(AF_INET),
    port: u16, // network byte order
    addr: [4]u8, // network byte order, kept as bytes so no swap can go wrong
    zero: [8]u8 = @splat(0),
} else extern struct {
    family: u16 = @intCast(AF_INET),
    port: u16,
    addr: [4]u8,
    zero: [8]u8 = @splat(0),
};

fn makeAddr(ip: []const u8, port: u16) Error!sockaddr_in {
    var octets: [4]u8 = undefined;
    var it = std.mem.splitScalar(u8, ip, '.');
    var i: usize = 0;
    while (it.next()) |part| : (i += 1) {
        if (i >= 4) return Error.BadAddress;
        octets[i] = std.fmt.parseInt(u8, part, 10) catch return Error.BadAddress;
    }
    if (i != 4) return Error.BadAddress;
    return .{
        .port = std.mem.nativeToBig(u16, port),
        .addr = octets,
    };
}

pub const Stream = struct {
    fd: c.fd_t,

    pub fn close(self: *Stream) void {
        if (self.fd >= 0) _ = c.close(self.fd);
        self.fd = -1;
    }

    pub fn writeAll(self: *Stream, bytes: []const u8) Error!void {
        var off: usize = 0;
        while (off < bytes.len) {
            const n = c.write(self.fd, bytes.ptr + off, bytes.len - off);
            if (n <= 0) return Error.WriteFailed;
            off += @intCast(n);
        }
    }

    pub fn readExact(self: *Stream, buf: []u8) Error!void {
        var off: usize = 0;
        while (off < buf.len) {
            const n = c.read(self.fd, buf.ptr + off, buf.len - off);
            if (n < 0) return Error.ReadFailed;
            if (n == 0) return Error.Closed;
            off += @intCast(n);
        }
    }
};

pub fn connect(ip: []const u8, port: u16) Error!Stream {
    const addr = try makeAddr(ip, port);
    const fd = c.socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return Error.SocketFailed;
    errdefer _ = c.close(fd);
    if (c.connect(fd, @ptrCast(&addr), @sizeOf(sockaddr_in)) != 0) return Error.ConnectFailed;
    return .{ .fd = fd };
}

pub const Listener = struct {
    fd: c.fd_t,

    pub fn close(self: *Listener) void {
        if (self.fd >= 0) _ = c.close(self.fd);
        self.fd = -1;
    }

    pub fn accept(self: *Listener) Error!Stream {
        const fd = c.accept(self.fd, null, null);
        if (fd < 0) return Error.AcceptFailed;
        return .{ .fd = fd };
    }
};

pub fn listen(ip: []const u8, port: u16) Error!Listener {
    const addr = try makeAddr(ip, port);
    const fd = c.socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return Error.SocketFailed;
    errdefer _ = c.close(fd);

    var one: c_int = 1;
    _ = c.setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, @ptrCast(&one), @sizeOf(c_int));

    if (c.bind(fd, @ptrCast(&addr), @sizeOf(sockaddr_in)) != 0) return Error.BindFailed;
    if (c.listen(fd, 16) != 0) return Error.ListenFailed;
    return .{ .fd = fd };
}

test "address parsing rejects malformed input" {
    try std.testing.expectError(Error.BadAddress, makeAddr("1.2.3", 80));
    try std.testing.expectError(Error.BadAddress, makeAddr("1.2.3.4.5", 80));
    try std.testing.expectError(Error.BadAddress, makeAddr("1.2.3.999", 80));
    const a = try makeAddr("127.0.0.1", 9701);
    try std.testing.expectEqual(std.mem.nativeToBig(u16, 9701), a.port);
}

test "loopback round trip carries an exact frame" {
    var l = try listen("127.0.0.1", 0);
    defer l.close();

    // Discover the bound port.
    var bound: sockaddr_in = undefined;
    var len: c.socklen_t = @sizeOf(sockaddr_in);
    try std.testing.expect(c.getsockname(l.fd, @ptrCast(&bound), &len) == 0);
    const port = std.mem.bigToNative(u16, bound.port);

    const T = struct {
        fn client(p: u16) !void {
            var s = try connect("127.0.0.1", p);
            defer s.close();
            try s.writeAll("trinet-frame");
        }
    };
    const th = try std.Thread.spawn(.{}, T.client, .{port});
    defer th.join();

    var conn = try l.accept();
    defer conn.close();
    var buf: [12]u8 = undefined;
    try conn.readExact(&buf);
    try std.testing.expectEqualStrings("trinet-frame", &buf);
}
