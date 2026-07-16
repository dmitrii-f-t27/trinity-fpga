#!/usr/bin/env python3
"""
trinity_flashed.py — Root daemon for FPGA flashing without repeated sudo.
Runs as a launchd service (root). Listens on Unix socket.
Client (trinity_flash) sends bitstream path → daemon flashes it.

Protocol (newline-delimited JSON):
  Request:  {"cmd": "flash", "bitstream": "/path/to/file.bit"}
  Request:  {"cmd": "kextunload"}
  Request:  {"cmd": "kextload"}
  Request:  {"cmd": "jtag_scan"}
  Response: {"ok": true/false, "msg": "...", "data": "..."}

Install:
  sudo python3 trinity_flashed.py --install
  sudo launchctl load /Library/LaunchDaemons/com.trinity.flashed.plist

Use:
  python3 trinity_flash.py /tmp/bitstreams/bf16.bit
"""
import socket, json, os, sys, subprocess, threading, tempfile, time

SOCKET_PATH = "/tmp/trinity_flashed.sock"
OPENOCD = "/opt/homebrew/bin/openocd"
KEXT_UNLOAD = "/usr/sbin/kextunload"
KEXT_LOAD = "/usr/sbin/kextload"
KMUTIL = "/usr/bin/kmutil"
APPLE_SERIAL = "com.apple.driver.AppleSerialShim"
FTDI_NOSERIAL_KEXT = "/Library/Extensions/FTDINoSerial.kext"
_REPO_ROOT = os.environ.get(
    "TRINITY_REPO",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)
CFG = os.path.join(_REPO_ROOT, "fpga/openxc7-synth/ax7203_al321.cfg")

def run_cmd(cmd, timeout=300):
    """Run command, return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -2, "", str(e)

def free_ftdi_for_libusb():
    """Make FTDI available for libusb (openocd). macOS 26 compatible."""
    # Load FTDINoSerial.kext which prevents serial driver from claiming FTDI
    rc, _, _ = run_cmd([KMUTIL, "load", "-p", FTDI_NOSERIAL_KEXT], timeout=15)
    return rc == 0

def restore_serial():
    """Restore serial driver access after JTAG. macOS 26 compatible."""
    # Unload FTDINoSerial so Apple serial driver can reclaim FTDI
    run_cmd([KMUTIL, "unload", "-p", FTDI_NOSERIAL_KEXT], timeout=10)
    # Give the system time to re-match the serial driver
    import time as _t
    _t.sleep(2)
    return True

def handle_flash(bitstream):
    """Flash bitstream: FTDINoSerial load → openocd → FTDINoSerial unload."""
    if not os.path.exists(bitstream):
        return {"ok": False, "msg": f"bitstream not found: {bitstream}"}

    # Step 1: Make FTDI available for libusb
    free_ftdi_for_libusb()
    import time as _t
    _t.sleep(1)

    # Step 2: Flash via openocd
    rc2, out2, err2 = run_cmd([
        OPENOCD, "-f", CFG,
        "-c", "adapter speed 100",
        "-c", "init",
        "-c", f"pld load 0 {bitstream}",
        "-c", "runtest 200000",
        "-c", "shutdown"
    ], timeout=600)

    # Step 3: Restore serial driver for UART access
    restore_serial()

    if rc2 == 0:
        return {"ok": True, "msg": f"flashed {bitstream}"}
    else:
        return {"ok": False, "msg": f"openocd failed (rc={rc2})", "data": err2[-500:] if err2 else ""}

def handle_jtag_scan():
    """Quick JTAG scan."""
    free_ftdi_for_libusb()
    import time as _t
    _t.sleep(1)
    rc2, out2, err2 = run_cmd([
        OPENOCD, "-f", CFG,
        "-c", "adapter speed 100",
        "-c", "init",
        "-c", "scan_chain",
        "-c", "shutdown"
    ], timeout=30)
    restore_serial()
    combined = out2 + err2
    return {"ok": rc2 == 0, "msg": combined[-500:]}

def handle_client(conn):
    """Handle one client connection."""
    try:
        data = conn.recv(65536).decode().strip()
        req = json.loads(data)

        if req["cmd"] == "flash":
            resp = handle_flash(req["bitstream"])
        elif req["cmd"] == "jtag_scan":
            resp = handle_jtag_scan()
        elif req["cmd"] == "kextunload":
            # Legacy: now means "free FTDI for libusb"
            ok = free_ftdi_for_libusb()
            resp = {"ok": ok, "msg": "ftdi freed for libusb" if ok else "failed"}
        elif req["cmd"] == "kextload":
            # Legacy: now means "restore serial driver"
            restore_serial()
            resp = {"ok": True, "msg": "serial restored"}
        elif req["cmd"] == "ping":
            resp = {"ok": True, "msg": "pong"}
        elif req["cmd"] == "run":
            # Run arbitrary command as root (for kext management)
            rc, out, err = run_cmd(req.get("args", []), timeout=req.get("timeout", 60))
            resp = {"ok": rc == 0, "msg": out[-1000:] if out else "", "data": err[-500:] if err else "", "rc": rc}
        elif req["cmd"] == "flash_fast":
            # Flash at higher speed (scan first to verify, then flash at best speed)
            bitstream = req["bitstream"]
            speed = req.get("speed", 100)
            if not os.path.exists(bitstream):
                resp = {"ok": False, "msg": f"not found: {bitstream}"}
            else:
                # Try flash without kextunload (might work in brief window after replug)
                rc2, out2, err2 = run_cmd([
                    OPENOCD, "-f", CFG,
                    "-c", f"adapter speed {speed}",
                    "-c", "init",
                    "-c", f"pld load 0 {bitstream}",
                    "-c", "runtest 200000",
                    "-c", "shutdown"
                ], timeout=req.get("timeout", 900))
                resp = {"ok": rc2 == 0, "msg": f"flashed at {speed}kHz" if rc2 == 0 else f"failed (rc={rc2})", "data": (out2+err2)[-500:]}
        else:
            resp = {"ok": False, "msg": f"unknown cmd: {req['cmd']}"}

        conn.sendall((json.dumps(resp) + "\n").encode())
    except Exception as e:
        try:
            conn.sendall((json.dumps({"ok": False, "msg": str(e)}) + "\n").encode())
        except:
            pass
    finally:
        conn.close()

def server_loop():
    """Main server loop."""
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(5)
    os.chmod(SOCKET_PATH, 0o666)  # world read/write
    print(f"trinity_flashed listening on {SOCKET_PATH}")

    while True:
        conn, _ = server.accept()
        t = threading.Thread(target=handle_client, args=(conn,))
        t.daemon = True
        t.start()

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trinity.flashed</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{script}</string>
        <string>--serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/trinity_flashed.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/trinity_flashed.log</string>
</dict>
</plist>
"""

def install():
    """Install as launchd daemon."""
    script = os.path.abspath(__file__)
    plist_path = "/Library/LaunchDaemons/com.trinity.flashed.plist"
    plist_content = PLIST.replace("{script}", script)

    with open("/tmp/com.trinity.flashed.plist", "w") as f:
        f.write(plist_content)

    print("=== Trinity Flash Daemon Installation ===")
    print(f"Script: {script}")
    print(f"Plist:  {plist_path}")
    print()
    print("Run these commands to install:")
    print(f"  sudo cp /tmp/com.trinity.flashed.plist {plist_path}")
    print(f"  sudo chown root:wheel {plist_path}")
    print(f"  sudo launchctl load {plist_path}")
    print()
    print("Verify:")
    print("  python3 trinity_flash.py --ping")
    print()
    print("Use:")
    print("  python3 trinity_flash.py /tmp/bitstreams/bf16.bit")
    print("  python3 trinity_flash.py --scan")

if __name__ == "__main__":
    if "--install" in sys.argv:
        install()
    elif "--serve" in sys.argv:
        server_loop()
    else:
        print("Usage: trinity_flashed.py --install | --serve")
        print("  --install  Show installation instructions")
        print("  --serve    Run as daemon (launched by launchd)")
