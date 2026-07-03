import AppKit
import SwiftUI

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

        let toastView = HStack(spacing: 8) {
            Image(systemName: isError ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
                .foregroundStyle(isError ? .orange : .green)
            Text(message)
                .font(.subheadline)
                .lineLimit(2)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .shadow(radius: 8)

        let hosting = NSHostingView(rootView: toastView)
        hosting.frame.size = hosting.fittingSize

        let panel = NSPanel(
            contentRect: NSRect(origin: .zero, size: hosting.frame.size),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.level = .statusBar
        panel.contentView = hosting
        panel.hasShadow = false

        if let screen = NSScreen.main {
            let x = screen.visibleFrame.maxX - hosting.frame.width - 20
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
