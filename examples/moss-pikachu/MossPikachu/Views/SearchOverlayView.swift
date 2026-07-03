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
    @State private var lastSearchTimingMs: Double = 0
    @State private var searchTask: Task<Void, Never>?
    @FocusState private var isSearchFocused: Bool

    private let panelWidth: CGFloat = 720
    private let panelHeight: CGFloat = 520

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

    var body: some View {
        VStack(spacing: 0) {
            searchHeader

            Divider()
                .padding(.horizontal, 18)

            contentArea

            Divider()
                .padding(.horizontal, 18)

            footer
        }
        .frame(width: panelWidth, height: panelHeight)
        .background(
            RoundedRectangle(cornerRadius: 22)
                .fill(.ultraThinMaterial)
                .shadow(color: .black.opacity(0.28), radius: 28, y: 18)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 22)
                .stroke(Color.white.opacity(0.16), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 22))
        .onAppear {
            syncKeyboardBridge()
            onHeightChange(panelHeight)
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
        }
        .onChange(of: isSearching) { searching in
            onPetStateChanged(searching ? .searching : .idle)
        }
        .onExitCommand {
            onClose()
        }
    }

    private var searchHeader: some View {
        HStack(spacing: 14) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 24, weight: .medium))
                .foregroundColor(.secondary)
                .frame(width: 30)

            TextField("Search your files...", text: $query)
                .textFieldStyle(.plain)
                .font(.system(size: 27, weight: .regular))
                .focused($isSearchFocused)
                .onSubmit {
                    openSelectedResult()
                }

            if searchService.isIndexing {
                ProgressView()
                    .controlSize(.small)
                    .help(searchService.statusMessage)
            }

            Button(action: onClose) {
                Image(systemName: "xmark.circle.fill")
                    .font(.title3)
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
            .help("Close (Esc)")
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 20)
    }

    @ViewBuilder
    private var contentArea: some View {
        if trimmedQuery.isEmpty {
            emptyState
        } else if isSearching {
            searchingState
        } else if results.isEmpty {
            noResultsState
        } else {
            ResultsListView(
                results: results,
                selectedIndex: keyboardBridge.selectedIndex,
                isSearching: isSearching,
                query: query,
                onResultTapped: openResult,
                onResultHovered: { keyboardBridge.selectedIndex = $0 }
            )
        }
    }

    private var emptyState: some View {
        VStack(spacing: 18) {
            CapvoltStickerImage(size: 70)

            VStack(spacing: 8) {
                Text("Pikachu Spotlight")
                    .font(.title3)
                    .fontWeight(.semibold)

                Text("Search ~/Downloads/\(IndexingPolicy.testScopeFolderName) with your local Moss session.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 430)
            }

            if searchService.isIndexing {
                Label(searchService.statusMessage, systemImage: "arrow.triangle.2.circlepath")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                Label("\(searchService.indexedFileCount) files indexed locally", systemImage: "internaldrive")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(28)
    }

    private var searchingState: some View {
        VStack(spacing: 14) {
            ProgressView()
                .controlSize(.regular)
            Text("Searching locally...")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var noResultsState: some View {
        VStack(spacing: 10) {
            Image(systemName: "doc.text.magnifyingglass")
                .font(.system(size: 38))
                .foregroundColor(.secondary)
            Text("No matching files")
                .font(.headline)
            Text("Try a broader description or check that the folder is enabled in Settings.")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(28)
    }

    private var footer: some View {
        HStack(spacing: 14) {
            footerShortcut("↑↓", "Select")
            footerShortcut("Return", "Open")
            footerShortcut("Esc", "Close")

            Spacer()

            statusSummary
        }
        .font(.caption)
        .foregroundColor(.secondary)
        .padding(.horizontal, 22)
        .padding(.vertical, 12)
    }

    private func footerShortcut(_ key: String, _ label: String) -> some View {
        HStack(spacing: 5) {
            Text(key)
                .font(.caption2)
                .fontWeight(.semibold)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(Color.primary.opacity(0.08))
                .cornerRadius(5)
            Text(label)
        }
    }

    @ViewBuilder
    private var statusSummary: some View {
        if isSearching {
            Text("Local query")
        } else if lastSearchTimingMs > 0, !results.isEmpty {
            Text("\(results.count) results in \(String(format: "%.0f", lastSearchTimingMs))ms")
        } else if searchService.lastSessionPushDate != nil {
            Text(searchService.sessionStatusMessage)
        } else {
            Text(searchService.statusMessage)
        }
    }

    private func clearSearch() {
        searchTask?.cancel()
        query = ""
        results = []
        isSearching = false
        lastSearchTimingMs = 0
        presentation.keyboardBridge.resetSelection()
        syncKeyboardBridge()
        onPetStateChanged(.idle)
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
                lastSearchTimingMs = searchResults.first?.timingMs ?? 0
                onPetStateChanged(searchResults.isEmpty ? .notFound : .found(searchResults.count))
            } catch {
                guard !Task.isCancelled else { return }
                isSearching = false
                onPetStateChanged(.idle)
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
