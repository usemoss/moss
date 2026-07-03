import AppKit
import SwiftUI

@MainActor
final class SearchOverlayController: NSObject {
    private let panel: SearchOverlayPanel
    private let searchService: SearchService
    private let presentation: SearchOverlayPresentation
    private let anchorProvider: () -> NSRect?
    private var hostingView: NSHostingView<SearchOverlayView>?
    private var localEventMonitor: Any?
    private var globalEventMonitor: Any?
    private var keyEventMonitor: Any?
    private var isVisible = false

    var onClose: (() -> Void)?
    var onPetStateChanged: ((PetState) -> Void)?

    private let panelWidth: CGFloat = 520
    private let collapsedHeight: CGFloat = 56
    private let maxExpandedHeight: CGFloat = 320

    init(
        searchService: SearchService,
        presentation: SearchOverlayPresentation,
        anchorProvider: @escaping () -> NSRect?
    ) {
        self.searchService = searchService
        self.presentation = presentation
        self.anchorProvider = anchorProvider

        panel = SearchOverlayPanel(
            contentRect: NSRect(x: 0, y: 0, width: 520, height: 56),
            styleMask: [.borderless, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )

        super.init()

        configurePanel()
        let contentView = SearchOverlayView(
            searchService: searchService,
            presentation: presentation,
            onClose: { [weak self] in self?.hide() },
            onHeightChange: { [weak self] height in
                self?.updatePanelHeight(height)
            },
            onPetStateChanged: { [weak self] state in
                self?.onPetStateChanged?(state)
            }
        )
        let hosting = NSHostingView(rootView: contentView)
        hostingView = hosting
        panel.contentView = hosting
    }

    private func configurePanel() {
        panel.isFloatingPanel = true
        panel.level = .popUpMenu
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.isMovableByWindowBackground = false
        panel.hidesOnDeactivate = false
        panel.becomesKeyOnlyIfNeeded = false
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
    }

    func toggle() {
        if isVisible {
            hide()
        } else {
            show()
        }
    }

    func show() {
        if !isVisible {
            presentation.requestClearQuery()
        }
        updatePanelHeight(collapsedHeight)
        positionBelowAnchor()
        isVisible = true
        NSApp.activate(ignoringOtherApps: true)
        panel.makeKeyAndOrderFront(nil)
        installClickOutsideMonitor()
        installKeyEventMonitor()
        focusSearchField()
    }

    func focusSearchField() {
        presentation.requestFocus()
        NSApp.activate(ignoringOtherApps: true)
        panel.makeKeyAndOrderFront(nil)
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            NSApp.activate(ignoringOtherApps: true)
            self.panel.makeKeyAndOrderFront(nil)
            self.presentation.requestFocus()
        }
    }

    var isSearchVisible: Bool {
        isVisible
    }

    func hide() {
        panel.orderOut(nil)
        isVisible = false
        removeClickOutsideMonitor()
        removeKeyEventMonitor()
        onPetStateChanged?(.idle)
        onClose?()
    }

    private func updatePanelHeight(_ contentHeight: CGFloat) {
        let height = min(max(contentHeight, collapsedHeight), maxExpandedHeight)
        var frame = panel.frame
        let oldMaxY = frame.maxY
        frame.size = NSSize(width: panelWidth, height: height)
        frame.origin.y = oldMaxY - height
        panel.setFrame(frame, display: true, animate: false)
        if isVisible {
            positionBelowAnchor()
        }
    }

    private func positionBelowAnchor() {
        if let anchor = anchorProvider(), anchor != .zero {
            let x = anchor.midX - panelWidth / 2
            let y = anchor.minY - panel.frame.height - 8
            panel.setFrameOrigin(NSPoint(x: x, y: y))
            return
        }

        guard let screen = NSScreen.main else { return }
        let screenFrame = screen.visibleFrame
        let x = screenFrame.midX - panelWidth / 2
        let y = screenFrame.maxY - panel.frame.height - 12
        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }

    private func installClickOutsideMonitor() {
        removeClickOutsideMonitor()

        localEventMonitor = NSEvent.addLocalMonitorForEvents(matching: .leftMouseDown) { [weak self] event in
            guard let self, self.isVisible else { return event }
            if self.shouldDismissForClick(at: NSEvent.mouseLocation) {
                self.hide()
            }
            return event
        }

        globalEventMonitor = NSEvent.addGlobalMonitorForEvents(matching: .leftMouseDown) { [weak self] _ in
            guard let self, self.isVisible else { return }
            if self.shouldDismissForClick(at: NSEvent.mouseLocation) {
                self.hide()
            }
        }
    }

    private func shouldDismissForClick(at screenPoint: NSPoint) -> Bool {
        if panel.frame.contains(screenPoint) {
            return false
        }
        if let anchor = anchorProvider(), anchor.contains(screenPoint) {
            return false
        }
        return true
    }

    private func installKeyEventMonitor() {
        removeKeyEventMonitor()

        keyEventMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self, self.isVisible else { return event }
            if self.presentation.keyboardBridge.handleKeyDown(event) {
                return nil
            }
            return event
        }
    }

    private func removeKeyEventMonitor() {
        if let keyEventMonitor {
            NSEvent.removeMonitor(keyEventMonitor)
            self.keyEventMonitor = nil
        }
    }

    private func removeClickOutsideMonitor() {
        if let localEventMonitor {
            NSEvent.removeMonitor(localEventMonitor)
            self.localEventMonitor = nil
        }
        if let globalEventMonitor {
            NSEvent.removeMonitor(globalEventMonitor)
            self.globalEventMonitor = nil
        }
    }
}

private final class SearchOverlayPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}
