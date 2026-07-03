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

    private var showResultsArea: Bool {
        !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private var preferredHeight: CGFloat {
        guard showResultsArea else { return 56 }
        let resultRows = max(1, min(results.count, 4))
        let base: CGFloat = 56
        let statusLine: CGFloat = 22
        let rowHeight: CGFloat = 52
        if isSearching || results.isEmpty {
            return base + statusLine + 44
        }
        return base + statusLine + CGFloat(resultRows) * rowHeight + 8
    }

    var body: some View {
        VStack(spacing: 0) {
            searchBar

            if showResultsArea {
                Divider()
                    .padding(.horizontal, 12)

                statusLine
                    .padding(.horizontal, 16)
                    .padding(.top, 6)

                ResultsListView(
                    results: results,
                    selectedIndex: keyboardBridge.selectedIndex,
                    isSearching: isSearching,
                    query: query,
                    compact: true,
                    onResultTapped: openResult,
                    onResultHovered: { keyboardBridge.selectedIndex = $0 }
                )
            }
        }
        .frame(width: 520)
        .background(
            RoundedRectangle(cornerRadius: 14)
                .fill(.ultraThinMaterial)
                .shadow(color: .black.opacity(0.18), radius: 16, y: 6)
        )
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .onAppear {
            syncKeyboardBridge()
            onHeightChange(preferredHeight)
        }
        .onChange(of: presentation.clearQueryToken) { _ in
            query = ""
            results = []
            isSearching = false
            presentation.keyboardBridge.resetSelection()
            lastSearchTimingMs = 0
            onHeightChange(preferredHeight)
        }
        .onChange(of: query) { newValue in
            performSearch(query: newValue)
            onHeightChange(preferredHeight)
        }
        .onChange(of: results.count) { _ in
            syncKeyboardBridge()
            onHeightChange(preferredHeight)
        }
        .onChange(of: keyboardBridge.selectedIndex) { _ in
            onHeightChange(preferredHeight)
        }
        .onChange(of: isSearching) { searching in
            onHeightChange(preferredHeight)
            if searching {
                onPetStateChanged(.searching)
            }
        }
        .onExitCommand {
            onClose()
        }
    }

    @ViewBuilder
    private var statusLine: some View {
        if searchService.isIndexing {
            Text("Indexing files...")
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        } else if isSearching {
            Text("Searching...")
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        } else if lastSearchTimingMs > 0, !results.isEmpty {
            Text("Found in \(String(format: "%.0f", lastSearchTimingMs))ms")
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        } else if showResultsArea && !isSearching && results.isEmpty {
            Text("No matching files found")
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var searchBar: some View {
        HStack(spacing: 10) {
            CapvoltStickerImage(size: 28)

            SearchTextField(
                text: $query,
                placeholder: "Find me a logo on my computer...",
                focusToken: presentation.focusToken,
                onSubmit: {
                    if !results.isEmpty {
                        openResult(results[keyboardBridge.selectedIndex])
                    }
                }
            )
            .frame(maxWidth: .infinity)

            Button(action: onClose) {
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(.secondary)
                    .font(.body)
            }
            .buttonStyle(.plain)
            .help("Close (Esc)")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
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
            results = []
            isSearching = false
            presentation.keyboardBridge.resetSelection()
            lastSearchTimingMs = 0
            onPetStateChanged(.idle)
            return
        }

        isSearching = true

        searchTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 200_000_000)
            guard !Task.isCancelled else { return }

            do {
                let searchResults = try await searchService.search(trimmed)
                guard !Task.isCancelled else { return }
                results = searchResults
                presentation.keyboardBridge.resetSelection()
                syncKeyboardBridge()
                isSearching = false
                lastSearchTimingMs = searchResults.first?.timingMs ?? 0
                if searchResults.isEmpty {
                    onPetStateChanged(.notFound)
                } else {
                    onPetStateChanged(.found(searchResults.count))
                }
            } catch {
                guard !Task.isCancelled else { return }
                isSearching = false
                onPetStateChanged(.idle)
                NotificationManager.shared.showError(error.localizedDescription)
            }
        }
    }

    private func openResult(_ result: SearchResult) {
        let url = URL(fileURLWithPath: result.path)
        if FileManager.default.fileExists(atPath: result.path) {
            NSWorkspace.shared.open(url)
            onClose()
        } else {
            NotificationManager.shared.showError("File no longer exists: \(result.filename)")
        }
    }
}

struct SearchTextField: NSViewRepresentable {
    @Binding var text: String
    var placeholder: String
    var focusToken: UUID
    var onSubmit: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeNSView(context: Context) -> NSTextField {
        let field = SearchInputTextField(string: "")
        field.target = context.coordinator
        field.action = #selector(Coordinator.submit(_:))
        field.isBordered = false
        field.drawsBackground = false
        field.focusRingType = NSFocusRingType.none
        field.font = NSFont.systemFont(ofSize: NSFont.systemFontSize)
        field.placeholderString = placeholder
        field.delegate = context.coordinator
        field.isEditable = true
        field.isSelectable = true
        field.lineBreakMode = NSLineBreakMode.byTruncatingTail
        field.cell?.truncatesLastVisibleLine = true
        return field
    }

    func updateNSView(_ nsView: NSTextField, context: Context) {
        context.coordinator.parent = self

        if nsView.stringValue != text {
            nsView.stringValue = text
        }
        if nsView.placeholderString != placeholder {
            nsView.placeholderString = placeholder
        }

        context.coordinator.scheduleFocus(for: nsView, token: focusToken)
    }

    final class Coordinator: NSObject, NSTextFieldDelegate {
        var parent: SearchTextField
        private var lastFocusToken = UUID()

        init(parent: SearchTextField) {
            self.parent = parent
        }

        func scheduleFocus(for field: NSTextField, token: UUID) {
            guard token != lastFocusToken else { return }
            lastFocusToken = token

            focus(field)
            DispatchQueue.main.async { self.focus(field) }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { self.focus(field) }
        }

        private func focus(_ field: NSTextField) {
            guard let window = field.window else { return }
            NSApp.activate(ignoringOtherApps: true)
            window.makeKeyAndOrderFront(nil)
            window.makeFirstResponder(field)
            field.currentEditor()?.selectedRange = NSRange(location: field.stringValue.count, length: 0)
        }

        @objc func submit(_ sender: NSTextField) {
            parent.onSubmit()
        }

        func controlTextDidChange(_ obj: Notification) {
            guard let field = obj.object as? NSTextField else { return }
            parent.text = field.stringValue
        }
    }
}

private final class SearchInputTextField: NSTextField {
    override var acceptsFirstResponder: Bool { true }
}
