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
                settingsSection(title: "Indexed Folders") {
                    Text("Test mode is enabled: Moss indexes only `~/Downloads/\(IndexingPolicy.testScopeFolderName)` so Spotlight testing stays fast.")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Toggle("Documents", isOn: $settings.indexDocuments)
                        .disabled(IndexingPolicy.isTestScopeEnabled)
                    Toggle("Desktop", isOn: $settings.indexDesktop)
                        .disabled(IndexingPolicy.isTestScopeEnabled)
                    Toggle("Downloads", isOn: $settings.indexDownloads)
                        .disabled(IndexingPolicy.isTestScopeEnabled)
                    Toggle("iCloud Drive", isOn: $settings.indexICloudDrive)
                        .disabled(IndexingPolicy.isTestScopeEnabled)

                    if searchService.watchedFolderPathsList.isEmpty {
                        Text("Create `~/Downloads/\(IndexingPolicy.testScopeFolderName)` to enable indexing.")
                            .font(.caption)
                            .foregroundColor(.orange)
                    } else {
                        ForEach(searchService.watchedFolderPathsList, id: \.self) { path in
                            Text(path)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                                .truncationMode(.middle)
                        }
                    }
                }

                settingsSection(title: "Privacy & Exclusions") {
                    Text("Always excluded: `.git`, `node_modules`, `.venv`, caches, logs, and app containers.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("All regular file types are indexed. Text-like files include contents; everything else is searchable by filename, path, extension, and metadata.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("Current scope is limited to Downloads/cwp-stuff for testing.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                settingsSection(title: "General") {
                    Toggle("Launch at login", isOn: $settings.launchAtLogin)
                        .disabled(true)
                    Text("Moss session storage is enabled with your API keys. Queries still run locally.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                settingsSection(title: "Moss Session") {
                    settingsRow(label: "Session", value: IndexingPolicy.sessionName)
                    settingsRow(label: "Session docs", value: "\(searchService.sessionDocCount)")
                    settingsRow(label: "Storage", value: searchService.sessionStatusMessage)
                    if let date = searchService.lastSessionPushDate {
                        settingsRow(label: "Last stored", value: date.formatted(date: .abbreviated, time: .shortened))
                    }
                    Text("The session is pushed to Moss for durable resume, then queried locally in-memory.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                settingsSection(title: "Index Status") {
                    settingsRow(label: "Status", value: searchService.statusMessage)
                    settingsRow(label: "Files indexed", value: "\(searchService.indexedFileCount)")
                    settingsRow(label: "Chunks indexed", value: "\(searchService.indexedChunkCount)")
                    settingsRow(label: "Skipped", value: "\(searchService.skippedFileCount)")
                    if searchService.discoveredFileCount > 0 {
                        settingsRow(label: "Discovered", value: "\(searchService.discoveredFileCount)")
                    }
                    if searchService.queuedFileCount > 0 {
                        settingsRow(label: "Queued", value: "\(searchService.queuedFileCount)")
                    }
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
        .frame(minWidth: 440, minHeight: 560)
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
