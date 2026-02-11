import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time

import httpx
import pytest


def _start_gateway_agent(*args: str) -> tuple[subprocess.Popen, int]:
    cmd = [sys.executable, "-u", "-m", "cascadeflow.server", *args]
    proc = subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
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
    pattern = re.compile(r"running at http://[^:]+:(\d+)/v1")
    recent: list[str] = []
    while time.time() - start < 15:
        try:
            line = q.get(timeout=0.25)
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        recent.append(line)
        if len(recent) > 50:
            recent = recent[-50:]
        match = pattern.search(line)
        if match:
            port = int(match.group(1))
            break

    if port is None:
        try:
            proc.terminate()
        except Exception:
            pass
        debug_tail = "\n".join(recent[-25:])
        raise AssertionError(
            "Gateway did not start (port not detected from stdout). Last lines:\n" + debug_tail
        )

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
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.integration
@pytest.mark.requires_api
def test_gateway_agent_mode_real_providers_smoke():
    # This is intentionally opt-in (integration test).
    # Run locally with:
    #   set -a && source /Users/saschabuehrle/dev/cascadeflow/.env && set +a
    #   pytest -m "integration and requires_api" tests/test_gateway_agent_integration.py -v
    if (
        not os.getenv("GROQ_API_KEY")
        and not os.getenv("OPENAI_API_KEY")
        and not os.getenv("ANTHROPIC_API_KEY")
    ):
        pytest.skip(
            "No provider keys set (need at least GROQ_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)"
        )

    proc, port = _start_gateway_agent(
        "--mode",
        "agent",
        "--preset",
        "development",
        "--host",
        "127.0.0.1",
        "--port",
        "0",
        "--include-gateway-metadata",
    )
    try:
        base = f"http://127.0.0.1:{port}"

        health = httpx.get(f"{base}/health", timeout=5.0)
        assert health.status_code == 200
        assert health.headers.get("X-Cascadeflow-Gateway-Mode") == "agent"

        chat = httpx.post(
            f"{base}/v1/chat/completions",
            json={
                "model": "cascadeflow",
                "messages": [{"role": "user", "content": "Say hello in one sentence."}],
            },
            timeout=60.0,
        )
        assert chat.status_code == 200
        data = chat.json()
        assert data["choices"][0]["message"]["content"]
        assert data["cascadeflow"]["gateway"]["mode"] == "agent"

        with httpx.stream(
            "POST",
            f"{base}/v1/chat/completions",
            json={
                "model": "cascadeflow",
                "messages": [{"role": "user", "content": "Stream a short greeting."}],
                "stream": True,
            },
            timeout=60.0,
        ) as resp:
            assert resp.status_code == 200
            lines = [line for line in resp.iter_lines() if line]
        assert any(line.startswith("data: ") for line in lines)
        assert lines[-1] == "data: [DONE]"

        anth = httpx.post(
            f"{base}/v1/messages",
            json={
                "model": "claude-any",
                "max_tokens": 64,
                "messages": [{"role": "user", "content": "Say hello in one sentence."}],
            },
            timeout=60.0,
        )
        assert anth.status_code == 200
        anth_data = anth.json()
        assert anth_data["type"] == "message"
        assert any(block.get("type") == "text" for block in anth_data.get("content", []))
    finally:
        _stop_gateway(proc)
