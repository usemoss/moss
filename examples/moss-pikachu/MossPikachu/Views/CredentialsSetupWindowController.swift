import AppKit
import SwiftUI

@MainActor
final class CredentialsSetupWindowController: NSWindowController {
    var onCredentialsSaved: (() -> Void)?

    init() {
        let content = CredentialsSetupView { [weak self] in
            self?.onCredentialsSaved?()
            self?.close()
        }
        let hosting = NSHostingView(rootView: content)
        hosting.frame = NSRect(x: 0, y: 0, width: 420, height: 320)

        let window = NSWindow(
            contentRect: hosting.frame,
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "Picklight Setup"
        window.center()
        window.contentView = hosting

        super.init(window: window)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func show() {
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
