import os
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

import httpx


def _pick_free_port() -> int:
    # Best-effort: avoids relying on subprocess stdout timing to discover an ephemeral port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_gateway(*args: str) -> tuple[subprocess.Popen, int, str]:
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
    fd, port_file = tempfile.mkstemp(prefix="cascadeflow-gateway-port-", suffix=".txt")
    os.close(fd)
    env["CASCADEFLOW_GATEWAY_PORT_FILE"] = port_file
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

    start = time.time()
    seen: list[str] = []
    while time.time() - start < 30:
        # Prefer probing readiness instead of parsing stdout/port files (CI/macOS can be flaky).
        try:
            health = httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.5)
            if health.status_code == 200:
                return proc, port, port_file
        except Exception:
            pass

        try:
            line = q.get(timeout=0.25)
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        seen.append(line)
        # Keep collecting output for debugging on failure.

    try:
        proc.terminate()
    except Exception:
        pass

    tail = "\n".join(seen[-50:])
    try:
        port_file_contents = open(port_file, encoding="utf-8").read()
    except Exception as exc:
        port_file_contents = f"<unreadable: {exc}>"

    raise AssertionError(
        "Gateway did not become ready (GET /health did not return 200). "
        f"returncode={proc.poll()} port={port} port_file={port_file} port_file_contents={port_file_contents!r} "
        f"last_output=\n{tail}"
    )


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

        health = httpx.get(f"{base}/health", timeout=5.0)
        assert health.status_code == 200
        assert health.headers.get("X-Cascadeflow-Gateway") == "cascadeflow"
        assert health.headers.get("X-Cascadeflow-Gateway-Mode") == "mock"
        assert health.headers.get("Access-Control-Allow-Origin") == "https://example.com"

        models = httpx.get(f"{base}/v1/models", timeout=5.0)
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

        health = httpx.get(f"{base}/health", timeout=5.0)
        assert health.status_code == 200
        assert health.headers.get("X-Cascadeflow-Gateway") is None
        assert health.headers.get("Access-Control-Allow-Origin") is None

        chat = httpx.post(
            f"{base}/v1/chat/completions",
            json={"model": "cascadeflow", "messages": [{"role": "user", "content": "Hello"}]},
            timeout=5.0,
        )
        assert chat.status_code == 200
    finally:
        _stop_gateway(proc)
        try:
            os.unlink(port_file)
        except Exception:
            pass
