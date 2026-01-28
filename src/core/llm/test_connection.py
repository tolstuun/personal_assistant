"""
Simple test to verify LLM connection works.

Run: python -m src.core.llm.test_connection
"""

import asyncio
import os
import sys


async def test_connection():
    """Test that we can connect to LLM provider."""
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  No API key found in environment.")
        print("   Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        print("   Example: export ANTHROPIC_API_KEY='sk-...'")
        return False

    try:
        from src.core.llm import get_llm

        print("🔄 Testing LLM connection...")

        llm = get_llm()
        print(f"   Using model: {llm.get_model_name()}")

        response = await llm.complete("Say 'Hello, World!' and nothing else.")

        print("✅ Connection successful!")
        print(f"   Response: {response.content[:100]}")
        print(f"   Tokens used: {response.usage}")

        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


async def test_fetcher():
    """Test that fetcher works."""
    try:
        from src.core.primitives import fetch

        print("\n🔄 Testing Fetcher...")

        result = await fetch("https://httpbin.org/get")

        if result.ok:
            print("✅ Fetcher works!")
            print(f"   Status: {result.status_code}")
            print(f"   Content type: {result.content_type}")
            print(f"   Size: {result.content_length} bytes")
            return True
        else:
            print(f"❌ Fetcher returned non-OK status: {result.status_code}")
            return False

    except Exception as e:
        print(f"❌ Fetcher failed: {e}")
        return False


async def main():
    print("=" * 50)
    print("Personal Assistant — Connection Test")
    print("=" * 50)

    results = []
    results.append(await test_fetcher())
    results.append(await test_connection())

    print("\n" + "=" * 50)
    if all(results):
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
