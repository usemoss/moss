import AppKit
import SwiftUI

enum CapvoltSticker {
    private static let resourceNames = ["capvolt-sticker", "capvolt-sticker.webp"]

    static func nsImage(size: CGFloat? = nil) -> NSImage? {
        for name in resourceNames {
            for ext in ["png", "webp"] {
                if let url = Bundle.main.url(forResource: name, withExtension: ext),
                   let image = NSImage(contentsOf: url) {
                    return resized(image, to: size)
                }
            }
        }

        // Dev fallback: project root or Resources folder
        let candidates = [
            URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("Resources/capvolt-sticker.png"),
            URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("capvolt-sticker.webp"),
            URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("MossPikachu/Resources/capvolt-sticker.png"),
        ]
        for url in candidates where FileManager.default.fileExists(atPath: url.path) {
            if let image = NSImage(contentsOf: url) {
                return resized(image, to: size)
            }
        }
        return nil
    }

    static var isAvailable: Bool { nsImage() != nil }

    private static func resized(_ image: NSImage, to size: CGFloat?) -> NSImage {
        guard let size, size > 0 else { return image }
        let newImage = NSImage(size: NSSize(width: size, height: size))
        newImage.lockFocus()
        image.draw(
            in: NSRect(x: 0, y: 0, width: size, height: size),
            from: .zero,
            operation: .copy,
            fraction: 1.0,
            respectFlipped: true,
            hints: nil
        )
        newImage.unlockFocus()
        newImage.isTemplate = false
        return newImage
    }
}

struct CapvoltStickerImage: View {
    var size: CGFloat = 64

    var body: some View {
        Group {
            if let nsImage = CapvoltSticker.nsImage(size: size) {
                Image(nsImage: nsImage)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
            } else {
                Text("⚡")
                    .font(.system(size: size * 0.7))
            }
        }
        .frame(width: size, height: size)
    }
}
