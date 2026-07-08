import SwiftUI

struct ResultsListView: View {
    let results: [SearchResult]
    let selectedIndex: Int
    let isSearching: Bool
    let query: String
    var compact: Bool = false
    let onResultTapped: (SearchResult) -> Void
    let onResultHovered: (Int) -> Void

    var body: some View {
        Group {
            if query.isEmpty {
                EmptyView()
            } else if isSearching {
                if compact {
                    EmptyView()
                } else {
                    searchingView
                }
            } else if results.isEmpty {
                EmptyView()
            } else {
                resultsScroll
            }
        }
        .frame(maxHeight: compact ? 220 : 400)
        .padding(.horizontal, compact ? 10 : 12)
        .padding(.bottom, compact ? 8 : 12)
    }

    private var searchingView: some View {
        HStack(spacing: 8) {
            ProgressView()
                .controlSize(.small)
            Text("Searching...")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: compact ? 36 : 80, alignment: .leading)
        .padding(.horizontal, compact ? 6 : 0)
    }

    private var resultsScroll: some View {
        ScrollView {
            VStack(spacing: compact ? 4 : 8) {
                ForEach(Array(results.enumerated()), id: \.element.id) { index, result in
                    ResultRowView(
                        result: result,
                        isSelected: index == selectedIndex,
                        compact: compact
                    )
                    .onTapGesture { onResultTapped(result) }
                    .onHover { isHovered in
                        if isHovered { onResultHovered(index) }
                    }
                }
            }
        }
    }
}

struct ResultRowView: View {
    let result: SearchResult
    let isSelected: Bool
    var compact: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 2 : 4) {
            HStack {
                Text(result.filename)
                    .font(compact ? .subheadline : .body)
                    .fontWeight(.semibold)
                    .lineLimit(1)
                Spacer()
                Text(String(format: "%.0fms", result.timingMs))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            if !compact {
                Text(String(result.text.prefix(100)))
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            } else {
                Text(result.path)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
        .padding(compact ? 8 : 12)
        .background(isSelected ? Color.accentColor.opacity(0.15) : Color(.controlBackgroundColor).opacity(0.6))
        .cornerRadius(compact ? 6 : 8)
    }
}
