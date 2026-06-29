import SwiftUI

struct SearchView: View {
    @EnvironmentObject private var store: IndexStore
    @State private var query = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {

                // ── Search bar ────────────────────────────────────────────
                HStack(spacing: 8) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(.secondary)
                    TextField("Search your documents and contacts…", text: $query)
                        .submitLabel(.search)
                        .onChange(of: query) { _, newValue in
                            Task { await store.search(query: newValue) }
                        }
                    if !query.isEmpty {
                        Button { query = "" } label: {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(10)
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .padding()

                // ── Results ───────────────────────────────────────────────
                if query.isEmpty {
                    emptyPrompt
                } else if store.searchHits.isEmpty {
                    noResults
                } else {
                    resultsList
                }

                // ── Status bar ────────────────────────────────────────────
                Text(store.statusMessage)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal)
                    .padding(.bottom, 4)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .navigationTitle("Personal Context")
        }
    }

    // MARK: - Subviews

    private var emptyPrompt: some View {
        ContentUnavailableView(
            "What do you want to find?",
            systemImage: "sparkle.magnifyingglass",
            description: Text("Ask anything — topics, names, ideas from your files and contacts.")
        )
    }

    private var noResults: some View {
        ContentUnavailableView.search(text: query)
    }

    private var resultsList: some View {
        List(store.searchHits) { hit in
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline) {
                    Text(hit.sourceName)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    ScoreBadge(score: hit.score)
                }
                Text(highlightedExcerpt(hit.excerpt, query: query))
                    .font(.body)
                    .lineLimit(4)
            }
            .padding(.vertical, 4)
        }
        .listStyle(.plain)
    }

    /// Bold the query terms in the excerpt (simple string match).
    private func highlightedExcerpt(_ text: String, query: String) -> AttributedString {
        var result = AttributedString(text)
        let terms = query.split(separator: " ").map(String.init)
        for term in terms {
            var searchRange = result.startIndex..<result.endIndex
            while let range = result[searchRange].range(of: term, options: .caseInsensitive) {
                result[range].font = .body.bold()
                searchRange = range.upperBound..<result.endIndex
            }
        }
        return result
    }
}

// MARK: - Score badge

struct ScoreBadge: View {
    let score: Float

    var body: some View {
        Text(String(format: "%.0f%%", score * 100))
            .font(.caption2.monospacedDigit())
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .background(badgeColor.opacity(0.15))
            .foregroundStyle(badgeColor)
            .clipShape(Capsule())
    }

    private var badgeColor: Color {
        switch score {
        case 0.8...: return .green
        case 0.5...: return .orange
        default:     return .secondary
        }
    }
}

// MARK: - StatusMessage extension for views

extension IndexStore {
    var statusMessage: String { status }
}
