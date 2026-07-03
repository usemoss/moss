import AppKit
import SwiftUI

struct KeyEventHandler: NSViewRepresentable {
    var shouldHandleKeys: () -> Bool = { true }
    let onKeyDown: (NSEvent) -> Bool

    func makeNSView(context: Context) -> KeyCatcherView {
        let view = KeyCatcherView()
        view.shouldHandleKeys = shouldHandleKeys
        view.onKeyDown = onKeyDown
        return view
    }

    func updateNSView(_ nsView: KeyCatcherView, context: Context) {
        nsView.shouldHandleKeys = shouldHandleKeys
        nsView.onKeyDown = onKeyDown
    }
}

final class KeyCatcherView: NSView {
    var shouldHandleKeys: (() -> Bool)?
    var onKeyDown: ((NSEvent) -> Bool)?

    override var acceptsFirstResponder: Bool { false }

    override func keyDown(with event: NSEvent) {
        guard shouldHandleKeys?() == true, onKeyDown?(event) == true else {
            super.keyDown(with: event)
            return
        }
    }
}
