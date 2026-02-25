#!/usr/bin/env python3
"""
Test script to send a properly formatted GitHub webhook to the local server.
"""

import requests
import json
from datetime import datetime

# Webhook payload for a push event
payload = {
    "pusher": {
        "name": "testuser"
    },
    "ref": "refs/heads/main",
    "after": "abc123def456",
    "head_commit": {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }
}

# Send webhook to local server
url = "http://localhost:5000/webhook"
headers = {
    "Content-Type": "application/json",
    "X-GitHub-Event": "push"
}

print(f"Sending test webhook to {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

response = requests.post(url, json=payload, headers=headers)

print(f"\nResponse Status: {response.status_code}")
print(f"Response Body: {response.json()}")

if response.status_code == 200:
    print("\n✅ Webhook sent successfully!")
    print("Check the UI at http://localhost:5000 to see the event")
else:
    print("\n❌ Webhook failed!")
