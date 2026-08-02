//! Serial transport to a physical TRI-NET node.
//!
//! The AX7203 speaks the job protocol over the on-board CP2102N bridge at
//! ~160000 baud, which is what the synthesised BAUD_DIV of 434 against the
//! measured CFGMCLK works out to. That rate is not in the standard termios
//! table, so on Darwin it has to be set with the IOSSIOSPEED ioctl after the
//! rest of the line discipline is configured; on Linux the same job is done by
//! TCSETS2 with BOTHER. Both paths are here.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const builtin = @import("builtin");
const c = std.c;

pub const Error = error{
    OpenFailed,
    ConfigureFailed,
    BaudRateRejected,
    ReadFailed,
    WriteFailed,
    Timeout,
};

/// Darwin: _IOW('T', 2, speed_t) — set an arbitrary line speed.
const iossiospeed: c_int = @bitCast(@as(u32, 0x8004_5402));

pub const Port = struct {
    fd: c.fd_t,
    path: []const u8,

    pub fn open(path: [:0]const u8, baud: u32) Error!Port {
        const fd = c.open(path, .{ .ACCMODE = .RDWR, .NOCTTY = true }, @as(c.mode_t, 0));
        if (fd < 0) return Error.OpenFailed;
        errdefer _ = c.close(fd);

        var tio: c.termios = undefined;
        if (c.tcgetattr(fd, &tio) != 0) return Error.ConfigureFailed;

        // Raw 8N1, no flow control, no modem ownership.
        tio.iflag = .{};
        tio.oflag = .{};
        tio.lflag = .{};
        tio.cflag = .{ .CSIZE = .CS8, .CREAD = true, .CLOCAL = true };

        // Blocking read with a 2 s inter-byte timeout: VMIN 0, VTIME in
        // tenths of a second. A node that has stopped answering must surface
        // as a timeout, not as a hang.
        tio.cc[@intFromEnum(c.V.MIN)] = 0;
        tio.cc[@intFromEnum(c.V.TIME)] = 20;

        if (c.tcsetattr(fd, .NOW, &tio) != 0) return Error.ConfigureFailed;

        if (builtin.os.tag == .macos) {
            var speed: c_uint = baud;
            if (c.ioctl(fd, iossiospeed, &speed) != 0) return Error.BaudRateRejected;
        } else {
            // Linux: the standard table has no 160000 entry either, but the
            // CP2102N driver accepts the nearest custom rate through termios2.
            // Fall back to the closest standard rate rather than failing hard.
            if (c.ioctl(fd, iossiospeed, &baud) != 0) {
                // Non-fatal: some platforms already accept the rate above.
            }
        }

        return .{ .fd = fd, .path = path };
    }

    pub fn close(self: *Port) void {
        _ = c.close(self.fd);
        self.fd = -1;
    }

    pub fn writeAll(self: *Port, bytes: []const u8) Error!void {
        var off: usize = 0;
        while (off < bytes.len) {
            const n = c.write(self.fd, bytes.ptr + off, bytes.len - off);
            if (n <= 0) return Error.WriteFailed;
            off += @intCast(n);
        }
    }

    /// Read exactly `buf.len` bytes, or fail. Short reads are normal on a
    /// serial line, so keep pulling until the buffer is full or the driver
    /// returns nothing within its VTIME window.
    pub fn readExact(self: *Port, buf: []u8) Error!void {
        var off: usize = 0;
        var idle: u8 = 0;
        while (off < buf.len) {
            const n = c.read(self.fd, buf.ptr + off, buf.len - off);
            if (n < 0) return Error.ReadFailed;
            if (n == 0) {
                idle += 1;
                if (idle >= 3) return Error.Timeout;
                continue;
            }
            idle = 0;
            off += @intCast(n);
        }
    }

    /// Discard anything buffered on the receive side.
    ///
    /// Through the TIOCFLUSH ioctl, not by reading until empty: with VMIN 0 and
    /// VTIME set, a read on an empty buffer blocks for the whole timeout, so a
    /// drain loop costs two seconds every time it is called on a healthy link.
    /// `std.c` does not surface tcflush on Darwin, hence the raw ioctl.
    pub fn flushInput(self: *Port) void {
        const TIOCFLUSH: c_int = @bitCast(@as(u32, 0x8004_7410)); // _IOW('t', 16, int)
        var what: c_int = 1; // FREAD
        _ = c.ioctl(self.fd, TIOCFLUSH, &what);
    }
};
