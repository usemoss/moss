import AppKit
import SwiftUI

@MainActor
final class IndexingBootstrapWindowController: NSWindowController {
    private let searchService: SearchService

    init(searchService: SearchService) {
        self.searchService = searchService
        let content = IndexingBootstrapView(searchService: searchService)
        let hosting = NSHostingView(rootView: content)
        hosting.frame = NSRect(x: 0, y: 0, width: 420, height: 220)

        let window = NSWindow(
            contentRect: hosting.frame,
            styleMask: [.titled, .closable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Moss Pikachu"
        window.titlebarAppearsTransparent = true
        window.isMovableByWindowBackground = true
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

private struct IndexingBootstrapView: View {
    @ObservedObject var searchService: SearchService

    var body: some View {
        VStack(spacing: 16) {
            CapvoltStickerImage(size: 56)

            Text("Indexing your files")
                .font(.title3)
                .fontWeight(.semibold)

            Text("Building your local search index for Documents, Desktop, Downloads, and iCloud Drive. Moss Pikachu will launch when this finishes.")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 8)

            ProgressView()
                .controlSize(.regular)

            Text(searchService.statusMessage)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(2)
                .multilineTextAlignment(.center)

            if searchService.discoveredFileCount > 0 {
                Text("\(searchService.indexedFileCount) / \(searchService.discoveredFileCount) files indexed")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(24)
        .frame(width: 420, height: 220)
    }
}
