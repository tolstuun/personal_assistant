#!/usr/bin/env python3
"""
Run the Personal Assistant server with HTTPS.

Usage:
    sudo python run.py
"""

from pathlib import Path

import uvicorn

# Let's Encrypt certificate paths
SSL_CERT = "/etc/letsencrypt/live/aioid.vip/fullchain.pem"
SSL_KEY = "/etc/letsencrypt/live/aioid.vip/privkey.pem"


def main():
    # Check if SSL certificates exist
    if not Path(SSL_CERT).exists() or not Path(SSL_KEY).exists():
        print("ERROR: SSL certificates not found!")
        print(f"Expected: {SSL_CERT}")
        print(f"Expected: {SSL_KEY}")
        print("\nRun: sudo certbot certonly --standalone -d aioid.vip")
        return

    print("Starting Personal Assistant with HTTPS...")
    print("URL: https://aioid.vip")

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=443,
        ssl_certfile=SSL_CERT,
        ssl_keyfile=SSL_KEY,
        log_level="info"
    )


if __name__ == "__main__":
    main()
