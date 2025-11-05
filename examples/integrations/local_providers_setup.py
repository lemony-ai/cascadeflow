"""
Ollama and vLLM Setup Examples

This example demonstrates how to configure and use Ollama and vLLM
in various scenarios:
- Local installation (default)
- Network deployment (another machine on your network)
- Remote server (with authentication)

Both providers are FREE (no API costs) and offer privacy-first inference.
"""

import asyncio
import os


# ============================================================================
# SCENARIO 1: Local Installation (Default)
# ============================================================================


async def example_1_local_ollama():
    """
    Scenario 1a: Local Ollama (default configuration)

    Requirements:
    - Ollama installed and running on localhost
    - No environment variables needed
    - No API key needed

    Installation:
    1. Download Ollama: https://ollama.ai/download
    2. Install and run: ollama serve (auto-starts on macOS/Windows)
    3. Pull a model: ollama pull llama3.2
    """
    print("\n" + "=" * 80)
    print("SCENARIO 1a: Local Ollama (localhost:11434)")
    print("=" * 80)

    from cascadeflow.providers.ollama import OllamaProvider

    # No configuration needed - uses default localhost:11434
    provider = OllamaProvider()

    try:
        # List available models
        models = await provider.list_models()
        print(f"\n✓ Available models: {models}")

        # Use a model
        if models:
            response = await provider.complete(
                prompt="What is 2+2?",
                model=models[0]
            )
            print(f"\n✓ Response: {response.content}")
            print(f"✓ Cost: ${response.cost} (FREE!)")
            print(f"✓ Latency: {response.latency_ms:.0f}ms")
        else:
            print("\n⚠️  No models found. Pull a model with: ollama pull llama3.2")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Is Ollama running? Try: ollama serve")
        print("  2. Test connection: curl http://localhost:11434/api/tags")

    await provider.client.aclose()


async def example_1_local_vllm():
    """
    Scenario 1b: Local vLLM (default configuration)

    Requirements:
    - vLLM installed and running on localhost
    - No environment variables needed
    - No API key needed

    Installation:
    1. Install vLLM: pip install vllm
    2. Start server:
       python -m vllm.entrypoints.openai.api_server \
         --model meta-llama/Llama-3-8B-Instruct \
         --port 8000
    3. Test: curl http://localhost:8000/v1/models
    """
    print("\n" + "=" * 80)
    print("SCENARIO 1b: Local vLLM (localhost:8000)")
    print("=" * 80)

    from cascadeflow.providers.vllm import VLLMProvider

    # No configuration needed - uses default localhost:8000/v1
    provider = VLLMProvider()

    try:
        # List available models
        models = await provider.list_models()
        print(f"\n✓ Available models: {models}")

        # Use the model
        if models:
            response = await provider.complete(
                prompt="What is the capital of France?",
                model=models[0],
                logprobs=True  # vLLM supports native logprobs!
            )
            print(f"\n✓ Response: {response.content}")
            print(f"✓ Cost: ${response.cost} (FREE!)")
            print(f"✓ Confidence: {response.confidence:.3f}")
            print(f"✓ Has logprobs: {hasattr(response, 'logprobs') and response.logprobs is not None}")
        else:
            print("\n⚠️  No models found. Is vLLM server running?")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Is vLLM running? Check: curl http://localhost:8000/v1/models")
        print("  2. Start server: python -m vllm.entrypoints.openai.api_server --model <model>")

    await provider.client.aclose()


# ============================================================================
# SCENARIO 2: Network Deployment (Another Machine on Your Network)
# ============================================================================


async def example_2_network_ollama():
    """
    Scenario 2a: Ollama on another machine in your network

    Use Case:
    - Run Ollama on a more powerful machine in your network
    - Access from your development machine
    - Great for shared team resources

    Setup on server machine (192.168.1.100):
    1. Install Ollama
    2. Configure to accept network connections:
       OLLAMA_HOST=0.0.0.0:11434 ollama serve
    3. Pull models: ollama pull llama3.2

    Setup on client machine:
    - Set OLLAMA_BASE_URL=http://192.168.1.100:11434
    """
    print("\n" + "=" * 80)
    print("SCENARIO 2a: Network Ollama (192.168.1.100:11434)")
    print("=" * 80)

    from cascadeflow.providers.ollama import OllamaProvider

    # Option A: Set via environment variable
    os.environ["OLLAMA_BASE_URL"] = "http://192.168.1.100:11434"
    provider_env = OllamaProvider()

    # Option B: Set via parameter
    provider_param = OllamaProvider(base_url="http://192.168.1.100:11434")

    print("\n✓ Configuration:")
    print(f"  Base URL (env): {provider_env.base_url}")
    print(f"  Base URL (param): {provider_param.base_url}")
    print("\nUsage is identical to local setup!")

    await provider_env.client.aclose()
    await provider_param.client.aclose()


async def example_2_network_vllm():
    """
    Scenario 2b: vLLM on another machine in your network

    Use Case:
    - Run vLLM on a GPU server in your network
    - Access from any machine on the network
    - Share expensive GPU resources across team

    Setup on GPU server (192.168.1.200):
    1. Install vLLM: pip install vllm
    2. Start server accessible on network:
       python -m vllm.entrypoints.openai.api_server \
         --model meta-llama/Llama-3-70B-Instruct \
         --host 0.0.0.0 \
         --port 8000
    3. Note: Use --host 0.0.0.0 to accept network connections

    Setup on client machine:
    - Set VLLM_BASE_URL=http://192.168.1.200:8000/v1
    """
    print("\n" + "=" * 80)
    print("SCENARIO 2b: Network vLLM (192.168.1.200:8000)")
    print("=" * 80)

    from cascadeflow.providers.vllm import VLLMProvider

    # Option A: Set via environment variable
    os.environ["VLLM_BASE_URL"] = "http://192.168.1.200:8000/v1"
    provider_env = VLLMProvider()

    # Option B: Set via parameter
    provider_param = VLLMProvider(base_url="http://192.168.1.200:8000/v1")

    print("\n✓ Configuration:")
    print(f"  Base URL (env): {provider_env.base_url}")
    print(f"  Base URL (param): {provider_param.base_url}")
    print("\nUsage is identical to local setup!")

    await provider_env.client.aclose()
    await provider_param.client.aclose()


# ============================================================================
# SCENARIO 3: Remote Server (with Authentication)
# ============================================================================


async def example_3_remote_ollama():
    """
    Scenario 3a: Remote Ollama with authentication

    Use Case:
    - Run Ollama on a cloud server
    - Access from anywhere (not just local network)
    - Secure with authentication

    Setup on remote server (ollama.yourdomain.com):
    1. Install Ollama
    2. Set up reverse proxy (nginx/caddy) with SSL
    3. Add authentication (Basic Auth, JWT, etc.)
    4. Configure firewall rules

    Example nginx config:
    ```nginx
    location /api/ {
        auth_basic "Ollama API";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://localhost:11434/api/;
        proxy_set_header Authorization $http_authorization;
    }
    ```

    Setup on client:
    - Set OLLAMA_BASE_URL=https://ollama.yourdomain.com
    - Set OLLAMA_API_KEY=your_auth_token (if using Bearer token)
    """
    print("\n" + "=" * 80)
    print("SCENARIO 3a: Remote Ollama with Authentication")
    print("=" * 80)

    from cascadeflow.providers.ollama import OllamaProvider

    # Option A: Set via environment variables
    os.environ["OLLAMA_BASE_URL"] = "https://ollama.yourdomain.com"
    os.environ["OLLAMA_API_KEY"] = "your_auth_token_here"
    provider_env = OllamaProvider()

    # Option B: Set via parameters
    provider_param = OllamaProvider(
        base_url="https://ollama.yourdomain.com",
        api_key="your_auth_token_here"
    )

    print("\n✓ Configuration:")
    print(f"  Base URL: {provider_env.base_url}")
    print(f"  Has auth: {bool(provider_env.api_key)}")
    print(f"  SSL enabled: {provider_env.base_url.startswith('https')}")
    print("\nAuthentication:")
    print("  - Authorization header automatically added")
    print("  - Bearer token format: 'Bearer your_auth_token_here'")

    await provider_env.client.aclose()
    await provider_param.client.aclose()


async def example_3_remote_vllm():
    """
    Scenario 3b: Remote vLLM with authentication

    Use Case:
    - Run vLLM on cloud GPU (AWS, GCP, Azure)
    - Access from anywhere
    - Secure with API key

    Setup on cloud server (vllm.yourdomain.com):
    1. Deploy vLLM to cloud GPU instance
    2. Start with authentication:
       python -m vllm.entrypoints.openai.api_server \
         --model meta-llama/Llama-3-70B-Instruct \
         --host 0.0.0.0 \
         --port 8000 \
         --api-key your_secure_api_key
    3. Set up SSL (use nginx/caddy reverse proxy)
    4. Configure firewall

    Setup on client:
    - Set VLLM_BASE_URL=https://vllm.yourdomain.com/v1
    - Set VLLM_API_KEY=your_secure_api_key
    """
    print("\n" + "=" * 80)
    print("SCENARIO 3b: Remote vLLM with Authentication")
    print("=" * 80)

    from cascadeflow.providers.vllm import VLLMProvider

    # Option A: Set via environment variables
    os.environ["VLLM_BASE_URL"] = "https://vllm.yourdomain.com/v1"
    os.environ["VLLM_API_KEY"] = "your_secure_api_key"
    provider_env = VLLMProvider()

    # Option B: Set via parameters
    provider_param = VLLMProvider(
        base_url="https://vllm.yourdomain.com/v1",
        api_key="your_secure_api_key"
    )

    print("\n✓ Configuration:")
    print(f"  Base URL: {provider_env.base_url}")
    print(f"  Has auth: {bool(provider_env.api_key)}")
    print(f"  SSL enabled: {provider_env.base_url.startswith('https')}")
    print("\nAuthentication:")
    print("  - Authorization header automatically added")
    print("  - Bearer token format: 'Bearer your_secure_api_key'")

    await provider_env.client.aclose()
    await provider_param.client.aclose()


# ============================================================================
# SCENARIO 4: Hybrid Setup (Best of All Worlds)
# ============================================================================


async def example_4_hybrid_setup():
    """
    Scenario 4: Hybrid setup using both Ollama and vLLM

    Use Case:
    - Use Ollama for development/testing (easy setup, small models)
    - Use vLLM for production (high performance, large models)
    - Automatic fallback between providers

    Setup:
    - Local Ollama for development: llama3.2:1b (fast, small)
    - Network vLLM for production: Llama-3-70B-Instruct (powerful)
    - cascadeflow automatically picks the best provider
    """
    print("\n" + "=" * 80)
    print("SCENARIO 4: Hybrid Setup (Ollama + vLLM)")
    print("=" * 80)

    from cascadeflow import CascadeAgent, ModelConfig

    # Create agent with cascading fallback
    agent = CascadeAgent(
        models=[
            ModelConfig(
                name="meta-llama/Llama-3-70B-Instruct",
                provider="vllm",
                base_url="http://192.168.1.200:8000/v1",
                cost=0,  # Free self-hosted
            ),
            ModelConfig(
                name="llama3.2:1b",
                provider="ollama",
                cost=0,  # Free local
            ),
        ]
    )

    print("\n✓ Configuration:")
    print(f"  Primary: vLLM (Llama-3-70B) - High quality")
    print(f"  Fallback: Ollama (llama3.2:1b) - Fast & free")
    print("\nBenefits:")
    print("  ✓ Best quality when vLLM available")
    print("  ✓ Always works (fallback to Ollama)")
    print("  ✓ Zero API costs for both")
    print("  ✓ Complete privacy (all local/network)")


# ============================================================================
# Configuration Summary
# ============================================================================


def print_configuration_summary():
    """Print summary of all configuration options."""
    print("\n" + "=" * 80)
    print("CONFIGURATION SUMMARY")
    print("=" * 80)

    print("\n📍 OLLAMA Configuration Options:")
    print("-" * 80)
    print("Environment Variables:")
    print("  OLLAMA_BASE_URL     - Server URL (http://localhost:11434)")
    print("  OLLAMA_HOST         - Legacy server URL (deprecated, use OLLAMA_BASE_URL)")
    print("  OLLAMA_API_KEY      - Optional API key for remote servers")
    print()
    print("Code Configuration:")
    print("  OllamaProvider(")
    print("    base_url='http://192.168.1.100:11434',  # Override URL")
    print("    api_key='your_token',                    # Optional auth")
    print("    timeout=300.0                            # Request timeout")
    print("  )")
    print()
    print("Examples:")
    print("  Local:   OLLAMA_BASE_URL=http://localhost:11434")
    print("  Network: OLLAMA_BASE_URL=http://192.168.1.100:11434")
    print("  Remote:  OLLAMA_BASE_URL=https://ollama.yourdomain.com")
    print("           OLLAMA_API_KEY=your_auth_token")

    print("\n📍 vLLM Configuration Options:")
    print("-" * 80)
    print("Environment Variables:")
    print("  VLLM_BASE_URL       - Server URL (http://localhost:8000/v1)")
    print("  VLLM_API_KEY        - Optional API key for authentication")
    print("  VLLM_MODEL_NAME     - Optional: specify which model is loaded")
    print()
    print("Code Configuration:")
    print("  VLLMProvider(")
    print("    base_url='http://192.168.1.200:8000/v1',  # Override URL")
    print("    api_key='your_token',                      # Optional auth")
    print("    timeout=120.0                              # Request timeout")
    print("  )")
    print()
    print("Examples:")
    print("  Local:   VLLM_BASE_URL=http://localhost:8000/v1")
    print("  Network: VLLM_BASE_URL=http://192.168.1.200:8000/v1")
    print("  Remote:  VLLM_BASE_URL=https://vllm.yourdomain.com/v1")
    print("           VLLM_API_KEY=your_secure_api_key")

    print("\n🔒 Security Best Practices:")
    print("-" * 80)
    print("  1. Use HTTPS (SSL) for remote deployments")
    print("  2. Use strong API keys (not 'your_token'!)")
    print("  3. Configure firewall rules to limit access")
    print("  4. Use reverse proxy (nginx/caddy) for SSL termination")
    print("  5. Monitor server logs for suspicious activity")
    print("  6. Rotate API keys regularly")
    print("  7. Use VPN for network deployments if possible")

    print("\n💡 Tips:")
    print("-" * 80)
    print("  • Local: Fastest latency, easiest setup")
    print("  • Network: Share GPU resources across team")
    print("  • Remote: Access from anywhere, requires security setup")
    print("  • Hybrid: Best of all worlds with automatic fallback")
    print("  • Both providers are 100% FREE (no API costs)")
    print("  • Both support tool calling for agentic workflows")


# ============================================================================
# Main
# ============================================================================


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("OLLAMA & vLLM SETUP EXAMPLES")
    print("=" * 80)
    print("\nThis example shows how to configure Ollama and vLLM for:")
    print("  1. Local installation (localhost)")
    print("  2. Network deployment (another machine)")
    print("  3. Remote server (with authentication)")
    print("  4. Hybrid setup (best of all)")

    # Run examples (comment out as needed)
    try:
        # Local examples (will actually try to connect)
        await example_1_local_ollama()
        await example_1_local_vllm()
    except Exception as e:
        print(f"\n⚠️  Local examples failed: {e}")
        print("This is expected if Ollama/vLLM is not running locally")

    # Network examples (configuration only, won't connect)
    await example_2_network_ollama()
    await example_2_network_vllm()

    # Remote examples (configuration only)
    await example_3_remote_ollama()
    await example_3_remote_vllm()

    # Hybrid example
    await example_4_hybrid_setup()

    # Print summary
    print_configuration_summary()

    print("\n" + "=" * 80)
    print("✅ Examples complete!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Choose your deployment scenario")
    print("  2. Set environment variables in .env file")
    print("  3. Test with: python examples/integrations/test_all_providers.py")
    print()


if __name__ == "__main__":
    asyncio.run(main())
