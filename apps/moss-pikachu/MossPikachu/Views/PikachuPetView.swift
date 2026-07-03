import SwiftUI

struct PikachuPetView: View {
    let petState: PetState
    var size: CGFloat = 64

    @State private var breatheScale: CGFloat = 1.0
    @State private var tailRotation: Double = 0
    @State private var headTilt: Double = 0
    @State private var bounceScale: CGFloat = 1.0
    @State private var isBlinking = false
    @State private var thinkingDots = ""
    @State private var showSparkles = false
    @State private var isHovered = false
    @State private var isSearchingAnimation = false

    var body: some View {
        ZStack {
            if showSparkles {
                HStack(spacing: 4) {
                    Text("✨")
                    Text("✨")
                }
                .offset(y: -size * 0.6)
                .transition(.scale.combined(with: .opacity))
            }

            CapvoltStickerImage(size: size)
                .scaleEffect(bounceScale * breatheScale * (isHovered ? 1.05 : 1.0))
                .rotationEffect(.degrees(headTilt))
                .opacity(isBlinking ? 0.35 : 1.0)
                .rotationEffect(.degrees(tailRotation), anchor: .bottomTrailing)

            if petState == .searching {
                Text(thinkingDots)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .offset(y: size * 0.55)
            }

            if petState == .notFound {
                Text("😢")
                    .font(.system(size: size * 0.22))
                    .offset(y: size * 0.38)
            }
        }
        .frame(width: size, height: size)
        .onHover { isHovered = $0 }
        .onAppear { startIdleAnimations() }
        .onChange(of: petState) { newState in
            applyState(newState)
        }
        .animation(.easeInOut(duration: 0.3), value: petState)
    }

    private func startIdleAnimations() {
        withAnimation(.easeInOut(duration: 2).repeatForever(autoreverses: true)) {
            breatheScale = 1.02
        }
        scheduleBlink()
        scheduleTailTwitch()
        applyState(petState)
    }

    private func applyState(_ state: PetState) {
        switch state {
        case .idle:
            isSearchingAnimation = false
            showSparkles = false
            headTilt = 0
            tailRotation = 0
            withAnimation(.easeInOut(duration: 2).repeatForever(autoreverses: true)) {
                breatheScale = 1.02
            }
        case .searching:
            isSearchingAnimation = true
            showSparkles = false
            withAnimation(.easeInOut(duration: 0.6).repeatForever(autoreverses: true)) {
                tailRotation = 12
            }
            scheduleThinkingDots()
        case .found:
            isSearchingAnimation = false
            tailRotation = 0
            celebrate()
        case .notFound:
            isSearchingAnimation = false
            showSparkles = false
            withAnimation(.easeInOut(duration: 1).repeatForever(autoreverses: true)) {
                headTilt = 8
            }
        }
    }

    private func celebrate() {
        withAnimation(.spring(response: 0.4, dampingFraction: 0.5)) {
            bounceScale = 1.15
            showSparkles = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.5)) {
                bounceScale = 1.0
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            showSparkles = false
        }
    }

    private func scheduleBlink() {
        let delay = Double.random(in: 5...8)
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            withAnimation(.easeInOut(duration: 0.15)) { isBlinking = true }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                withAnimation(.easeInOut(duration: 0.15)) { isBlinking = false }
                scheduleBlink()
            }
        }
    }

    private func scheduleTailTwitch() {
        let delay = Double.random(in: 3...5)
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            withAnimation(.easeInOut(duration: 0.3)) { tailRotation = 2 }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                withAnimation(.easeInOut(duration: 0.3)) { tailRotation = -2 }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    tailRotation = 0
                    scheduleTailTwitch()
                }
            }
        }
    }

    private func scheduleThinkingDots() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            guard isSearchingAnimation else {
                thinkingDots = ""
                return
            }
            switch thinkingDots {
            case "": thinkingDots = "."
            case ".": thinkingDots = ".."
            case "..": thinkingDots = "..."
            default: thinkingDots = ""
            }
            scheduleThinkingDots()
        }
    }
}
