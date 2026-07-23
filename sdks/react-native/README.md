# @moss-dev/moss-react-native

React Native / Expo module for [Moss](https://github.com/usemoss/moss) — on-device semantic search.

Closes the gap described in [usemoss/moss#432](https://github.com/usemoss/moss/issues/432).

## Status

| Platform | Support |
|----------|---------|
| **iOS** | Native via `Moss.xcframework` (same binary as the Swift SDK, release `v0.6.2`) |
| **Android** | Stub — throws until Android native builds land ([#411](https://github.com/usemoss/moss/issues/411)) |
| **Expo Go** | Not supported (custom native code; use a [dev client](https://docs.expo.dev/develop/development-builds/introduction/) / `expo prebuild`) |

## Install

```bash
npx expo install @moss-dev/moss-react-native
```

Add the config plugin in `app.json` / `app.config.js`:

```json
{
  "expo": {
    "plugins": ["@moss-dev/moss-react-native"]
  }
}
```

Then regenerate native projects:

```bash
npx expo prebuild
npx pod-install
```

CocoaPods downloads `Moss.xcframework` during `pod install` (checksum-verified against the Swift SDK release).

## Quick start

```tsx
import { MossClient } from '@moss-dev/moss-react-native';

const client = new MossClient(process.env.EXPO_PUBLIC_MOSS_PROJECT_ID!, process.env.EXPO_PUBLIC_MOSS_PROJECT_KEY!);

await client.createIndex('support-docs', [
  { id: '1', text: 'Refunds are processed within 3-5 business days.' },
  { id: '2', text: 'You can track your order on the dashboard.' },
]);

await client.loadIndex('support-docs');
const result = await client.query('support-docs', 'how long do refunds take?');
for (const doc of result.docs) {
  console.log(`[${doc.score.toFixed(3)}] ${doc.text}`);
}

client.close();
```

## API

Mirrors the Node `@moss-dev/moss` client for the core cloud + local query loop:

- `new MossClient(projectId, projectKey)`
- `createIndex(name, docs, options?)`
- `addDocs(name, docs, options?)`
- `loadIndex(name, options?)` / `unloadIndex(name)`
- `query(name, query, options?)`
- `listIndexes()` / `getIndex(name)` / `deleteIndex(name)`
- `close()`
- `MossClient.sdkVersion`
- `MossClient.setModelCacheDir(path)` (optional; iOS defaults to `Library/Caches/moss-models`)

Session / Authenticator APIs from the Swift SDK are intentionally out of scope for this first release.

## Requirements

- Expo SDK 54+ (or a React Native app with Expo Modules)
- iOS 16.4+ (Expo SDK 54+ baseline)
- Xcode 15+
- Apple Silicon Mac for the iOS Simulator (the Moss.xcframework simulator slice is arm64-only)
- A development build / `expo prebuild` — Expo Go is not supported
- Until this package is published to npm, install from a local path or git checkout (`file:…` / `github:…`)

## Development (this monorepo)

```bash
cd sdks/react-native
npm install
npm run build
```

See [`examples/react-native/`](../../examples/react-native/) for a minimal usage sketch.

## License

[BSD 2-Clause](./LICENSE)
