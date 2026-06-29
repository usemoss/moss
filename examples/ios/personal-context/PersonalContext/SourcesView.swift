import SwiftUI
import UniformTypeIdentifiers

struct SourcesView: View {
    @EnvironmentObject private var store: IndexStore
    let onSignOut: () -> Void

    @State private var showFilePicker   = false
    @State private var showAddSheet     = false
    @State private var confirmRemove:   IndexedSource? = nil

    var body: some View {
        NavigationStack {
            List {
                // ── Indexed sources ───────────────────────────────────────
                if store.sources.isEmpty {
                    emptyState
                } else {
                    Section("Indexed") {
                        ForEach(store.sources) { source in
                            SourceRow(source: source) {
                                confirmRemove = source
                            }
                        }
                    }
                }

                // ── Add section ───────────────────────────────────────────
                Section("Add sources") {
                    Button {
                        showFilePicker = true
                    } label: {
                        Label("Import files (PDF, TXT)", systemImage: "doc.badge.plus")
                    }

                    Button {
                        Task { await store.ingestContacts() }
                    } label: {
                        Label("Import Contacts", systemImage: "person.2.badge.plus")
                    }
                }
            }
            .navigationTitle("Sources")
            .overlay {
                if store.isWorking {
                    workingOverlay
                }
            }
            // File picker
            .fileImporter(
                isPresented: $showFilePicker,
                allowedContentTypes: [.pdf, .plainText],
                allowsMultipleSelection: true
            ) { result in
                guard let urls = try? result.get() else { return }
                Task {
                    for url in urls {
                        await store.ingestFile(url: url)
                    }
                }
            }
            // Confirm removal
            .confirmationDialog(
                "Remove \(confirmRemove?.name ?? "")?",
                isPresented: .init(
                    get: { confirmRemove != nil },
                    set: { if !$0 { confirmRemove = nil } }
                ),
                titleVisibility: .visible
            ) {
                Button("Remove", role: .destructive) {
                    if let s = confirmRemove {
                        Task { await store.removeSource(s) }
                    }
                    confirmRemove = nil
                }
            } message: {
                Text("All indexed content from this source will be deleted.")
            }
            // Status footer
            .safeAreaInset(edge: .bottom) {
                Text(store.status)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.ultraThinMaterial)
            }
        }
    }

    // MARK: - Subviews

    private var emptyState: some View {
        ContentUnavailableView(
            "No sources yet",
            systemImage: "tray",
            description: Text("Import files or contacts to start searching.")
        )
        .listRowBackground(Color.clear)
    }

    private var workingOverlay: some View {
        VStack(spacing: 10) {
            ProgressView()
            Text(store.status)
                .font(.caption)
                .multilineTextAlignment(.center)
        }
        .padding(20)
        .background(.regularMaterial)
        .cornerRadius(14)
    }
}

// MARK: - Source row

struct SourceRow: View {
    let source:    IndexedSource
    let onRemove:  () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: source.kind == .file ? "doc.text" : "person.2")
                .frame(width: 28)
                .foregroundStyle(.blue)

            VStack(alignment: .leading, spacing: 2) {
                Text(source.name)
                    .font(.body)
                    .lineLimit(1)
                Text("\(source.docCount) chunks · \(source.addedAt.formatted(date: .abbreviated, time: .omitted))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button(role: .destructive, action: onRemove) {
                Image(systemName: "trash")
                    .foregroundStyle(.red)
            }
            .buttonStyle(.borderless)
        }
    }
}
