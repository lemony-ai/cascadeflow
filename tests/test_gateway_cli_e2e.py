import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time

import httpx


def _start_gateway(*args: str) -> tuple[subprocess.Popen, int]:
    cmd = [sys.executable, "-u", "-m", "cascadeflow.server", *args]
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    assert proc.stdout is not None
    q: queue.Queue[str] = queue.Queue()

    def _reader() -> None:
        try:
            for line in proc.stdout:
                q.put(line.rstrip("\n"))
        except Exception:
            return

    threading.Thread(target=_reader, daemon=True).start()

    port: int | None = None
    start = time.time()
    pattern = re.compile(r"running at http://127\.0\.0\.1:(\d+)/v1")
    while time.time() - start < 10:
        try:
            line = q.get(timeout=0.25)
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        match = pattern.search(line)
        if match:
            port = int(match.group(1))
            break

    if port is None:
        try:
            proc.terminate()
        except Exception:
            pass
        raise AssertionError("Gateway did not start (port not detected from stdout)")

    return proc, port


def _stop_gateway(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return

    try:
        if sys.platform != "win32":
            proc.send_signal(signal.SIGINT)
        else:
            proc.terminate()
    except Exception:
        pass

    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_gateway_cli_mock_e2e_with_metadata():
    proc, port = _start_gateway(
        "--mode", "mock", "--host", "127.0.0.1", "--port", "0", "--include-gateway-metadata"
    )
    try:
        base = f"http://127.0.0.1:{port}"

        health = httpx.get(f"{base}/health", timeout=5.0)
        assert health.status_code == 200
        assert health.headers.get("X-Cascadeflow-Gateway") == "cascadeflow"
        assert health.headers.get("X-Cascadeflow-Gateway-Mode") == "mock"

        models = httpx.get(f"{base}/v1/models", timeout=5.0)
        assert models.status_code == 200
        assert models.headers.get("X-Cascadeflow-Gateway-Endpoint") == "models.list"

        chat = httpx.post(
            f"{base}/v1/chat/completions",
            json={"model": "cascadeflow-auto", "messages": [{"role": "user", "content": "Hello"}]},
            timeout=5.0,
        )
        assert chat.status_code == 200
        assert chat.headers.get("X-Cascadeflow-Gateway-API") == "openai"
        payload = chat.json()
        assert payload["choices"][0]["message"]["content"]
        assert payload["cascadeflow"]["gateway"]["endpoint"] == "chat.completions"

        anth = httpx.post(
            f"{base}/v1/messages",
            json={"model": "cascadeflow-fast", "messages": [{"role": "user", "content": "Hello"}]},
            timeout=5.0,
        )
        assert anth.status_code == 200
        assert anth.headers.get("X-Cascadeflow-Gateway-API") == "anthropic"

        embed = httpx.post(
            f"{base}/v1/embeddings",
            json={"model": "cascadeflow", "input": ["hello", "world"]},
            timeout=10.0,
        )
        assert embed.status_code == 200
        data = embed.json()
        assert len(data["data"]) == 2
        assert len(data["data"][0]["embedding"]) == 384
    finally:
        _stop_gateway(proc)
