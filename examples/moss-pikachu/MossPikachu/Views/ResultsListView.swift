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
        ScrollView {
            LazyVStack(spacing: 6) {
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
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct ResultRowView: View {
    let result: SearchResult
    let isSelected: Bool
    var compact: Bool = false

    private var fileExtension: String {
        let ext = URL(fileURLWithPath: result.path).pathExtension.uppercased()
        return ext.isEmpty ? "FILE" : ext
    }

    private var snippet: String {
        let cleaned = result.text
            .replacingOccurrences(of: "\n", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return String(cleaned.prefix(160))
    }

    var body: some View {
        HStack(spacing: 12) {
            fileBadge

            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 8) {
                    Text(result.filename)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(.primary)
                        .lineLimit(1)

                    Text(fileExtension)
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 2)
                        .background(Color.primary.opacity(0.06))
                        .cornerRadius(4)

                    Spacer()

                    Text(String(format: "%.0fms", result.timingMs))
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                Text(result.path)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)

                if !snippet.isEmpty {
                    Text(snippet)
                        .font(.caption)
                        .foregroundColor(.secondary.opacity(0.9))
                        .lineLimit(2)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(rowBackground)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isSelected ? Color.accentColor.opacity(0.25) : Color.clear, lineWidth: 1)
        )
        .cornerRadius(12)
        .contentShape(Rectangle())
    }

    private var fileBadge: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 10)
                .fill(isSelected ? Color.accentColor.opacity(0.18) : Color.primary.opacity(0.06))
            Image(systemName: symbolName)
                .font(.system(size: 18, weight: .semibold))
                .foregroundColor(isSelected ? .accentColor : .secondary)
        }
        .frame(width: 42, height: 42)
    }

    private var rowBackground: some View {
        RoundedRectangle(cornerRadius: 12)
            .fill(isSelected ? Color.accentColor.opacity(0.14) : Color(NSColor.controlBackgroundColor).opacity(0.72))
    }

    private var symbolName: String {
        switch URL(fileURLWithPath: result.path).pathExtension.lowercased() {
        case "pdf":
            return "doc.richtext"
        case "md", "txt", "rtf":
            return "doc.text"
        case "html":
            return "globe"
        case "docx":
            return "doc"
        default:
            return "doc"
        }
    }
}
