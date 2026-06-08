# Token server (for the iOS auth sample)

A tiny stand-in for *your* backend. It holds the long-lived `projectKey` and
vends short-lived Moss tokens to the iOS app, so the key never ships in the app
binary. Pairs with
[`BackendTokenAuthenticator.swift`](../MossExample/BackendTokenAuthenticator.swift).

The app only needs an HTTP endpoint that returns
`{ "token": "...", "expiresIn": 3600 }`, so the backend language is your choice.
Two equivalent implementations are provided — pick one:

| Language | Folder | How it gets the token |
| --- | --- | --- |
| Node | [`node/`](node/) | Uses the JS SDK's `MossClient.getAuthToken()` helper. |
| Python | [`python/`](python/) | Calls Moss's auth endpoint directly. |

Both expose the same `GET /moss-token` route on port `3456` and return the same
JSON, so nothing changes on the iOS side either way.

## Run it

### Node

```bash
cd node
npm install
MOSS_PROJECT_ID=your_project_id MOSS_PROJECT_KEY=your_project_key npm start
```

### Python

```bash
cd python
pip install -r requirements.txt
MOSS_PROJECT_ID=your_project_id MOSS_PROJECT_KEY=your_project_key \
  uvicorn server:app --port 3456
```

Either way you should be able to hit it from another terminal:

```bash
curl http://localhost:3456/moss-token
# {"token":"eyJhbGciOi...","expiresIn":3600}
```

## Point the app at it

1. Launch the app and, on the credentials screen, fill in the **Project ID**
   and the **Token endpoint URL** (`http://localhost:3456/moss-token`). Leave
   the project key blank — when a token URL is present the app authenticates
   through `BackendTokenAuthenticator` instead of the static key.
2. Tap **Run Session Demo**. Watch the server log: you'll see **one**
   `vended token` line for the whole run, not one per request — that's the
   on-device cache working.

- **Simulator:** `http://localhost:3456` reaches your Mac directly.
- **Real device:** use your Mac's LAN IP (e.g. `http://192.168.1.20:3456`) and
  make sure the phone is on the same Wi-Fi.

## Note on HTTP

The app's `Info.plist` enables `NSAllowsLocalNetworking` so the Simulator can
reach this plain-HTTP localhost server during development. A production token
endpoint is served over **HTTPS**, which needs no App Transport Security
exception — you can drop that key for a real build.

## Production note

Both servers skip authenticating the *caller* to stay short. In production,
verify the request comes from a signed-in user (session cookie, your own JWT,
OAuth introspection, …) before vending a Moss token.
