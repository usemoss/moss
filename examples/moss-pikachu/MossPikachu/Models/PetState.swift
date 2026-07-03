import Foundation

enum PetState: Sendable {
    case idle
    case searching
    case found(Int)
    case notFound
}

extension PetState: Equatable {
    nonisolated static func == (lhs: PetState, rhs: PetState) -> Bool {
        switch (lhs, rhs) {
        case (.idle, .idle), (.searching, .searching), (.notFound, .notFound):
            return true
        case (.found(let a), .found(let b)):
            return a == b
        default:
            return false
        }
    }
}
