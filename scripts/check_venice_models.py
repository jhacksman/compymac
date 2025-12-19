#!/usr/bin/env python3
"""
Debug tool to check all Venice.ai models are working.

This script tests each available Venice.ai model with a simple chat request
and reports which models are working and which are failing.

Usage:
    export LLM_API_KEY="your-venice-api-key"
    python scripts/check_venice_models.py
"""

import os
import sys
import time
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compymac.config import LLMConfig
from compymac.llm import LLMClient, LLMError


# All Venice.ai models (fetched from API Dec 2024)
# To update: curl -H "Authorization: Bearer $LLM_API_KEY" https://api.venice.ai/api/v1/models
VENICE_MODELS = [
    # Llama models
    {"id": "llama-3.3-70b", "name": "Llama 3.3 70B"},
    {"id": "llama-3.2-3b", "name": "Llama 3.2 3B"},
    {"id": "hermes-3-llama-3.1-405b", "name": "Hermes 3 Llama 3.1 405B"},
    # Qwen models
    {"id": "qwen3-4b", "name": "Qwen3 4B"},
    {"id": "qwen3-next-80b", "name": "Qwen3 Next 80B"},
    {"id": "qwen3-coder-480b-a35b-instruct", "name": "Qwen3 Coder 480B A35B"},
    {"id": "qwen3-235b-a22b-thinking-2507", "name": "Qwen3 235B Thinking"},
    {"id": "qwen3-235b-a22b-instruct-2507", "name": "Qwen3 235B Instruct"},
    # Other providers
    {"id": "mistral-31-24b", "name": "Mistral 31 24B"},
    {"id": "google-gemma-3-27b-it", "name": "Google Gemma 3 27B"},
    {"id": "grok-41-fast", "name": "Grok 41 Fast"},
    {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro Preview"},
    {"id": "claude-opus-45", "name": "Claude Opus 45"},
    {"id": "openai-gpt-oss-120b", "name": "OpenAI GPT OSS 120B"},
    {"id": "openai-gpt-52", "name": "OpenAI GPT 52"},
    {"id": "kimi-k2-thinking", "name": "Kimi K2 Thinking"},
    {"id": "zai-org-glm-4.6", "name": "ZAI GLM 4.6"},
    {"id": "deepseek-v3.2", "name": "DeepSeek V3.2"},
    {"id": "venice-uncensored", "name": "Venice Uncensored"},
]


@dataclass
class ModelTestResult:
    model_id: str
    model_name: str
    success: bool
    response_time: float
    response_preview: str
    error: str


def test_model(model_id: str, model_name: str, api_key: str, timeout: float = 60.0) -> ModelTestResult:
    """Test a single model with a simple chat request."""
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=api_key,
        model=model_id,
        temperature=0.7,
        max_tokens=50,
    )
    
    start_time = time.time()
    
    try:
        client = LLMClient(config)
        # Override timeout for this test
        client._client.timeout = timeout
        
        response = client.chat(
            messages=[{"role": "user", "content": "Say 'Hello' in one word."}]
        )
        
        elapsed = time.time() - start_time
        client.close()
        
        return ModelTestResult(
            model_id=model_id,
            model_name=model_name,
            success=True,
            response_time=elapsed,
            response_preview=response.content[:100] if response.content else "(empty)",
            error="",
        )
        
    except LLMError as e:
        elapsed = time.time() - start_time
        return ModelTestResult(
            model_id=model_id,
            model_name=model_name,
            success=False,
            response_time=elapsed,
            response_preview="",
            error=str(e)[:200],
        )
    except Exception as e:
        elapsed = time.time() - start_time
        return ModelTestResult(
            model_id=model_id,
            model_name=model_name,
            success=False,
            response_time=elapsed,
            response_preview="",
            error=f"Unexpected error: {str(e)[:150]}",
        )


def main():
    print("=" * 70)
    print("Venice.ai Model Health Check")
    print("=" * 70)
    
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        print("ERROR: LLM_API_KEY environment variable not set")
        print("Usage: export LLM_API_KEY='your-key' && python scripts/check_venice_models.py")
        return 1
    
    print(f"Testing {len(VENICE_MODELS)} models...")
    print(f"Timeout per model: 60 seconds")
    print("-" * 70)
    
    results: list[ModelTestResult] = []
    
    for i, model in enumerate(VENICE_MODELS, 1):
        model_id = model["id"]
        model_name = model["name"]
        
        print(f"\n[{i}/{len(VENICE_MODELS)}] Testing {model_name} ({model_id})...", end=" ", flush=True)
        
        result = test_model(model_id, model_name, api_key)
        results.append(result)
        
        if result.success:
            print(f"OK ({result.response_time:.1f}s)")
            print(f"    Response: {result.response_preview}")
        else:
            print(f"FAILED ({result.response_time:.1f}s)")
            print(f"    Error: {result.error}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    working = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    print(f"\nWorking models ({len(working)}/{len(results)}):")
    for r in working:
        print(f"  [OK] {r.model_name} ({r.model_id}) - {r.response_time:.1f}s")
    
    if failed:
        print(f"\nFailed models ({len(failed)}/{len(results)}):")
        for r in failed:
            print(f"  [FAIL] {r.model_name} ({r.model_id})")
            print(f"         Error: {r.error[:80]}...")
    
    print("\n" + "=" * 70)
    
    if len(working) == len(results):
        print("All models working!")
        return 0
    elif len(working) > 0:
        print(f"Partial success: {len(working)}/{len(results)} models working")
        return 0
    else:
        print("All models failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
