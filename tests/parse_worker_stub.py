"""A misbehaving parse worker for tests/test_parse_limits.py.

Run exactly like app.utils.parse_worker (`python -m tests.parse_worker_stub <mode> <cpu> <mem>`),
so the tests cross the real process boundary. Each mode is one way a hostile file, a compromised
parser or an overloaded machine could make the real worker behave.
"""

import json
import os
import signal
import sys
import tempfile
import time

from app.utils.parse_worker import emit_ok, emit_refused, limit_resources


def raw(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def main() -> None:  # one branch per misbehavior
    mode, cpu_seconds, memory_bytes = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    limit_resources(cpu_seconds, memory_bytes, allow_fork=mode == "grandchild-unlimited")
    if mode == "reply-without-reading":  # answers and exits while the server is still writing
        emit_refused("no_text")
        os._exit(0)
    sys.stdin.buffer.read()
    if mode == "sleep":
        time.sleep(60)
    elif mode == "burn":
        while True:  # pure CPU: only the CPU limit can stop this quickly
            pass
    elif mode == "die":
        os.kill(os.getpid(), signal.SIGKILL)
    elif mode == "big":
        emit_ok("x" * 5_000_000, 1)
    elif mode == "flood":  # announces a huge reply, then never stops: only the byte cap ends it
        raw(json.dumps({"status": "ok", "pages": 1, "length": 10**12}).encode() + b"\n")
        while True:
            raw(b"y" * 65536)
    elif mode == "garbage":
        raw(b"not a header\n...")
    elif mode == "unknown-code":
        emit_refused("<script>alert(1)</script>")
    elif mode == "no-text":
        emit_refused("no_text")
    elif mode == "reason-list":
        raw(json.dumps({"status": "refused", "reason": [], "length": 0}).encode() + b"\n")
    elif mode == "deep-json":
        raw(b"[" * 200_000 + b"\n")
    elif mode == "pages-bool":
        raw(json.dumps({"status": "ok", "pages": True, "length": 2}).encode() + b"\nok")
    elif mode == "truncated":
        raw(json.dumps({"status": "ok", "pages": 1, "length": 100}).encode() + b"\nonly ten b")
        os._exit(0)
    elif mode == "slow-exit":
        emit_ok("complete reply", 1)
        time.sleep(30)  # e.g. a slow interpreter shutdown: the reply is already complete
    elif mode == "surrogate":
        emit_ok("bad \ud800 char", None)
    elif mode == "env":
        leaked = [k for k in os.environ if k in {"SECRET_KEY", "DATABASE_URL"}]
        report = "LEAK " + ",".join(leaked) if leaked else json.dumps(sorted(os.environ))
        emit_ok(report, None)
    elif mode == "big-header":  # a valid reply whose header is far larger than any real one
        body = b"ok"
        header = {"status": "ok", "pages": 1, "pad": "x" * 10_000, "length": len(body)}
        raw(json.dumps(header).encode() + b"\n" + body)
    elif mode == "sys-path":
        emit_ok(json.dumps(sys.path), None)
    elif mode == "cwd":
        emit_ok(os.getcwd(), None)
    elif mode == "write-file":
        try:
            target = os.path.join(tempfile.gettempdir(), f"parse-worker-{os.getpid()}.txt")
            with open(target, "w") as f:
                f.write("escaped")
                f.flush()
            emit_ok("written", None)
        except OSError:
            emit_ok("blocked", None)
    elif mode == "fork":
        try:
            pid = os.fork()
        except OSError:
            emit_ok("blocked", None)
            return
        if pid == 0:
            os._exit(0)
        emit_ok("forked", None)
    elif mode == "grandchild-unlimited":
        pid = os.fork()
        if pid == 0:  # grandchild: keeps running (and holds stdout) after the worker exits
            time.sleep(60)
            os._exit(0)
        emit_ok(str(pid), None)
        os._exit(0)
    elif mode == "oom":
        try:
            with open("/proc/self/oom_score_adj") as f:
                emit_ok(f.read().strip(), None)
        except OSError:
            emit_ok("unsupported", None)


if __name__ == "__main__":
    main()
