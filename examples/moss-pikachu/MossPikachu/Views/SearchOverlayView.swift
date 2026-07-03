import AppKit
import SwiftUI

struct SearchOverlayView: View {
    @ObservedObject var searchService: SearchService
    @ObservedObject var presentation: SearchOverlayPresentation
    @ObservedObject private var keyboardBridge: SearchKeyboardBridge
    let onClose: () -> Void
    let onHeightChange: (CGFloat) -> Void
    let onPetStateChanged: (PetState) -> Void

    @State private var query = ""
    @State private var results: [SearchResult] = []
    @State private var isSearching = false
    @State private var searchTask: Task<Void, Never>?
    @FocusState private var isSearchFocused: Bool

    private let bubbleWidth: CGFloat = 300
    private let bubbleInputHeight: CGFloat = 54
    private let resultRowHeight: CGFloat = 44
    private let maxVisibleResults = 4

    init(
        searchService: SearchService,
        presentation: SearchOverlayPresentation,
        onClose: @escaping () -> Void,
        onHeightChange: @escaping (CGFloat) -> Void = { _ in },
        onPetStateChanged: @escaping (PetState) -> Void = { _ in }
    ) {
        self.searchService = searchService
        self.presentation = presentation
        _keyboardBridge = ObservedObject(wrappedValue: presentation.keyboardBridge)
        self.onClose = onClose
        self.onHeightChange = onHeightChange
        self.onPetStateChanged = onPetStateChanged
    }

    private var trimmedQuery: String {
        query.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var contentHeight: CGFloat {
        var height = bubbleInputHeight + 24
        if !trimmedQuery.isEmpty {
            if isSearching {
                height += 36
            } else if results.isEmpty {
                height += 40
            } else {
                let visibleCount = min(results.count, maxVisibleResults)
                height += CGFloat(visibleCount) * resultRowHeight + 8
            }
        }
        return height
    }

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            VStack(alignment: .leading, spacing: 0) {
                thoughtBubble

                if !trimmedQuery.isEmpty {
                    if isSearching {
                        thinkingRow
                    } else if results.isEmpty {
                        noResultsRow
                    } else {
                        compactResults
                    }
                }
            }
            .frame(width: bubbleWidth, alignment: .leading)
            .background(
                CloudBubbleShape()
                    .fill(.ultraThinMaterial)
                    .shadow(color: .black.opacity(0.18), radius: 16, y: 8)
            )
            .overlay(
                CloudBubbleShape()
                    .stroke(Color.white.opacity(0.2), lineWidth: 1)
            )

            ThoughtBubbleDots()
                .offset(x: 22, y: 22)
        }
        .padding(.bottom, 22)
        .onAppear {
            syncKeyboardBridge()
            onHeightChange(contentHeight)
            onPetStateChanged(.attentive)
            focusSearchField()
        }
        .onChange(of: presentation.focusToken) { _ in
            focusSearchField()
        }
        .onChange(of: presentation.clearQueryToken) { _ in
            clearSearch()
            focusSearchField()
        }
        .onChange(of: query) { newValue in
            performSearch(query: newValue)
        }
        .onChange(of: results.count) { _ in
            syncKeyboardBridge()
            onHeightChange(contentHeight)
        }
        .onChange(of: isSearching) { searching in
            onHeightChange(contentHeight)
            if searching {
                onPetStateChanged(.searching)
            } else if trimmedQuery.isEmpty {
                onPetStateChanged(.attentive)
            }
        }
        .onExitCommand {
            onClose()
        }
    }

    private var thoughtBubble: some View {
        HStack(spacing: 8) {
            TextField("What are you looking for?", text: $query)
                .textFieldStyle(.plain)
                .font(.system(size: 15))
                .focused($isSearchFocused)
                .onSubmit {
                    openSelectedResult()
                }

            if isSearching {
                ProgressView()
                    .controlSize(.small)
                    .scaleEffect(0.8)
            }
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 13)
    }

    private var thinkingRow: some View {
        HStack(spacing: 8) {
            ProgressView()
                .controlSize(.small)
            Text("Thinking…")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 14)
        .padding(.bottom, 10)
    }

    private var noResultsRow: some View {
        Text("No matches in ~/Downloads/\(IndexingPolicy.testScopeFolderName)")
            .font(.caption)
            .foregroundColor(.secondary)
            .padding(.horizontal, 14)
            .padding(.bottom, 10)
    }

    private var compactResults: some View {
        ResultsListView(
            results: Array(results.prefix(maxVisibleResults)),
            selectedIndex: keyboardBridge.selectedIndex,
            isSearching: isSearching,
            query: query,
            compact: true,
            onResultTapped: openResult,
            onResultHovered: { keyboardBridge.selectedIndex = $0 }
        )
        .frame(height: CGFloat(min(results.count, maxVisibleResults)) * resultRowHeight)
    }

    private func clearSearch() {
        searchTask?.cancel()
        query = ""
        results = []
        isSearching = false
        presentation.keyboardBridge.resetSelection()
        syncKeyboardBridge()
        onHeightChange(contentHeight)
        onPetStateChanged(.attentive)
    }

    private func focusSearchField() {
        isSearchFocused = true
        DispatchQueue.main.async {
            isSearchFocused = true
        }
    }

    private func syncKeyboardBridge() {
        presentation.keyboardBridge.hasResults = !results.isEmpty
        presentation.keyboardBridge.resultCount = results.count
        if presentation.keyboardBridge.selectedIndex >= results.count {
            presentation.keyboardBridge.selectedIndex = max(0, results.count - 1)
        }
    }

    private func performSearch(query: String) {
        searchTask?.cancel()
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            clearSearch()
            return
        }

        isSearching = true
        onPetStateChanged(.searching)

        searchTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 160_000_000)
            guard !Task.isCancelled else { return }

            do {
                let searchResults = try await searchService.search(trimmed)
                guard !Task.isCancelled else { return }
                results = searchResults
                presentation.keyboardBridge.resetSelection()
                syncKeyboardBridge()
                isSearching = false
                onHeightChange(contentHeight)
                onPetStateChanged(searchResults.isEmpty ? .notFound : .found(searchResults.count))
            } catch {
                guard !Task.isCancelled else { return }
                isSearching = false
                onHeightChange(contentHeight)
                onPetStateChanged(.attentive)
                NotificationManager.shared.showError(error.localizedDescription)
            }
        }
    }

    private func openSelectedResult() {
        guard !results.isEmpty else { return }
        let index = min(keyboardBridge.selectedIndex, results.count - 1)
        openResult(results[index])
    }

    private func openResult(_ result: SearchResult) {
        if FileManager.default.fileExists(atPath: result.path) {
            NSWorkspace.shared.open(URL(fileURLWithPath: result.path))
            onClose()
        } else {
            NotificationManager.shared.showError("File no longer exists: \(result.filename)")
        }
    }
}

private struct ThoughtBubbleDots: View {
    var body: some View {
        ZStack {
            Circle()
                .fill(Color(nsColor: .windowBackgroundColor).opacity(0.82))
                .frame(width: 11, height: 11)
                .offset(x: 0, y: 0)

            Circle()
                .fill(Color(nsColor: .windowBackgroundColor).opacity(0.74))
                .frame(width: 7, height: 7)
                .offset(x: -12, y: 10)

            Circle()
                .fill(Color(nsColor: .windowBackgroundColor).opacity(0.62))
                .frame(width: 4, height: 4)
                .offset(x: -22, y: 17)
        }
        .frame(width: 32, height: 28)
    }
}

private struct CloudBubbleShape: Shape {
    func path(in rect: CGRect) -> Path {
        let insetRect = rect.insetBy(dx: 5, dy: 4)
        var path = Path()

        path.addRoundedRect(
            in: insetRect,
            cornerSize: CGSize(width: 24, height: 24)
        )

        let lobes: [(CGFloat, CGFloat, CGFloat)] = [
            (0.18, 0.28, 15),
            (0.38, 0.12, 18),
            (0.62, 0.13, 17),
            (0.82, 0.30, 14),
            (0.22, 0.78, 13),
            (0.72, 0.84, 14),
        ]

        for (x, y, radius) in lobes {
            let center = CGPoint(x: rect.minX + rect.width * x, y: rect.minY + rect.height * y)
            path.addEllipse(in: CGRect(
                x: center.x - radius,
                y: center.y - radius,
                width: radius * 2,
                height: radius * 2
            ))
        }

        return path
    }
}
