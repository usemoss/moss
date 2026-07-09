import Foundation

enum PetState: Sendable {
    case idle
    case attentive
    case searching
    case found(Int)
    case notFound
}

enum PetInteraction: Sendable {
    case standing
    case hovering
    case dragging
    case sliding
}

extension PetState: Equatable {
    nonisolated static func == (lhs: PetState, rhs: PetState) -> Bool {
        switch (lhs, rhs) {
        case (.idle, .idle), (.attentive, .attentive), (.searching, .searching), (.notFound, .notFound):
            return true
        case (.found(let a), .found(let b)):
            return a == b
        default:
            return false
        }
    }
}
