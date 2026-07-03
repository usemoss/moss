import SwiftUI

struct SettingsView: View {
    @ObservedObject var searchService: SearchService

    @State private var settings = UserSettings.load()
    @State private var statusMessage = ""

    init(searchService: SearchService) {
        self.searchService = searchService
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                settingsSection(title: "Indexed Folder") {
                    Text("Moss indexes only `~/Downloads/\(IndexScope.folderName)` via a local SessionIndex.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    if let scopePath = searchService.watchedFolderPathsList.first {
                        settingsRow(label: "Folder", value: scopePath)
                    } else {
                        Text("Create `~/Downloads/\(IndexScope.folderName)` to enable indexing.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                settingsSection(title: "General") {
                    Toggle("Launch at login", isOn: $settings.launchAtLogin)
                        .disabled(true)
                    Toggle("Moss Cloud sync", isOn: $settings.mossCloudSync)
                }

                settingsSection(title: "Index Status") {
                    settingsRow(label: "Status", value: searchService.statusMessage)
                    settingsRow(label: "Files indexed", value: "\(searchService.indexedFileCount)")
                    settingsRow(label: "Chunks indexed", value: "\(searchService.indexedChunkCount)")
                    if let date = searchService.lastIndexedDate {
                        settingsRow(label: "Last indexed", value: date.formatted(date: .abbreviated, time: .shortened))
                    }
                    if searchService.isIndexing {
                        HStack {
                            ProgressView().controlSize(.small)
                            Text("Indexing in progress...")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    ForEach(searchService.watchedFolderPathsList, id: \.self) { path in
                        Text(path)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                    HStack {
                        Button("Index Now") {
                            Task { await indexNow() }
                        }
                        .disabled(searchService.isIndexing)
                        Button("Clear & Rescan") {
                            Task { await clearAndRescan() }
                        }
                        .disabled(searchService.isIndexing)
                    }
                }

                settingsSection(title: "About") {
                    settingsRow(label: "Version", value: "1.0.0")
                    settingsRow(label: "Sticker", value: CapvoltSticker.isAvailable ? "Loaded" : "Missing")
                }

                if !statusMessage.isEmpty {
                    Text(statusMessage)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                HStack {
                    Spacer()
                    Button("Save", action: saveSettings)
                        .keyboardShortcut(.defaultAction)
                }
            }
            .padding(20)
        }
        .frame(minWidth: 440, minHeight: 520)
    }

    @ViewBuilder
    private func settingsSection<Content: View>(title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.headline)
            VStack(alignment: .leading, spacing: 8) {
                content()
            }
            .padding(12)
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
        }
    }

    private func settingsRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value)
                .foregroundColor(.secondary)
        }
    }

    private func saveSettings() {
        settings.save()
        searchService.updateSettings(settings)
        statusMessage = "Settings saved."
    }

    private func indexNow() async {
        do {
            try await searchService.reindexNow()
            statusMessage = "Reindex complete."
            NotificationManager.shared.showSuccess(
                "Indexed \(searchService.indexedChunkCount) chunks from \(searchService.indexedFileCount) files"
            )
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
        }
    }

    private func clearAndRescan() async {
        do {
            try await searchService.clearIndexAndRescan()
            statusMessage = "Index cleared and rescan started."
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
        }
    }
}
