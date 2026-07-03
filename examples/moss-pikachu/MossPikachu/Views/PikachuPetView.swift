import SwiftUI

struct PikachuPetView: View {
    @ObservedObject var petStateController: PetStateController
    var size: CGFloat = 64

    @State private var bounceScale: CGFloat = 1.0
    @State private var headTilt: Double = 0
    @State private var isHovered = false

    private var searchState: PetState {
        petStateController.state
    }

    private var animation: CapvoltAnimation {
        CapvoltAnimation.resolvedAnimation(
            searchState: searchState,
            interaction: petStateController.interaction,
            isHovered: isHovered
        )
    }

    private var shouldAnimatePet: Bool {
        switch petStateController.interaction {
        case .hovering, .dragging, .sliding:
            return true
        case .standing:
            return false
        }
    }

    var body: some View {
        Group {
            if shouldAnimatePet {
                CapvoltSpritesheetView(
                    animation: animation,
                    size: size,
                    frameDuration: animation.frameDuration
                )
            } else {
                CapvoltStandingImage(size: size)
            }
        }
        .scaleEffect(bounceScale)
        .rotationEffect(.degrees(headTilt))
        .frame(width: size, height: size)
        .background(Color.clear)
        .onHover { hovering in
            isHovered = hovering
            guard searchState == .idle,
                  petStateController.interaction != .dragging,
                  petStateController.interaction != .sliding else {
                return
            }
            petStateController.interaction = hovering ? .hovering : .standing
        }
        .onAppear {
            applyState(searchState)
        }
        .onChange(of: searchState) { newState in
            if newState == .idle {
                if petStateController.interaction != .dragging,
                   petStateController.interaction != .sliding {
                    petStateController.interaction = isHovered ? .hovering : .standing
                }
            } else if petStateController.interaction == .hovering {
                petStateController.interaction = .standing
            }
            applyState(newState)
        }
        .animation(.easeInOut(duration: 0.25), value: searchState)
        .animation(.easeInOut(duration: 0.15), value: petStateController.interaction)
    }

    private func applyState(_ state: PetState) {
        switch state {
        case .idle, .attentive:
            headTilt = 0
        case .searching:
            headTilt = 0
        case .found:
            celebrate()
        case .notFound:
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                headTilt = 6
            }
        }
    }

    private func celebrate() {
        headTilt = 0
        withAnimation(.spring(response: 0.35, dampingFraction: 0.55)) {
            bounceScale = 1.12
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
            withAnimation(.spring(response: 0.35, dampingFraction: 0.55)) {
                bounceScale = 1.0
            }
        }
    }
}

private struct CapvoltStandingImage: View {
    var size: CGFloat

    var body: some View {
        Group {
            if let image = CapvoltPetAssets.standingFrame() {
                Image(nsImage: image)
                    .resizable()
                    .interpolation(.none)
                    .aspectRatio(contentMode: .fit)
            } else {
                CapvoltStickerImage(size: size)
            }
        }
        .frame(width: size, height: size)
        .background(Color.clear)
    }
}
