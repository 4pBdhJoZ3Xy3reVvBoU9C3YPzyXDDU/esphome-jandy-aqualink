"""Read-only live capture + decode from the Atom RS-485 TCP bridge.

Connects to the M5Stack ESPHome stream-server, feeds the raw byte stream
through PoolDecoder, and prints decoded state, the (dest, cmd) message types
seen, and checksum health. It NEVER writes to the socket, so it is safe to run
alongside other readers and carries zero bus risk.

Usage:
    python capture.py [--host H] [--port P] [--seconds N] [--raw]
"""

import argparse
import socket
import time

from jandy.decoder import PoolDecoder


def kind(dest: int, cmd: int) -> str:
    if cmd == 0x00:
        return "poll"
    if cmd == 0x01:
        return "ack"
    if cmd == 0x25:
        return "display-text"
    return "status/other"


def report(dec: PoolDecoder, full: bool = False) -> None:
    s = dec.stats
    bad_pct = (100.0 * s["bad_checksum"] / s["frames"]) if s["frames"] else 0.0
    print(
        f"[{s['bytes']:>6} B] frames={s['frames']:>4} "
        f"bad_cksum={s['bad_checksum']} ({bad_pct:.1f}%)  state={dec.state}",
        flush=True,
    )
    if full:
        print("\n  message types seen (dest cmd  count  kind):")
        for (dest, cmd), n in sorted(dec.message_counts.items()):
            print(f"    0x{dest:02X} 0x{cmd:02X}  {n:>4}  {kind(dest, cmd)}")
        print("\n  last raw frame per type (for protocol discovery):")
        for (dest, cmd), frame in sorted(dec.last_frame_by_type.items()):
            print(f"    0x{dest:02X} 0x{cmd:02X}  {frame.raw.hex(' ')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="192.168.4.51")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--raw", action="store_true", help="dump each raw frame as it arrives")
    args = ap.parse_args()

    dec = PoolDecoder()
    print(f"connecting to {args.host}:{args.port} (read-only) ...", flush=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    try:
        sock.connect((args.host, args.port))
    except Exception as exc:
        print(f"CONNECT FAILED: {type(exc).__name__}: {exc}")
        return 1
    print(f"connected; capturing for {args.seconds:.0f}s\n", flush=True)

    sock.settimeout(1.0)
    deadline = time.monotonic() + args.seconds
    last_report = time.monotonic()
    try:
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                print("stream closed by peer")
                break
            frames = dec.feed(chunk)
            if args.raw:
                for frame in frames:
                    flag = "" if frame.checksum_valid() else "   <BAD CKSUM>"
                    print(f"  {frame.raw.hex(' ')}{flag}", flush=True)
            now = time.monotonic()
            if now - last_report >= 5.0:
                last_report = now
                report(dec)
    finally:
        sock.close()

    print("\n=== final ===")
    report(dec, full=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
