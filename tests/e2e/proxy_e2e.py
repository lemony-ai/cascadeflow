import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass
class TestResult:
    name: str
    status: str
    detail: str
    response_status: int | None = None


def wait_for_port(port: int, timeout: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def start_proxy() -> subprocess.Popen:
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = f"{repo_root}:{env.get('PYTHONPATH', '')}"
    process = subprocess.Popen(
        [sys.executable, "-m", "cascadeflow.proxy.server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if not wait_for_port(8000, timeout=15):
        stdout, stderr = process.communicate(timeout=2)
        raise RuntimeError(f"Proxy failed to start. stdout={stdout} stderr={stderr}")
    return process


def stop_proxy(process: subprocess.Popen) -> None:
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> requests.Response:
    return requests.post(url, headers=headers, json=payload, timeout=30)


def run_proxy_tests() -> dict[str, Any]:
    results: list[TestResult] = []
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not openai_key:
        results.append(TestResult("openai_e2e", "skipped", "OPENAI_API_KEY not set"))
    if not anthropic_key:
        results.append(TestResult("anthropic_e2e", "skipped", "ANTHROPIC_API_KEY not set"))

    if openai_key:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}",
        }
        payload = {
            "model": "cascadeflow-auto",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        response = post_json("http://localhost:8000/v1/chat/completions", headers, payload)
        status = "passed" if response.ok else "failed"
        results.append(
            TestResult(
                "openai_e2e",
                status,
                response.text[:400],
                response_status=response.status_code,
            )
        )

        # Streaming test
        stream_payload = {
            "model": "cascadeflow-auto",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        stream_response = requests.post(
            "http://localhost:8000/v1/chat/completions",
            headers=headers,
            json=stream_payload,
            stream=True,
            timeout=30,
        )
        chunk_ok = False
        if stream_response.ok:
            for line in stream_response.iter_lines():
                if line and line.startswith(b"data:"):
                    chunk_ok = True
                    break
        results.append(
            TestResult(
                "openai_streaming",
                "passed" if chunk_ok else "failed",
                "received SSE chunk" if chunk_ok else "no SSE chunk found",
                response_status=stream_response.status_code,
            )
        )

        # Virtual models
        for model_name in [
            "cascadeflow-auto",
            "cascadeflow-fast",
            "cascadeflow-quality",
            "cascadeflow-cost",
        ]:
            payload["model"] = model_name
            response = post_json("http://localhost:8000/v1/chat/completions", headers, payload)
            status = "passed" if response.ok else "failed"
            results.append(
                TestResult(
                    f"virtual_model_{model_name}",
                    status,
                    response.text[:400],
                    response_status=response.status_code,
                )
            )

    if anthropic_key:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": anthropic_key,
        }
        payload = {
            "model": "cascadeflow-auto",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Hello"}],
        }
        response = post_json("http://localhost:8000/v1/messages", headers, payload)
        status = "passed" if response.ok else "failed"
        results.append(
            TestResult(
                "anthropic_e2e",
                status,
                response.text[:400],
                response_status=response.status_code,
            )
        )

        stream_payload = {
            "model": "cascadeflow-auto",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        stream_response = requests.post(
            "http://localhost:8000/v1/messages",
            headers=headers,
            json=stream_payload,
            stream=True,
            timeout=30,
        )
        chunk_ok = False
        if stream_response.ok:
            for line in stream_response.iter_lines():
                if line and line.startswith(b"data:"):
                    chunk_ok = True
                    break
        results.append(
            TestResult(
                "anthropic_streaming",
                "passed" if chunk_ok else "failed",
                "received SSE chunk" if chunk_ok else "no SSE chunk found",
                response_status=stream_response.status_code,
            )
        )

    # Error handling tests (no keys required for some)
    invalid_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer invalid",
    }
    invalid_response = post_json(
        "http://localhost:8000/v1/chat/completions",
        invalid_headers,
        {"model": "cascadeflow-auto", "messages": [{"role": "user", "content": "Hello"}]},
    )
    results.append(
        TestResult(
            "error_invalid_key",
            "passed" if invalid_response.status_code >= 400 else "failed",
            invalid_response.text[:400],
            response_status=invalid_response.status_code,
        )
    )

    malformed_response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        data="not-json",
        timeout=30,
    )
    results.append(
        TestResult(
            "error_malformed_request",
            "passed" if malformed_response.status_code >= 400 else "failed",
            malformed_response.text[:400],
            response_status=malformed_response.status_code,
        )
    )

    model_not_found = post_json(
        "http://localhost:8000/v1/chat/completions",
        invalid_headers,
        {"model": "missing-model", "messages": [{"role": "user", "content": "Hello"}]},
    )
    results.append(
        TestResult(
            "error_model_not_found",
            "passed" if model_not_found.status_code >= 400 else "failed",
            model_not_found.text[:400],
            response_status=model_not_found.status_code,
        )
    )

    return {
        "results": [result.__dict__ for result in results],
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    try:
        proxy_spec = importlib.util.find_spec("cascadeflow.proxy.server")
    except ModuleNotFoundError:
        proxy_spec = None

    if proxy_spec is None:
        print(
            json.dumps(
                {
                    "results": [
                        {
                            "name": "proxy_boot",
                            "status": "skipped",
                            "detail": "cascadeflow.proxy.server module not found",
                            "response_status": None,
                        }
                    ]
                },
                indent=2,
            )
        )
        return 0
    proxy_process = None
    try:
        proxy_process = start_proxy()
        summary = run_proxy_tests()
        print(json.dumps(summary, indent=2))
    finally:
        if proxy_process:
            stop_proxy(proxy_process)

    failed = [r for r in summary["results"] if r["status"] == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
