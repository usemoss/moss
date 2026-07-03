# macOS Patterns

## Menu bar agent (no Dock icon)

`Info.plist`:
```xml
<key>LSUIElement</key>
<true/>
```

Or build setting: `INFOPLIST_KEY_LSUIElement = YES`

## Search overlay (NSPanel)

- Subclass `NSPanel`, style `.nonactivatingPanel` + `.fullSizeContentView`
- `level = .floating`, `isOpaque = false`, `backgroundColor = .clear`
- `collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]`
- `isMovableByWindowBackground = false`
- Click-outside: global `NSEvent.addLocalMonitorForEvents(matching: .leftMouseDown)`

## Global hotkey (Carbon, no deps)

- Key code `46` = M (US keyboard)
- Modifiers: `cmdKey | shiftKey`
- `RegisterEventHotKey` + `InstallEventHandler` for `kEventHotKeyPressed`

## App Sandbox

Disabled for MVP (`ENABLE_APP_SANDBOX = NO`) — required for:
- FSEvents on ~/Documents, ~/Desktop, ~/Downloads
- Spawning Python subprocess with venv outside bundle

Re-enable with entitlements before App Store distribution.

## Credentials

Read from Keychain service `dev.moss.pikachu` or fall back to environment variables for dev.
