import AppKit
import Foundation

enum CapvoltAnimation: String, CaseIterable, Sendable {
    case idle
    case wave
    case run
    case failed
    case review
    case jump
    case extra1
    case extra2

    nonisolated var row: Int {
        0
    }

    nonisolated static func forPetState(_ state: PetState) -> CapvoltAnimation {
        resolvedAnimation(searchState: state, interaction: .standing, isHovered: false)
    }

    nonisolated static func resolvedAnimation(
        searchState: PetState,
        interaction: PetInteraction,
        isHovered: Bool
    ) -> CapvoltAnimation {
        .idle
    }

    nonisolated var frameDuration: TimeInterval {
        1.0 / 5.0
    }

    nonisolated var frameCount: Int {
        CapvoltPetAssets.calmStripFrameCount
    }
}

nonisolated enum CapvoltPetAssets {
    static let frameWidth: CGFloat = 192
    static let frameHeight: CGFloat = 208
    static let columns: Int = 8
    static let rows: Int = 9
    static let framesPerRow: Int = 8
    static let calmStripFrameCount: Int = 6
    static let frameDuration: TimeInterval = 1.0 / 6.0

    private static let bundleSubdirectory = "pets/capvolt"

    nonisolated static var isAvailable: Bool {
        spritesheetURL() != nil
    }

    nonisolated static func spritesheetURL() -> URL? {
        if let url = Bundle.main.url(forResource: "spritesheet", withExtension: "webp", subdirectory: bundleSubdirectory) {
            return url
        }
        if let url = Bundle.main.url(forResource: "spritesheet", withExtension: "webp") {
            return url
        }
        let devPath = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Resources/pets/capvolt/spritesheet.webp")
        return FileManager.default.fileExists(atPath: devPath.path) ? devPath : nil
    }

    nonisolated static func loadSpritesheet() -> NSImage? {
        guard let url = spritesheetURL() else { return nil }
        return NSImage(contentsOf: url)
    }

    nonisolated static func standingFrame() -> NSImage? {
        guard let image = loadSpritesheet() else { return nil }
        return croppedFrame(from: image, column: 0, row: 0)
    }

    nonisolated static func frameRect(column: Int, row: Int) -> CGRect {
        CGRect(
            x: CGFloat(column) * frameWidth,
            y: CGFloat(row) * frameHeight,
            width: frameWidth,
            height: frameHeight
        )
    }

    nonisolated static func croppedFrame(from image: NSImage, column: Int, row: Int) -> NSImage? {
        let source = CGRect(
            x: CGFloat(column) * frameWidth,
            y: image.size.height - CGFloat(row + 1) * frameHeight,
            width: frameWidth,
            height: frameHeight
        )
        guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil)?
            .cropping(to: source) else {
            return nil
        }
        return NSImage(cgImage: cgImage, size: NSSize(width: frameWidth, height: frameHeight))
    }
}
