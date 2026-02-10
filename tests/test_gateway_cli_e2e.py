from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

import httpx


def _pick_free_port() -> int:
    # Best-effort: avoids relying on subprocess stdout timing to discover an ephemeral port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class _Spawned:
    pid: int

    def poll(self) -> int | None:
        try:
            waited, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            return 0
        if waited == 0:
            return None
        if os.WIFEXITED(status):
            return int(os.WEXITSTATUS(status))
        if os.WIFSIGNALED(status):
            return 128 + int(os.WTERMSIG(status))
        return 1

    def send_signal(self, sig: int) -> None:
        os.kill(self.pid, sig)

    def terminate(self) -> None:
        self.send_signal(signal.SIGTERM)

    def wait(self, timeout: float) -> int:
        start = time.time()
        while time.time() - start < timeout:
            rc = self.poll()
            if rc is not None:
                return rc
            time.sleep(0.05)
        raise TimeoutError

    def kill(self) -> None:
        self.send_signal(signal.SIGKILL)


def _start_gateway(*args: str) -> tuple[object, int, str]:
    port = _pick_free_port()
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "cascadeflow.server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        *args,
    ]
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    # Make localhost reachable even if the runner sets HTTP(S)_PROXY.
    env.setdefault("NO_PROXY", "127.0.0.1,localhost")
    env.setdefault("no_proxy", "127.0.0.1,localhost")
    fd, port_file = tempfile.mkstemp(prefix="cascadeflow-gateway-port-", suffix=".txt")
    os.close(fd)
    env["CASCADEFLOW_GATEWAY_PORT_FILE"] = port_file
    # macOS GitHub runners can deadlock when forking a Python process after native
    # deps have initialized threads (e.g. onnxruntime). Using posix_spawn avoids fork.
    if sys.platform == "darwin" and hasattr(os, "posix_spawn"):
        pid = os.posix_spawn(sys.executable, cmd, env)  # type: ignore[attr-defined]
        proc: object = _Spawned(pid=pid)
    else:
        proc = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=False,
            env=env,
        )

    start = time.time()
    while time.time() - start < 30:
        # Prefer probing readiness instead of parsing stdout/port files (CI/macOS can be flaky).
        try:
            health = httpx.get(
                f"http://127.0.0.1:{port}/health", timeout=0.5, trust_env=False
            )
            if health.status_code == 200:
                return proc, port, port_file
        except Exception:
            pass

        # If the child exited, fail early.
        poll = getattr(proc, "poll", None)
        if callable(poll) and poll() is not None:
            break
        time.sleep(0.1)

    try:
        term = getattr(proc, "terminate", None)
        if callable(term):
            term()
    except Exception:
        pass

    try:
        port_file_contents = open(port_file, encoding="utf-8").read()
    except Exception as exc:
        port_file_contents = f"<unreadable: {exc}>"

    rc = None
    try:
        poll = getattr(proc, "poll", None)
        if callable(poll):
            rc = poll()
    except Exception:
        rc = None

    raise AssertionError(
        "Gateway did not become ready (GET /health did not return 200). "
        f"returncode={rc} port={port} port_file={port_file} port_file_contents={port_file_contents!r}"
    )


def _stop_gateway(proc: object) -> None:
    poll = getattr(proc, "poll", None)
    if callable(poll) and poll() is not None:
        return

    try:
        if sys.platform != "win32":
            send = getattr(proc, "send_signal", None)
            if callable(send):
                send(signal.SIGINT)
        else:
            term = getattr(proc, "terminate", None)
            if callable(term):
                term()
    except Exception:
        pass

    try:
        wait = getattr(proc, "wait", None)
        if callable(wait):
            # subprocess.Popen.wait uses `timeout=...`, our _Spawned.wait does not.
            try:
                wait(timeout=3)  # type: ignore[misc]
                return
            except TypeError:
                wait(3)  # type: ignore[misc]
                return
        return
    except Exception:
        pass

    try:
        kill = getattr(proc, "kill", None)
        if callable(kill):
            kill()
    except Exception:
        pass


def test_gateway_cli_mock_e2e_with_metadata():
    proc, port, port_file = _start_gateway(
        "--mode",
        "mock",
        "--include-gateway-metadata",
        "--cors-allow-origin",
        "https://example.com",
        "--token-cost",
        "0",
        "--advertise-model",
        "gpt-4o-mini",
        "--virtual-model",
        "cascadeflow-auto=test-virtual",
    )
    try:
        base = f"http://127.0.0.1:{port}"

        health = httpx.get(f"{base}/health", timeout=5.0, trust_env=False)
        assert health.status_code == 200
        assert health.headers.get("X-Cascadeflow-Gateway") == "cascadeflow"
        assert health.headers.get("X-Cascadeflow-Gateway-Mode") == "mock"
        assert health.headers.get("Access-Control-Allow-Origin") == "https://example.com"

        models = httpx.get(f"{base}/v1/models", timeout=5.0, trust_env=False)
        assert models.status_code == 200
        assert models.headers.get("X-Cascadeflow-Gateway-Endpoint") == "models.list"
        model_ids = {
            item.get("id") for item in models.json().get("data", []) if isinstance(item, dict)
        }
        assert "gpt-4o-mini" in model_ids

        chat = httpx.post(
            f"{base}/v1/chat/completions",
            json={"model": "cascadeflow-auto", "messages": [{"role": "user", "content": "Hello"}]},
            timeout=5.0,
            trust_env=False,
        )
        assert chat.status_code == 200
        assert chat.headers.get("X-Cascadeflow-Gateway-API") == "openai"
        payload = chat.json()
        assert payload["model"] == "test-virtual"
        assert payload["choices"][0]["message"]["content"]
        assert payload["cascadeflow"]["cost"] == 0.0
        assert payload["cascadeflow"]["gateway"]["endpoint"] == "chat.completions"

        anth = httpx.post(
            f"{base}/v1/messages",
            json={"model": "cascadeflow-fast", "messages": [{"role": "user", "content": "Hello"}]},
            timeout=5.0,
            trust_env=False,
        )
        assert anth.status_code == 200
        assert anth.headers.get("X-Cascadeflow-Gateway-API") == "anthropic"

        embed = httpx.post(
            f"{base}/v1/embeddings",
            json={"model": "cascadeflow", "input": ["hello", "world"]},
            timeout=10.0,
            trust_env=False,
        )
        assert embed.status_code == 200
        data = embed.json()
        assert len(data["data"]) == 2
        assert len(data["data"][0]["embedding"]) == 384
    finally:
        _stop_gateway(proc)
        try:
            os.unlink(port_file)
        except Exception:
            pass


def test_gateway_cli_mock_e2e_without_headers_or_cors():
    proc, port, port_file = _start_gateway(
        "--mode",
        "mock",
        "--no-gateway-headers",
        "--disable-cors",
    )
    try:
        base = f"http://127.0.0.1:{port}"

        health = httpx.get(f"{base}/health", timeout=5.0, trust_env=False)
        assert health.status_code == 200
        assert health.headers.get("X-Cascadeflow-Gateway") is None
        assert health.headers.get("Access-Control-Allow-Origin") is None

        chat = httpx.post(
            f"{base}/v1/chat/completions",
            json={"model": "cascadeflow", "messages": [{"role": "user", "content": "Hello"}]},
            timeout=5.0,
            trust_env=False,
        )
        assert chat.status_code == 200
    finally:
        _stop_gateway(proc)
        try:
            os.unlink(port_file)
        except Exception:
            pass
