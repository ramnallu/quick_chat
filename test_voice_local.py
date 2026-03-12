#!/usr/bin/env python3
"""Local test client that simulates Twilio ConversationRelay WebSocket messages.

Connects to the server WebSocket, sends a setup message followed by
one or more prompt messages, and prints every response from the server.

Usage:
    # 1. Start the unified server
    #    uvicorn server:app --host 0.0.0.0 --port 8000
    #
    # 2. Run this test
    #    python test_voice_local.py

No Twilio account required.
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    sys.exit("Missing dependency: pip install websockets")

WS_URL = "ws://localhost:8000/voice-ws"

# Simulated ConversationRelay messages
SETUP_MESSAGE = {
    "type": "setup",
    "sessionId": "test-session-001",
    "callSid": "CA_test_00000000",
    "from": "+15559876543",
    "to": "+15551000001",  # maps to "sawan indian cuisine" in phone_mapping.json
}

TEST_PROMPTS = [
    "What are your hours today?",
    "Do you have vegetarian options?",
]


async def run_test():
    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL) as ws:
        # --- Setup -----------------------------------------------------------
        print("\n--- Sending SETUP ---")
        await ws.send(json.dumps(SETUP_MESSAGE))
        greeting = await asyncio.wait_for(ws.recv(), timeout=10)
        greeting_data = json.loads(greeting)
        print(f"  Greeting: {greeting_data.get('token', greeting_data)}")
        assert greeting_data.get("type") == "text", f"Expected 'text', got {greeting_data.get('type')}"

        # --- Prompts ---------------------------------------------------------
        for i, prompt_text in enumerate(TEST_PROMPTS, 1):
            print(f"\n--- Sending PROMPT {i}: \"{prompt_text}\" ---")
            await ws.send(json.dumps({
                "type": "prompt",
                "voicePrompt": prompt_text,
            }))

            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=60)
                resp_data = json.loads(resp)
                token = resp_data.get("token", "")
                print(f"  Agent: {token}")
                assert resp_data.get("type") == "text", f"Expected 'text', got {resp_data.get('type')}"
                word_count = len(token.split())
                print(f"  Word count: {word_count} (max recommended: 75)")
            except asyncio.TimeoutError:
                print("  ERROR: Timed out waiting for response")

        # --- Interrupt test --------------------------------------------------
        print("\n--- Sending INTERRUPT ---")
        await ws.send(json.dumps({"type": "interrupt"}))
        # Interrupts don't produce a response, just verify no crash
        await asyncio.sleep(0.5)

        print("\n--- All tests passed ---")


if __name__ == "__main__":
    asyncio.run(run_test())
