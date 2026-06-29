import SwiftUI

enum SearchMode: String, CaseIterable {
    case results = "Results"
    case answer  = "AI Answer"
}

struct SearchView: View {
    @EnvironmentObject private var store: IndexStore
    @State private var query = ""
    @State private var mode:  SearchMode = .results

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {

                // ── Search bar ────────────────────────────────────────────
                HStack(spacing: 8) {
                    Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                    TextField("Search your documents and contacts…", text: $query)
                        .submitLabel(.search)
                        .onSubmit { triggerSearch() }
                        .onChange(of: query) { _, newValue in
                            if newValue.isEmpty {
                                store.searchHits = []
                                store.llmAnswer  = ""
                            } else {
                                // Live search only in Results mode; Answer needs explicit submit
                                if mode == .results {
                                    Task { await store.search(query: newValue) }
                                }
                            }
                        }
                    if !query.isEmpty {
                        Button { query = "" } label: {
                            Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(10)
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .padding([.horizontal, .top])
                .padding(.bottom, 8)

                // ── Mode picker ───────────────────────────────────────────
                Picker("Mode", selection: $mode) {
                    ForEach(SearchMode.allCases, id: \.self) { m in
                        Text(m.rawValue).tag(m)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.bottom, 8)
                .onChange(of: mode) { _, _ in
                    triggerSearch()
                }

                Divider()

                // ── Content ───────────────────────────────────────────────
                if query.isEmpty {
                    emptyPrompt
                } else {
                    switch mode {
                    case .results: resultsPane
                    case .answer:  answerPane
                    }
                }

                // ── Status bar ────────────────────────────────────────────
                Text(store.status)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .navigationTitle("Personal Context")
        }
    }

    // MARK: - Trigger

    private func triggerSearch() {
        guard !query.isEmpty else { return }
        Task {
            if mode == .results {
                await store.search(query: query)
            } else {
                await store.generateAnswer(query: query)
            }
        }
    }

    // MARK: - Results pane

    private var resultsPane: some View {
        Group {
            if store.searchHits.isEmpty {
                ContentUnavailableView.search(text: query)
            } else {
                List(store.searchHits) { hit in
                    HitRow(hit: hit)
                }
                .listStyle(.plain)
            }
        }
    }

    // MARK: - Answer pane

    private var answerPane: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {

                if !store.hasOpenAI {
                    HStack(spacing: 10) {
                        Image(systemName: "info.circle").foregroundStyle(.orange)
                        Text("Add an OpenAI key in Settings to get AI answers.")
                            .font(.caption)
                    }
                    .padding(10)
                    .background(Color.orange.opacity(0.1))
                    .cornerRadius(8)
                }

                if store.isAnswering {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Retrieving from Moss + generating answer…")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                } else if !store.llmAnswer.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Answer", systemImage: "sparkles")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.purple)
                        Text(store.llmAnswer)
                            .font(.body)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                }

                // Source chunks used as context
                if !store.searchHits.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Sources used (\(store.searchHits.count))")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.secondary)

                        ForEach(Array(store.searchHits.enumerated()), id: \.element.id) { i, hit in
                            HStack(alignment: .top, spacing: 10) {
                                Text("[\(i + 1)]")
                                    .font(.caption2.monospacedDigit())
                                    .foregroundStyle(.secondary)
                                    .frame(width: 24, alignment: .leading)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(hit.sourceName)
                                        .font(.caption.weight(.medium))
                                        .foregroundStyle(.secondary)
                                    Text(hit.excerpt)
                                        .font(.caption)
                                        .lineLimit(3)
                                }
                                Spacer()
                                ScoreBadge(score: hit.score)
                            }
                            .padding(8)
                            .background(Color(.systemGray6))
                            .cornerRadius(8)
                        }
                    }
                }
            }
            .padding()
        }
    }

    // MARK: - Subviews

    private var emptyPrompt: some View {
        ContentUnavailableView(
            "What do you want to find?",
            systemImage: "sparkle.magnifyingglass",
            description: Text("Search for topics, names, or ideas across your files and contacts.")
        )
    }

}

// MARK: - Hit row

struct HitRow: View {
    let hit: SearchHit

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(hit.sourceName)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                ScoreBadge(score: hit.score)
            }
            Text(hit.excerpt)
                .font(.body)
                .lineLimit(4)
        }
        .padding(.vertical, 4)
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
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }

    private var color: Color {
        switch score {
        case 0.8...: return .green
        case 0.5...: return .orange
        default:     return .secondary
        }
    }
}
