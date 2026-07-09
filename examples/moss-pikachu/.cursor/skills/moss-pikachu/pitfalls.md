# Pitfalls

1. **Do not use Moss Swift SPM on macOS** — `Package.swift` targets iOS only
2. **Do not install Moss from GitHub main SDK** — no `SessionIndex`; use `pip install moss>=1.6.0`
3. **No Python disk save API** — use in-memory session + Swift file manifest for relaunch
4. **FSEvents permissions** — may need Full Disk Access; handle `start()` returning false gracefully
5. **App Sandbox blocks subprocess** — disable sandbox for MVP or add `com.apple.security.cs.allow-unsigned-executable-memory`
6. **Bundle resources** — `moss_worker.py` must be in Copy Bundle Resources; resolve via `Bundle.main.url(forResource:withExtension:)`
7. **@MainActor default** — Xcode 26 sets `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor`; mark background work `nonisolated` or use `Task.detached`
8. **Carbon hotkey in sandbox** — works without sandbox; test on real hardware not just simulator
