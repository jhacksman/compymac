"""
Venice.ai Smoke Test
Tests connectivity and basic functionality of Venice.ai API integration
"""

import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from MVPReader.core.venice_llm_client import VeniceLLMClient


async def test_venice_connection():
    """Test Venice.ai API connection"""
    
    print("Venice.ai Smoke Test")
    print("=" * 60)
    
    api_key = os.getenv("VENICE_API_KEY")
    base_url = os.getenv("VENICE_BASE_URL", "https://api.venice.ai")
    model = os.getenv("VENICE_MODEL", "qwen3-next-80b")
    
    if not api_key:
        print("\n❌ Error: VENICE_API_KEY environment variable not set")
        print("   Set it with: export VENICE_API_KEY='your-api-key'")
        return False
    
    print(f"\n✓ API Key: {api_key[:10]}...{api_key[-4:]}")
    print(f"✓ Base URL: {base_url}")
    print(f"✓ Model: {model}")
    
    print("\n1. Initializing Venice LLM client...")
    client = VeniceLLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model
    )
    print("   ✓ Client initialized")
    
    print("\n2. Testing chat completion...")
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello from Venice.ai!' and nothing else."}
        ]
        
        response = await client.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=50
        )
        
        print(f"   ✓ Response received: {response}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    print("\n3. Testing with analysis prompt...")
    try:
        messages = [
            {
                "role": "system",
                "content": "You are an AI assistant that analyzes social media feeds."
            },
            {
                "role": "user",
                "content": """Analyze this sample feed event:
                
[Slack] @alice in #ai-research: "Just published a new paper on transformer architectures"

Provide a brief highlight and suggestion."""
            }
        ]
        
        response = await client.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        
        print(f"   ✓ Analysis response received ({len(response)} chars)")
        print(f"\n   Response preview:")
        print(f"   {response[:200]}...")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! Venice.ai integration is working.")
    return True


def main():
    """Run smoke test"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(test_venice_connection())
        loop.close()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
