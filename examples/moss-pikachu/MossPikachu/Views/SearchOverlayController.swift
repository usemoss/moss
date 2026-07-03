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

    private let panelWidth: CGFloat = 300
    private var panelHeight: CGFloat = 70

    init(
        searchService: SearchService,
        presentation: SearchOverlayPresentation,
        anchorProvider: @escaping () -> NSRect?
    ) {
        self.searchService = searchService
        self.presentation = presentation
        self.anchorProvider = anchorProvider

        panel = SearchOverlayPanel(
            contentRect: NSRect(x: 0, y: 0, width: 300, height: 70),
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
        panel.hasShadow = false
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
        updatePanelHeight(panelHeight)
        positionNearPet()
        isVisible = true
        onPetStateChanged?(.attentive)
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
        panelHeight = max(contentHeight, 70)
        var frame = panel.frame
        let previousMaxY = frame.maxY
        frame.size = NSSize(width: panelWidth, height: panelHeight)
        frame.origin.y = previousMaxY - panelHeight
        panel.setFrame(frame, display: true, animate: false)
        if isVisible {
            positionNearPet()
        }
    }

    private func positionNearPet() {
        guard let anchor = anchorProvider() else {
            positionFallbackCenter()
            return
        }

        let screen = panel.screen ?? NSScreen.screens.first { $0.frame.contains(anchor.origin) } ?? NSScreen.main
        guard let screen else { return }
        let screenFrame = screen.visibleFrame

        let gap: CGFloat = 10
        var x = anchor.maxX + gap
        var y = anchor.maxY - panelHeight + 8

        if x + panelWidth > screenFrame.maxX - 12 {
            x = anchor.minX - panelWidth - gap
        }
        if y + panelHeight > screenFrame.maxY - 12 {
            y = screenFrame.maxY - panelHeight - 12
        }
        if y < screenFrame.minY + 12 {
            y = screenFrame.minY + 12
        }
        if x < screenFrame.minX + 12 {
            x = screenFrame.minX + 12
        }

        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }

    private func positionFallbackCenter() {
        let screen = panel.screen ?? NSScreen.main
        guard let screen else { return }
        let screenFrame = screen.visibleFrame
        let x = screenFrame.midX - panelWidth / 2
        let y = screenFrame.maxY - panelHeight - (screenFrame.height * 0.2)
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
        if let petFrame = anchorProvider(), petFrame.contains(screenPoint) {
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
