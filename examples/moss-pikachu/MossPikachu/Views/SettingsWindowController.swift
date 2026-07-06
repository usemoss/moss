import AppKit
import SwiftUI

@MainActor
final class SettingsWindowController {
    private var window: NSWindow?
    private let searchService: SearchService

    init(searchService: SearchService) {
        self.searchService = searchService
    }

    func show() {
        if window == nil {
            let settingsView = SettingsView(searchService: searchService)
            let hostingView = NSHostingView(rootView: settingsView)
            hostingView.frame = NSRect(x: 0, y: 0, width: 420, height: 480)

            window = NSWindow(
                contentRect: hostingView.frame,
                styleMask: [.titled, .closable, .miniaturizable],
                backing: .buffered,
                defer: false
            )
            window?.title = "Picklight Settings"
            window?.contentView = hostingView
            window?.center()
            window?.isReleasedWhenClosed = false
        }

        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
