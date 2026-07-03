import AppKit
import QuartzCore
import SwiftUI
import Combine

@MainActor
final class PetStateController: ObservableObject {
    @Published var state: PetState = .idle
    @Published var interaction: PetInteraction = .standing
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
    private let momentumFactor: CGFloat = 0.22
    private let slideDuration: TimeInterval = 0.38
    private var slideTimer: Timer?
    private var slideStartTime: CFTimeInterval = 0
    private var slideFrom: NSPoint = .zero
    private var slideTo: NSPoint = .zero
    private var isSliding = false

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
        hosting.wantsLayer = true
        hosting.layer?.backgroundColor = NSColor.clear.cgColor
        hostingView = hosting

        let container = PetWindowContentView(frame: NSRect(x: 0, y: 0, width: petSize, height: petSize))
        container.wantsLayer = true
        container.layer?.backgroundColor = NSColor.clear.cgColor
        container.onClick = { [weak self] in
            DispatchQueue.main.async {
                self?.onPetClicked?()
            }
        }
        container.onRightClick = { [weak self] location in
            self?.showContextMenu(at: location, in: container)
        }
        container.onDragBegan = { [weak self] in
            self?.handleDragBegan()
        }
        container.onDragEnded = { [weak self] velocity in
            self?.handleDragEnded(velocity: velocity)
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

    private func handleDragBegan() {
        cancelSlideAnimation()
        petStateController.interaction = .dragging
    }

    private func handleDragEnded(velocity: CGVector) {
        guard let screen = NSScreen.screens.first(where: { $0.frame.contains(panel.frame.origin) }) ?? NSScreen.main else {
            petStateController.interaction = .standing
            savePosition()
            return
        }

        let current = panel.frame.origin
        let momentumTarget = NSPoint(
            x: current.x + velocity.dx * momentumFactor,
            y: current.y + velocity.dy * momentumFactor
        )
        let target = clampedOrigin(momentumTarget, on: screen)
        animateSlide(from: current, to: target)
    }

    private func animateSlide(from start: NSPoint, to target: NSPoint) {
        cancelSlideAnimation()

        let distance = hypot(target.x - start.x, target.y - start.y)
        if distance < 0.5 {
            panel.setFrameOrigin(target)
            petStateController.interaction = .standing
            savePosition()
            return
        }

        slideFrom = start
        slideTo = target
        slideStartTime = CACurrentMediaTime()
        isSliding = true
        petStateController.interaction = .sliding

        slideTimer = Timer.scheduledTimer(withTimeInterval: 1.0 / 60.0, repeats: true) { [weak self] timer in
            guard let self else {
                timer.invalidate()
                return
            }
            self.tickSlide(timer: timer)
        }
        if let slideTimer {
            RunLoop.main.add(slideTimer, forMode: .common)
        }
    }

    private func tickSlide(timer: Timer) {
        let elapsed = CACurrentMediaTime() - slideStartTime
        let progress = min(1.0, elapsed / slideDuration)
        let eased = 1 - pow(1 - progress, 3)

        let x = slideFrom.x + (slideTo.x - slideFrom.x) * eased
        let y = slideFrom.y + (slideTo.y - slideFrom.y) * eased
        panel.setFrameOrigin(NSPoint(x: x, y: y))

        guard progress >= 1.0 else { return }

        timer.invalidate()
        slideTimer = nil
        isSliding = false
        panel.setFrameOrigin(slideTo)
        petStateController.interaction = .standing
        savePosition()
    }

    private func cancelSlideAnimation() {
        slideTimer?.invalidate()
        slideTimer = nil
        isSliding = false
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
        PikachuPetView(petStateController: petStateController, size: 72)
    }
}

private struct DragSample {
    let location: NSPoint
    let timestamp: TimeInterval
}

private final class PetWindowContentView: NSView {
    var onClick: (() -> Void)?
    var onRightClick: ((NSPoint) -> Void)?
    var onDragBegan: (() -> Void)?
    var onDragEnded: ((CGVector) -> Void)?

    private var dragStartMouseLocation: NSPoint?
    private var dragStartWindowOrigin: NSPoint?
    private var didDrag = false
    private var dragBeganNotified = false
    private var dragSamples: [DragSample] = []

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool {
        true
    }

    override func mouseDown(with event: NSEvent) {
        dragStartMouseLocation = NSEvent.mouseLocation
        dragStartWindowOrigin = window?.frame.origin
        didDrag = false
        dragBeganNotified = false
        dragSamples = [DragSample(location: NSEvent.mouseLocation, timestamp: event.timestamp)]
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
            if !dragBeganNotified {
                dragBeganNotified = true
                onDragBegan?()
            }
            didDrag = true
        }

        dragSamples.append(DragSample(location: NSEvent.mouseLocation, timestamp: event.timestamp))
        if dragSamples.count > 4 {
            dragSamples.removeFirst(dragSamples.count - 4)
        }

        let origin = NSPoint(
            x: dragStartWindowOrigin.x + delta.x,
            y: dragStartWindowOrigin.y + delta.y
        )
        window.setFrameOrigin(origin)
    }

    override func mouseUp(with event: NSEvent) {
        if didDrag {
            onDragEnded?(estimatedVelocity())
        } else if event.type == .rightMouseUp {
            onRightClick?(event.locationInWindow)
        } else {
            onClick?()
        }
        dragStartMouseLocation = nil
        dragStartWindowOrigin = nil
        didDrag = false
        dragBeganNotified = false
        dragSamples = []
    }

    override func rightMouseDown(with event: NSEvent) {
        onRightClick?(event.locationInWindow)
    }

    private func estimatedVelocity() -> CGVector {
        guard dragSamples.count >= 2 else { return .zero }

        let recent = dragSamples.suffix(2)
        let first = recent[recent.startIndex]
        let last = recent[recent.index(before: recent.endIndex)]

        let dt = last.timestamp - first.timestamp
        guard dt > 0.001 else { return .zero }

        return CGVector(
            dx: (last.location.x - first.location.x) / dt,
            dy: (last.location.y - first.location.y) / dt
        )
    }
}
