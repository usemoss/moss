"""
Minimal token-vending backend for the iOS `BackendTokenAuthenticator` sample.

This stands in for *your* API server. It is the only place that holds the
long-lived projectKey; the iOS app never sees it. The app calls
`GET /moss-token` and gets back a short-lived { token, expiresIn } which it
caches on-device (see BackendTokenAuthenticator.swift).

It exchanges your projectId + projectKey for a short-lived token via Moss's
auth endpoint.

Run it:
    cd examples/ios/token-server/python
    pip install -r requirements.txt
    MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... uvicorn server:app --port 3456

The iOS Simulator reaches this over http://localhost:3456 (the simulator shares
the host Mac's network). For a real device, use your Mac's LAN IP.
"""

import os

import httpx
from fastapi import FastAPI, HTTPException

MOSS_AUTH_URL = "https://service.usemoss.dev/identity/auth/token"

PROJECT_ID = os.environ.get("MOSS_PROJECT_ID")
PROJECT_KEY = os.environ.get("MOSS_PROJECT_KEY")
if not PROJECT_ID or not PROJECT_KEY:
    raise SystemExit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in the environment.")

app = FastAPI()


@app.get("/moss-token")
async def moss_token():
    # PRODUCTION: authenticate the caller here first (session cookie, your own
    # JWT, etc.) so only your signed-in users can mint Moss tokens. This sample
    # skips that to stay short.
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            MOSS_AUTH_URL,
            json={"projectId": PROJECT_ID, "projectKey": PROJECT_KEY},
        )

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid Moss credentials")
    resp.raise_for_status()

    # { "token": "...", "expiresIn": 3600 } — passed straight through to the app,
    # which caches it on-device until ~60s before expiry.
    data = resp.json()
    print(f"vended token (expiresIn={data.get('expiresIn')}s)")
    return data
