import AppKit

@MainActor
final class NotificationManager {
    static let shared = NotificationManager()

    private var toastWindow: NSPanel?

    func showError(_ message: String) {
        showToast(message, duration: 3, isError: true)
    }

    func showSuccess(_ message: String) {
        showToast(message, duration: 1, isError: false)
    }

    private func showToast(_ message: String, duration: TimeInterval, isError: Bool) {
        toastWindow?.orderOut(nil)

        let toastView = ToastView(message: message, isError: isError)
        let size = toastView.fittingSize

        let panel = NSPanel(
            contentRect: NSRect(origin: .zero, size: size),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.level = .statusBar
        panel.contentView = toastView
        panel.hasShadow = false

        if let screen = NSScreen.main {
            let x = screen.visibleFrame.maxX - size.width - 20
            let y = screen.visibleFrame.minY + 20
            panel.setFrameOrigin(NSPoint(x: x, y: y))
        }

        panel.orderFrontRegardless()
        toastWindow = panel

        DispatchQueue.main.asyncAfter(deadline: .now() + duration) { [weak self] in
            self?.toastWindow?.orderOut(nil)
            self?.toastWindow = nil
        }
    }
}

private final class ToastView: NSVisualEffectView {
    private let iconView = NSImageView()
    private let label = NSTextField(labelWithString: "")

    init(message: String, isError: Bool) {
        super.init(frame: NSRect(x: 0, y: 0, width: 320, height: 52))
        material = .hudWindow
        blendingMode = .behindWindow
        state = .active
        wantsLayer = true
        layer?.cornerRadius = 12
        layer?.masksToBounds = true

        iconView.image = NSImage(
            systemSymbolName: isError ? "exclamationmark.triangle.fill" : "checkmark.circle.fill",
            accessibilityDescription: nil
        )
        iconView.contentTintColor = isError ? .systemOrange : .systemGreen
        iconView.translatesAutoresizingMaskIntoConstraints = false

        label.stringValue = message
        label.font = .systemFont(ofSize: 13)
        label.textColor = .labelColor
        label.lineBreakMode = .byTruncatingTail
        label.maximumNumberOfLines = 2
        label.translatesAutoresizingMaskIntoConstraints = false

        addSubview(iconView)
        addSubview(label)

        NSLayoutConstraint.activate([
            iconView.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 14),
            iconView.centerYAnchor.constraint(equalTo: centerYAnchor),
            iconView.widthAnchor.constraint(equalToConstant: 18),
            iconView.heightAnchor.constraint(equalToConstant: 18),

            label.leadingAnchor.constraint(equalTo: iconView.trailingAnchor, constant: 9),
            label.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -14),
            label.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override var fittingSize: NSSize {
        NSSize(width: 320, height: 52)
    }
}
