#!/usr/bin/env python3
"""TCP_REPAIR tests."""

import argparse
import filecmp
import json
import os
from pathlib import Path
import random
import select
import signal
import subprocess
import sys
import time

namespaces = {}
processes = []
tests = []
interfaces = {}


def run_command(prog, *options, check=True, timeout=10):
    return subprocess.run([prog, *options], capture_output=True, text=True,
                          check=check, timeout=timeout)


def ns_command(ns, prog, *options):
    return ["nsenter", f"--net=/proc/{namespaces[ns].pid}/ns/net", "--", prog, *options]


def ns_create(ns):
    holder = subprocess.Popen(
        ["unshare", "--net", sys.executable, "-c",
         "import sys; print('ready', flush=True); sys.stdin.read()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    namespaces[ns] = holder
    if holder.stdout.readline() != b"ready\n":
        raise RuntimeError(holder.stderr.read().decode())


def ns_remove(ns):
    holder = namespaces.pop(ns)
    holder.stdin.close()
    try:
        holder.wait(timeout=2)
    except subprocess.TimeoutExpired:
        holder.kill()
        holder.wait()


def ns_run(ns, prog, *options, timeout=10, check=True):
    return subprocess.run(ns_command(ns, prog, *options), capture_output=True,
                          text=True, timeout=timeout, check=check)


def setup_network(ns1, ns2, veth0=None, veth1=None):
    ns_create(ns1)
    ns_create(ns2)
    suffix = str(os.getpid())
    veth0 = veth0 or "veth_a"
    veth1 = veth1 or "veth_b"
    run_command("ip", "link", "add", veth0, "type", "veth", "peer", "name", veth1)
    for ns, dev, addr in ((ns1, veth0, "192.0.2.1/24"),
                          (ns2, veth1, "192.0.2.2/24")):
        run_command("ip", "link", "set", dev, "netns", str(namespaces[ns].pid))
        ns_run(ns, "ip", "link", "set", "lo", "up")
        ns_run(ns, "ip", "addr", "add", addr, "dev", dev)
        ns_run(ns, "ip", "link", "set", dev, "up")
        interfaces[ns] = dev


def display_network(ns1, ns2):
    for ns in (ns1, ns2):
        print(f"{ns}:\n{ns_run(ns, 'ip', '-br', 'addr').stdout}", end="", flush=True)


def clean_network(ns1, ns2):
    for ns in (ns1, ns2):
        if ns in namespaces:
            ns_remove(ns)
        interfaces.pop(ns, None)


def tc_set(ns, interface, /, latency=None, loss=None, rate=None,
           reorder_ratio=None, reorder_gap=None, jitter=0):
    options = []
    if latency or jitter or reorder_ratio:
        options += ["delay", f"{latency or 0}ms"]
        if jitter:
            options += [f"{jitter}ms"]
    if loss:
        options += ["loss", "random", f"{loss}%"]
    if rate:
        options += ["rate", rate]
    if reorder_ratio:
        options += ["reorder", f"{reorder_ratio}%"]
        if reorder_gap:
            options += ["gap", str(reorder_gap)]
    if options:
        print(f"{ns}/{interface}: netem {' '.join(options)}", flush=True)
        return ns_run(ns, "tc", "qdisc", "replace", "dev", interface,
                      "root", "netem", *options)


def tc_clean(ns, interface):
    return ns_run(ns, "tc", "qdisc", "del", "dev", interface, "root", check=False)


def tc_clean_all():
    for ns, dev in interfaces.items():
        tc_clean(ns, dev)


def compare_files(a, b):
    return filecmp.cmp(a, b, shallow=False)


def create_random_file(file, size):
    with open(file, "wb") as stream:
        while size > 0:
            chunk = os.urandom(min(size, 4096))
            stream.write(chunk)
            size -= len(chunk)


def it(name, fn):
    tests.append((name, fn))


def run_cleanup():
    for proc in reversed(processes):
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        if proc.stderr:
            error = proc.stderr.read().decode(errors="replace")
            if error:
                print(error, file=sys.stderr, end="")
    processes.clear()
    clean_network("A", "B")


def signal_cleanup(signum, frame):
    raise KeyboardInterrupt


def select_endpoint(ns):
    links = json.loads(ns_run(ns, "ip", "-j", "addr", "show").stdout)
    for link in links:
        if link["ifname"] == "lo" or "UP" not in link["flags"]:
            continue
        for addr in link["addr_info"]:
            if addr["family"] == "inet":
                ip = addr["local"]
                result = ns_run(ns, sys.executable, "-c",
                    "import socket,sys; s=socket.socket(); "
                    "s.bind((sys.argv[1],0)); print(s.getsockname()[1])", ip)
                return link["ifname"], ip, int(result.stdout)
    raise RuntimeError(f"{ns}: no active IPv4 interface")


def transfer(sender, receiver, data, timeout):
    sent = 0
    received = bytearray()
    started = time.monotonic()
    while len(received) < len(data):
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise RuntimeError(f"timeout: sent {sent}, received {len(received)}/{len(data)} bytes")
        readers, writers, _ = select.select(
            [receiver.stdout], [sender.stdin] if sent < len(data) else [], [], remaining)
        if writers:
            try:
                sent += os.write(sender.stdin.fileno(), data[sent:sent + 4096])
            except BrokenPipeError:
                raise RuntimeError("sender exited or closed stdin") from None
        if readers:
            chunk = os.read(receiver.stdout.fileno(), 4096)
            if not chunk:
                raise RuntimeError(f"peer EOF after {len(received)}/{len(data)} bytes")
            received.extend(chunk)
    if received != data:
        raise RuntimeError("received data differs")
    elapsed = time.monotonic() - started
    print(f"  {len(data)} bytes, {elapsed:.3f}s, {len(data) / elapsed / 1024:.2f} KiB/s", flush=True)


def run_tcpdump(path, ns, interface):
    proc = subprocess.Popen(ns_command(ns, "tcpdump", "-n", "-U", "-i", interface,
                                      "-w", str(Path(path).absolute())), stderr=subprocess.PIPE)
    processes.append(proc)
    time.sleep(0.2)
    if proc.poll() is not None:
        raise RuntimeError("tcpdump failed to start")


def run_tests(args):
    rng = random.Random(args.seed)
    seq_a, seq_b = rng.randrange(2**32), rng.randrange(2**32)
    if args.a_seq is not None:
        seq_a = args.a_seq
    if args.b_seq is not None:
        seq_b = args.b_seq
    recv_a = (seq_b + args.a_offset) % 2**32
    recv_b = (seq_a + args.b_offset) % 2**32
    try:
        setup_network("A", "B")
        dev_a, ip_a, port_a = select_endpoint("A")
        dev_b, ip_b, port_b = select_endpoint("B")
        for ns, dev in (("A", dev_a), ("B", dev_b)):
            tc_set(ns, dev, latency=args.delay, jitter=args.jitter,
                   loss=args.loss, rate=args.rate,
                   reorder_ratio=args.reorder, reorder_gap=args.reorder_gap)
        print(f"A: {dev_a} {ip_a}:{port_a}, send_seq={seq_a}, recv_seq={recv_a} (offset {args.a_offset:+d})", flush=True)
        print(f"B: {dev_b} {ip_b}:{port_b}, send_seq={seq_b}, recv_seq={recv_b} (offset {args.b_offset:+d})", flush=True)
        if args.dump:
            run_tcpdump(args.dump, "A", dev_a)

        peers = []
        for ns, local, local_port, peer, peer_port, send_seq, recv_seq in (
            ("A", ip_a, port_a, ip_b, port_b, seq_a, recv_a),
            ("B", ip_b, port_b, ip_a, port_a, seq_b, recv_b),
        ):
            proc = subprocess.Popen(ns_command(ns, args.exe_path, local, str(local_port),
                peer, str(peer_port), str(send_seq), str(recv_seq)),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append(proc)
            peers.append(proc)
            os.set_blocking(proc.stdin.fileno(), False)
            os.set_blocking(proc.stdout.fileno(), False)

        deadline = time.monotonic() + 3
        while True:
            errors = []
            for name, proc in zip(("A", "B"), peers):
                code = proc.poll()
                if code is not None:
                    error = proc.stderr.read().decode(errors="replace").strip()
                    errors.append(f"talker {name} exited during setup (exit code {code})\n{error}")
            if errors:
                raise RuntimeError("\n".join(errors))
            if all(f":{port}" in ns_run(ns, "ss", "-Htn", "state", "established").stdout
                   for ns, port in (("A", port_a), ("B", port_b))):
                break
            if time.monotonic() > deadline:
                raise RuntimeError("connection setup timeout")
            time.sleep(0.05)

        left, right = peers
        data = rng.randbytes(args.size)
        it("A -> B", lambda: transfer(left, right, data, args.timeout))
        it("B -> A", lambda: transfer(right, left, data, args.timeout))
        failed = 0
        for name, fn in tests:
            print(f"Testing {name}", flush=True)
            try:
                fn()
                print("  PASS", flush=True)
            except RuntimeError as error:
                failed += 1
                print(f"  FAIL: {error}", flush=True)
        if failed:
            for ns in ("A", "B"):
                print(f"{ns} TCP state:\n{ns_run(ns, 'ss', '-tin').stdout}", flush=True)
        else:
            left.stdin.close()
            for proc in peers:
                if proc.wait(timeout=args.timeout) != 0:
                    raise RuntimeError("talker failed on EOF")
            print("PASS: EOF shutdown", flush=True)
        print(f"Result: {len(tests) - failed} passed, {failed} failed", flush=True)
        return int(failed != 0)
    finally:
        run_cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe_path", nargs="?", default="./build/talker")
    parser.add_argument("--a-offset", type=int, default=0,
                        help="A recv_seq - B send_seq (default: 0)")
    parser.add_argument("--b-offset", type=int, default=0,
                        help="B recv_seq - A send_seq (default: 0)")
    parser.add_argument("--seed", type=int, help="Reproduce initial sequences and payload")
    parser.add_argument("--a-seq", type=int, help="Override A send_seq")
    parser.add_argument("--b-seq", type=int, help="Override B send_seq")
    parser.add_argument("--delay", type=float, default=0, help="Delay in ms per direction (RTT adds twice this)")
    parser.add_argument("--jitter", type=float, default=0, help="Delay jitter in ms per direction")
    parser.add_argument("--loss", type=float, default=0, help="Packet loss percentage per direction")
    parser.add_argument("--rate", help="Rate per direction, e.g. 10mbit")
    parser.add_argument("--reorder", type=float, default=0,
                        help="Netem reorder percentage per direction (requires --delay > 0)")
    parser.add_argument("--reorder-gap", type=int,
                        help="Minimum packet gap before reordering (positive integer; requires --reorder > 0)")
    parser.add_argument("--size", type=int, default=1024, help="Bytes per direction (default: 1024)")
    parser.add_argument("--timeout", type=float, default=60, help="Timeout per transfer/EOF in seconds (default: 60)")
    parser.add_argument("--dump", nargs="?", const="dump.pcap", help="Capture packets at A")
    parser.add_argument("--in-netns", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if any(seq is not None and not 0 <= seq < 2**32 for seq in (args.a_seq, args.b_seq)):
        parser.error("a-seq/b-seq must be between 0 and 2^32")
    if args.size <= 0 or args.timeout <= 0 or args.delay < 0 or args.jitter < 0 or not 0 <= args.loss <= 100:
        parser.error("size/timeout must be positive, delay/jitter nonnegative, loss between 0 and 100")
    if not 0 <= args.reorder <= 100:
        parser.error("reorder must be between 0 and 100")
    if args.reorder > 0 and not args.delay > 0:
        parser.error("reorder requires --delay > 0")
    if args.reorder_gap is not None and (args.reorder_gap <= 0 or args.reorder == 0):
        parser.error("reorder-gap must be positive and requires --reorder > 0")
    args.exe_path = str(Path(args.exe_path).absolute())
    if not os.access(args.exe_path, os.X_OK):
        parser.error(f"executable not found or not executable: {args.exe_path}")
    if not args.in_netns:
        # Try userns.
        return subprocess.call(["unshare", "--user", "--map-root-user", "--net",
            sys.executable, str(Path(__file__).absolute()), *sys.argv[1:], "--in-netns"])
    signal.signal(signal.SIGTERM, signal_cleanup)
    signal.signal(signal.SIGINT, signal_cleanup)
    try:
        return run_tests(args)
    except (RuntimeError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr, end="")
        return 1

if __name__ == "__main__":
    sys.exit(main())
