#!/usr/bin/env python3
"""
Continuously send test webhooks every 10 seconds so you can see them in the UI.
Press Ctrl+C to stop.
"""

import requests
import json
from datetime import datetime
import time

def send_webhook():
    payload = {
        "pusher": {
            "name": "testuser"
        },
        "ref": "refs/heads/main",
        "after": f"commit{int(time.time())}",  # Unique commit ID
        "head_commit": {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    }

    url = "http://localhost:5000/webhook"
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Webhook sent successfully")
        else:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Error: {e}")

if __name__ == "__main__":
    print("🚀 Starting continuous webhook sender...")
    print("📊 Open http://localhost:5000 to see events in real-time")
    print("⏱️  Sending webhooks every 10 seconds")
    print("🛑 Press Ctrl+C to stop\n")
    
    try:
        while True:
            send_webhook()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n\n✋ Stopped sending webhooks")
