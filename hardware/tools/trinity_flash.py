#!/usr/bin/env python3
"""
trinity_flash.py — Client utility for FPGA flashing without sudo.
Requires trinity_flashed daemon (installed once with sudo).

Usage:
  python3 trinity_flash.py /tmp/bitstreams/bf16.bit    # Flash bitstream
  python3 trinity_flash.py --scan                       # JTAG scan
  python3 trinity_flash.py --ping                       # Check daemon
  python3 trinity_flash.py --unload                     # Unload serial kext
  python3 trinity_flash.py --load                       # Reload serial kext
"""
import socket, json, sys, os

SOCKET_PATH = "/tmp/trinity_flashed.sock"

def send_cmd(cmd, **kwargs):
    """Send command to flash daemon."""
    if not os.path.exists(SOCKET_PATH):
        print(f"ERROR: daemon not running ({SOCKET_PATH} not found)")
        print("Install: sudo python3 hardware/tools/trinity_flashed.py --install")
        sys.exit(1)

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(600)  # 10 min for large bitstreams
        s.connect(SOCKET_PATH)
        req = {"cmd": cmd, **kwargs}
        s.sendall((json.dumps(req) + "\n").encode())
        data = s.recv(65536).decode().strip()
        s.close()
        return json.loads(data)
    except socket.timeout:
        return {"ok": False, "msg": "timeout (bitstream too large? try slower speed)"}
    except ConnectionRefusedError:
        return {"ok": False, "msg": "daemon not running"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--ping":
        r = send_cmd("ping")
        print(f"{'OK' if r['ok'] else 'FAIL'}: {r['msg']}")
        sys.exit(0 if r['ok'] else 1)

    elif sys.argv[1] == "--scan":
        print("Scanning JTAG chain...")
        r = send_cmd("jtag_scan")
        if r['ok']:
            print("JTAG scan output:")
            print(r['msg'])
        else:
            print(f"FAIL: {r['msg']}")
        sys.exit(0 if r['ok'] else 1)

    elif sys.argv[1] == "--unload":
        r = send_cmd("kextunload")
        print(f"{'OK' if r['ok'] else 'FAIL'}: {r['msg']}")
        sys.exit(0 if r['ok'] else 1)

    elif sys.argv[1] == "--load":
        r = send_cmd("kextload")
        print(f"{'OK' if r['ok'] else 'FAIL'}: {r['msg']}")
        sys.exit(0 if r['ok'] else 1)

    else:
        bitstream = os.path.abspath(sys.argv[1])
        if not os.path.exists(bitstream):
            print(f"ERROR: {bitstream} not found")
            sys.exit(1)
        print(f"Flashing {bitstream}...")
        r = send_cmd("flash", bitstream=bitstream)
        if r['ok']:
            print(f"SUCCESS: {r['msg']}")
            sys.exit(0)
        else:
            print(f"FAIL: {r['msg']}")
            if 'data' in r and r['data']:
                print(f"  Detail: {r['data'][:200]}")
            sys.exit(1)

if __name__ == "__main__":
    main()
