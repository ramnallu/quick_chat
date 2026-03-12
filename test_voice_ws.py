#!/usr/bin/env python3
"""Local test script that simulates Retell AI WebSocket messages.

This connects to the voice_server's WebSocket endpoint and sends a
sequence of Retell-format messages to verify the integration end-to-end
without needing an actual Retell account or phone call.

Usage:
    # Terminal 1 — start the voice server
    python voice_server.py

    # Terminal 2 — run this test
    python test_voice_ws.py

    # Optionally specify the business to test:
    python test_voice_ws.py --business "Sawan Indian Cuisine"
    python test_voice_ws.py --business "Active Body Fitness"
    python test_voice_ws.py --business "White Tiger Martial Arts"
"""

import argparse
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("ERROR: 'websockets' package required. Install with:")
    print("  pip install websockets")
    sys.exit(1)


DEFAULT_SERVER = "ws://localhost:8080"
DEFAULT_BUSINESS = "Sawan Indian Cuisine"

# Simulated user questions to cycle through
TEST_QUESTIONS = [
    "What are your hours?",
    "Do you have any vegetarian options?",
    "Where are you located?",
]


def make_call_details(business_id: str) -> str:
    """Build a simulated Retell call_details message."""
    return json.dumps({
        "interaction_type": "call_details",
        "call": {
            "call_id": "test-call-001",
            "from_number": "+15551234567",
            "to_number": "+10987654321",
            "business_id": business_id,  # Override for testing
        },
    })


def make_response_required(transcript: list[dict]) -> str:
    """Build a simulated Retell response_required message."""
    return json.dumps({
        "interaction_type": "response_required",
        "transcript": transcript,
    })


def make_ping() -> str:
    return json.dumps({"interaction_type": "ping"})


async def run_test(server_url: str, business_id: str):
    call_id = "test-call-001"
    ws_url = f"{server_url}/llm-websocket/{call_id}"
    print(f"\n{'='*60}")
    print(f"  Retell WebSocket Test Client")
    print(f"  Server:   {ws_url}")
    print(f"  Business: {business_id}")
    print(f"{'='*60}\n")

    async with websockets.connect(ws_url) as ws:
        # ----------------------------------------------------------
        # Step 1: Send call_details
        # ----------------------------------------------------------
        print("[TX] call_details")
        await ws.send(make_call_details(business_id))

        # Receive greeting
        greeting_raw = await asyncio.wait_for(ws.recv(), timeout=10)
        greeting = json.loads(greeting_raw)
        print(f"[RX] Greeting: {greeting.get('content', '')}\n")

        # ----------------------------------------------------------
        # Step 2: Send a ping to verify keep-alive
        # ----------------------------------------------------------
        print("[TX] ping")
        await ws.send(make_ping())
        pong_raw = await asyncio.wait_for(ws.recv(), timeout=5)
        pong = json.loads(pong_raw)
        print(f"[RX] {pong}\n")

        # ----------------------------------------------------------
        # Step 3: Simulate conversation turns
        # ----------------------------------------------------------
        transcript = [
            {"role": "agent", "content": greeting.get("content", "Hello!")},
        ]

        for question in TEST_QUESTIONS:
            print(f"[TX] User says: \"{question}\"")
            transcript.append({"role": "user", "content": question})
            await ws.send(make_response_required(transcript))

            # Collect all streaming frames until content_complete
            full_response = ""
            while True:
                frame_raw = await asyncio.wait_for(ws.recv(), timeout=60)
                frame = json.loads(frame_raw)
                content = frame.get("content", "")
                full_response += content

                if frame.get("content_complete", False):
                    break

            print(f"[RX] Agent: {full_response.strip()}\n")
            transcript.append({"role": "agent", "content": full_response.strip()})

        print(f"{'='*60}")
        print("  Test completed successfully!")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Test the QuickChat voice WebSocket server")
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"WebSocket server base URL (default: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--business",
        default=DEFAULT_BUSINESS,
        help=f"Business name to test (default: {DEFAULT_BUSINESS})",
    )
    args = parser.parse_args()

    asyncio.run(run_test(args.server, args.business))


if __name__ == "__main__":
    main()
