import AppKit
import SwiftUI
import Combine

@MainActor
final class PetStateController: ObservableObject {
    @Published var state: PetState = .idle
}

@MainActor
final class FloatingPetWindowController: NSObject {
    private let panel: NSPanel
    private let petStateController: PetStateController
    private var hostingView: NSHostingView<PetStateObservingView>?
    private var contentView: PetWindowContentView?

    private let petSize: CGFloat = 80
    private let positionKeyX = "MossPikachu.petOriginX"
    private let positionKeyY = "MossPikachu.petOriginY"

    var onPetClicked: (() -> Void)?
    var onShowSettings: (() -> Void)?
    var onQuit: (() -> Void)?

    var screenFrame: NSRect {
        panel.frame
    }

    init(petStateController: PetStateController) {
        self.petStateController = petStateController

        panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 80, height: 80),
            styleMask: [.nonactivatingPanel, .borderless, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )

        super.init()

        configurePanel()
        setupContent()
        restorePosition()
    }

    func show() {
        panel.orderFrontRegardless()
    }

    private func configurePanel() {
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.hidesOnDeactivate = false
        panel.isMovableByWindowBackground = false
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
    }

    private func setupContent() {
        let wrapper = PetStateObservingView(
            petStateController: petStateController
        )

        let hosting = NSHostingView(rootView: wrapper)
        hostingView = hosting

        let container = PetWindowContentView(frame: NSRect(x: 0, y: 0, width: petSize, height: petSize))
        container.onClick = { [weak self] in
            // Defer until after mouseUp so click-outside monitors don't interfere.
            DispatchQueue.main.async {
                self?.onPetClicked?()
            }
        }
        container.onRightClick = { [weak self] location in
            self?.showContextMenu(at: location, in: container)
        }
        container.onDragEnded = { [weak self] in
            self?.clampToVisibleScreen()
            self?.savePosition()
        }
        contentView = container

        container.addSubview(hosting)
        hosting.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            hosting.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            hosting.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            hosting.topAnchor.constraint(equalTo: container.topAnchor),
            hosting.bottomAnchor.constraint(equalTo: container.bottomAnchor),
        ])

        panel.contentView = container
    }

    private func showContextMenu(at location: NSPoint, in view: NSView) {
        let menu = NSMenu()
        let searchItem = NSMenuItem(title: "Search", action: #selector(menuSearch), keyEquivalent: "")
        let settingsItem = NSMenuItem(title: "Settings…", action: #selector(menuSettings), keyEquivalent: ",")
        let quitItem = NSMenuItem(title: "Quit Moss Pikachu", action: #selector(menuQuit), keyEquivalent: "q")
        [searchItem, settingsItem, quitItem].forEach { $0.target = self }
        menu.addItem(searchItem)
        menu.addItem(NSMenuItem.separator())
        menu.addItem(settingsItem)
        menu.addItem(NSMenuItem.separator())
        menu.addItem(quitItem)
        menu.popUp(positioning: nil, at: location, in: view)
    }

    @objc private func menuSearch() {
        onPetClicked?()
    }

    @objc private func menuSettings() {
        onShowSettings?()
    }

    @objc private func menuQuit() {
        onQuit?()
    }

    private func restorePosition() {
        let defaults = UserDefaults.standard
        guard let screen = NSScreen.main else { return }

        let screenFrame = screen.visibleFrame
        let savedX = defaults.object(forKey: positionKeyX) as? CGFloat
        let savedY = defaults.object(forKey: positionKeyY) as? CGFloat

        let origin: NSPoint
        if let savedX, let savedY {
            origin = clampedOrigin(NSPoint(x: savedX, y: savedY), on: screen)
        } else {
            origin = NSPoint(
                x: screenFrame.maxX - petSize - 24,
                y: screenFrame.minY + 24
            )
        }

        panel.setFrameOrigin(origin)
    }

    private func savePosition() {
        let origin = panel.frame.origin
        UserDefaults.standard.set(origin.x, forKey: positionKeyX)
        UserDefaults.standard.set(origin.y, forKey: positionKeyY)
    }

    private func clampToVisibleScreen() {
        guard let screen = NSScreen.main else { return }
        panel.setFrameOrigin(clampedOrigin(panel.frame.origin, on: screen))
    }

    private func clampedOrigin(_ origin: NSPoint, on screen: NSScreen) -> NSPoint {
        let screenFrame = screen.visibleFrame
        let x = min(max(origin.x, screenFrame.minX), screenFrame.maxX - petSize)
        let y = min(max(origin.y, screenFrame.minY), screenFrame.maxY - petSize)
        return NSPoint(x: x, y: y)
    }
}

private struct PetStateObservingView: View {
    @ObservedObject var petStateController: PetStateController

    var body: some View {
        PikachuPetView(petState: petStateController.state, size: 64)
    }
}

private final class PetWindowContentView: NSView {
    var onClick: (() -> Void)?
    var onRightClick: ((NSPoint) -> Void)?
    var onDragEnded: (() -> Void)?

    private var dragStartMouseLocation: NSPoint?
    private var dragStartWindowOrigin: NSPoint?
    private var didDrag = false

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool {
        true
    }

    override func mouseDown(with event: NSEvent) {
        dragStartMouseLocation = NSEvent.mouseLocation
        dragStartWindowOrigin = window?.frame.origin
        didDrag = false
    }

    override func mouseDragged(with event: NSEvent) {
        guard let window,
              let dragStartMouseLocation,
              let dragStartWindowOrigin else {
            return
        }

        let delta = NSPoint(
            x: NSEvent.mouseLocation.x - dragStartMouseLocation.x,
            y: NSEvent.mouseLocation.y - dragStartMouseLocation.y
        )

        if abs(delta.x) > 3 || abs(delta.y) > 3 {
            didDrag = true
        }

        let origin = NSPoint(
            x: dragStartWindowOrigin.x + delta.x,
            y: dragStartWindowOrigin.y + delta.y
        )
        window.setFrameOrigin(origin)
    }

    override func mouseUp(with event: NSEvent) {
        if didDrag {
            onDragEnded?()
        } else if event.type == .rightMouseUp {
            onRightClick?(event.locationInWindow)
        } else {
            onClick?()
        }
        dragStartMouseLocation = nil
        dragStartWindowOrigin = nil
        didDrag = false
    }

    override func rightMouseDown(with event: NSEvent) {
        onRightClick?(event.locationInWindow)
    }
}
