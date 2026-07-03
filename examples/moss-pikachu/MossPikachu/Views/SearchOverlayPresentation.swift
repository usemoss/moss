import Foundation
import Combine
import AppKit

@MainActor
final class SearchKeyboardBridge: ObservableObject {
    @Published var selectedIndex = 0
    var hasResults = false
    var resultCount = 0

    func handleKeyDown(_ event: NSEvent) -> Bool {
        guard hasResults, resultCount > 0 else { return false }
        switch event.keyCode {
        case 126:
            selectedIndex = max(0, selectedIndex - 1)
            return true
        case 125:
            selectedIndex = min(resultCount - 1, selectedIndex + 1)
            return true
        case 48:
            selectedIndex = (selectedIndex + 1) % resultCount
            return true
        default:
            return false
        }
    }

    func resetSelection() {
        selectedIndex = 0
    }
}

@MainActor
final class SearchOverlayPresentation: ObservableObject {
    @Published var focusToken = UUID()
    @Published var clearQueryToken = UUID()
    let keyboardBridge = SearchKeyboardBridge()

    func requestFocus() {
        focusToken = UUID()
    }

    func requestClearQuery() {
        clearQueryToken = UUID()
    }
}
