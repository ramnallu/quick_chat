#!/usr/bin/env python3
"""Test client for the POST /chat endpoint.

Usage:
    # 1. Start the server
    #    uvicorn server:app --host 0.0.0.0 --port 8000
    #
    # 2. Run this test
    #    python test_chat_api.py
"""

import requests
import sys

BASE_URL = "http://localhost:8000"


def test_health():
    """Test the health endpoint."""
    print("--- Testing GET /health ---")
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["status"] == "ok"
    print(f"  Response: {data}")
    print("  PASSED")


def test_chat():
    """Test the chat endpoint with a sample query."""
    print("\n--- Testing POST /chat ---")
    payload = {
        "business_id": "Sawan Indian Cuisine",
        "query": "What are your hours?",
        "chat_history": [],
        "user_id": "test-user",
    }
    resp = requests.post(f"{BASE_URL}/chat", json=payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "answer" in data, f"Response missing 'answer' key: {data}"
    assert "sources" in data, f"Response missing 'sources' key: {data}"
    print(f"  Answer: {data['answer'][:200]}")
    print(f"  Sources: {data['sources']}")
    print("  PASSED")


def test_chat_with_history():
    """Test the chat endpoint with conversation history."""
    print("\n--- Testing POST /chat (with history) ---")
    payload = {
        "business_id": "Sawan Indian Cuisine",
        "query": "Do you have vegetarian options?",
        "chat_history": [
            {"role": "user", "content": "What are your hours?"},
            {"role": "assistant", "content": "We are open from 11am to 10pm."},
        ],
    }
    resp = requests.post(f"{BASE_URL}/chat", json=payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "answer" in data
    print(f"  Answer: {data['answer'][:200]}")
    print("  PASSED")


def test_chat_missing_fields():
    """Test validation: missing required fields."""
    print("\n--- Testing POST /chat (missing fields) ---")
    resp = requests.post(f"{BASE_URL}/chat", json={"query": "hello"})
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
    print(f"  Validation error (expected): {resp.status_code}")
    print("  PASSED")


if __name__ == "__main__":
    try:
        test_health()
        test_chat()
        test_chat_with_history()
        test_chat_missing_fields()
        print("\n--- All tests passed ---")
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to {BASE_URL}. Is the server running?", file=sys.stderr)
        sys.exit(1)
    except AssertionError as e:
        print(f"ERROR: Test failed: {e}", file=sys.stderr)
        sys.exit(1)
