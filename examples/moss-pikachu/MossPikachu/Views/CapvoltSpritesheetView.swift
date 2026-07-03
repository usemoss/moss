import AppKit
import SwiftUI

struct CapvoltSpritesheetView: View {
    let animation: CapvoltAnimation
    var size: CGFloat = 64
    var frameDuration: TimeInterval = CapvoltPetAssets.frameDuration

    @State private var frameIndex = 0
    @State private var timer: Timer?

    private var spritesheet: NSImage? {
        CapvoltPetAssets.loadSpritesheet()
    }

    var body: some View {
        Group {
            if let spritesheet,
               let frame = CapvoltPetAssets.croppedFrame(
                   from: spritesheet,
                   column: frameIndex % animation.frameCount,
                   row: animation.row
               ) {
                Image(nsImage: frame)
                    .resizable()
                    .interpolation(.none)
                    .aspectRatio(contentMode: .fit)
                    .background(Color.clear)
            } else {
                CapvoltStickerImage(size: size)
            }
        }
        .frame(width: size, height: size)
        .background(Color.clear)
        .compositingGroup()
        .onAppear { startAnimation() }
        .onDisappear { stopAnimation() }
        .onChange(of: animation) { _ in
            frameIndex = 0
            restartAnimation()
        }
        .onChange(of: frameDuration) { _ in
            restartAnimation()
        }
    }

    private func startAnimation() {
        stopAnimation()
        timer = Timer.scheduledTimer(withTimeInterval: frameDuration, repeats: true) { _ in
            frameIndex = (frameIndex + 1) % animation.frameCount
        }
        if let timer {
            RunLoop.main.add(timer, forMode: .common)
        }
    }

    private func restartAnimation() {
        startAnimation()
    }

    private func stopAnimation() {
        timer?.invalidate()
        timer = nil
    }
}
