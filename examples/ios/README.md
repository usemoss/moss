# Moss iOS Example

A SwiftUI app that exercises the [Moss Swift SDK](https://github.com/usemoss/moss)
end-to-end - on-device semantic search for iOS.

It demonstrates both halves of the SDK:

- **Cloud** - `createIndex` → `getIndex` → `listIndexes` → `addDocs` →
  `getDocs` → `loadIndex` → `query` → `deleteDocs` → `refreshIndex` →
  `onMemoryPressure`, with per-step timing.
- **Local sessions** - embed docs on-device (no network), `query`,
  `deleteDocs`, then `save` / reopen / `loadFromDisk`.
- **Live search** - query a cloud index on every keystroke, with
  cancellation so only the latest query's results show.

## Quick start

The whole API is `async`/`throws`. Construct a client, then either query a
cloud index or run a fully on-device session.

**Cloud** - create/load an index and search it:

```swift
import Moss

let client = try MossClient(projectId: "your_project_id", projectKey: "your_project_key")
defer { client.close() }

_ = try await client.createIndex("support-docs", docs: [
    .init(id: "1", text: "Refunds are processed within 3-5 business days."),
    .init(id: "2", text: "Track your order from the dashboard."),
])
try await client.loadIndex("support-docs")

let result = try await client.query("support-docs", "how long do refunds take?")
for doc in result.docs {
    print(String(format: "[%.3f] %@", doc.score, doc.text))
}
```

**On-device session** - embed and search locally, with no network calls:

```swift
let session = try await client.session("notes")
defer { session.close() }

try await session.addDocs([
    .init(id: "1", text: "Transformers replaced RNNs for sequence modeling."),
    .init(id: "2", text: "Embeddings map text into vectors for similarity search."),
])

let hits = try await session.query("how do transformers work", options: .init(topK: 3))
hits.docs.forEach { print($0.score, $0.id) }

// Persist so the next launch skips re-embedding.
try await session.save(toCachePath: NSTemporaryDirectory())
```

See [`MossDemoModel.swift`](MossExample/MossDemoModel.swift) for every call
exercised end-to-end with timing.

## Requirements

- iOS 15.1+
- Xcode 15+
- An **Apple Silicon** Mac. The SDK ships arm64 builds only (device and
  simulator); Intel simulators are not supported.
- [XcodeGen](https://github.com/yonyz/XcodeGen) to generate the project:
  `brew install xcodegen`

## The SDK dependency

The app depends on the published Moss Swift package - no local SDK checkout
needed. The dependency is declared in [`project.yml`](project.yml):

```yaml
packages:
  Moss:
    url: https://github.com/usemoss/moss
    from: 0.2.0
```

On first build, Xcode downloads the precompiled `Moss.xcframework` from the
[v0.2.0 release](https://github.com/usemoss/moss/releases/tag/v0.2.0),
verifies its checksum, and links it in.

## Generate the project

```bash
cd examples/ios
xcodegen generate
open MossExample.xcodeproj
```

Re-run `xcodegen generate` whenever you edit `project.yml`.

## Run

### Xcode

Open `MossExample.xcodeproj`, pick an **iPhone 15+** simulator on Apple
Silicon (or a connected device - set your team under **Signing &
Capabilities**), and hit ▶.

### Command line

`generic/platform=iOS Simulator` builds for the simulator without pinning a
specific device, so it works regardless of which simulators you have
installed:

```bash
xcodebuild -project MossExample.xcodeproj \
  -scheme MossExample \
  -destination 'generic/platform=iOS Simulator' \
  -configuration Debug \
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build
```

To target a specific simulator instead, pass e.g.
`-destination 'platform=iOS Simulator,name=iPhone 17 Pro'` - run
`xcrun simctl list devices available` to see what's installed.

## Using it

1. **First launch** shows a credentials screen - enter your Moss project ID,
   project key, and the name of a cloud index to search. Find these in the
   [Moss dashboard](https://portal.usemoss.dev).
2. **Search bar** queries that cloud index live as you type.
3. **Cloud Example** walks the full cloud API against a throwaway index and
   deletes it when done.
4. **Local Session** runs the entire on-device flow - no cloud project
   required, so it works even with placeholder credentials.

## Code tour

| File | What it shows |
| --- | --- |
| [`MossDemoModel.swift`](MossExample/MossDemoModel.swift) | Every SDK call, narrated step-by-step. Start here. |
| [`ContentView.swift`](MossExample/ContentView.swift) | SwiftUI wiring - credentials, live search, buttons. |
| [`MossExampleApp.swift`](MossExample/MossExampleApp.swift) | App entry point. |

## Credentials

To keep the sample short, it stores the project key in `@AppStorage`. For a
production app, use the `Authenticator` protocol instead: your app fetches a
short-lived token from your own backend, so the long-lived project key stays
on your server rather than shipping in the binary.

```swift
final class MyAuth: Authenticator {
    func getAuthHeader() async throws -> String {
        try await myServer.fetchMossToken()
    }
}

let client = try MossClient(projectId: id, authenticator: MyAuth())
```
