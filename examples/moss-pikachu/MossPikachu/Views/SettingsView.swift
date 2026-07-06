import SwiftUI

struct SettingsView: View {
    @ObservedObject var searchService: SearchService

    @State private var settings = UserSettings.load()
    @State private var statusMessage = ""
    @State private var credentialProjectID = ""
    @State private var credentialProjectKey = ""
    @State private var showCredentialEditor = false

    init(searchService: SearchService) {
        self.searchService = searchService
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                settingsSection(title: "Setup") {
                    settingsRow(
                        label: "Moss credentials",
                        value: searchService.credentialsConfigured ? "Configured" : "Missing"
                    )
                    settingsRow(label: "Python + Moss", value: searchService.pythonEnvironmentStatus)

                    if let error = searchService.initializationError, !error.isEmpty {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.orange)
                    }

                    if !searchService.inaccessibleFolderMessages.isEmpty {
                        ForEach(searchService.inaccessibleFolderMessages, id: \.self) { message in
                            Text(message)
                                .font(.caption)
                                .foregroundColor(.orange)
                        }
                    }

                    HStack {
                        Button("Retry Initialize") {
                            Task { await searchService.retryInitialize() }
                        }
                        .disabled(searchService.isInitializing)

                        Button(showCredentialEditor ? "Hide credentials" : "Update credentials") {
                            showCredentialEditor.toggle()
                        }
                    }

                    if showCredentialEditor {
                        TextField("Project ID", text: $credentialProjectID)
                            .textFieldStyle(.roundedBorder)
                        SecureField("Project Key", text: $credentialProjectKey)
                            .textFieldStyle(.roundedBorder)
                        HStack {
                            Button("Save credentials") {
                                saveCredentials()
                            }
                            Button("Clear credentials", role: .destructive) {
                                clearCredentials()
                            }
                        }
                    }
                }

                settingsSection(title: "Indexed Folders") {
                    Text("Default: Documents, Desktop, and Downloads. Grant folder access if macOS prompts.")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Toggle("Documents", isOn: $settings.indexDocuments)
                    Toggle("Desktop", isOn: $settings.indexDesktop)
                    Toggle("Downloads", isOn: $settings.indexDownloads)
                    Toggle("Movies", isOn: $settings.indexMovies)
                    Toggle("Music", isOn: $settings.indexMusic)
                    Toggle("Pictures", isOn: $settings.indexPictures)
                    Toggle("Public", isOn: $settings.indexPublic)
                    Toggle("iCloud Drive", isOn: $settings.indexICloudDrive)

                    if searchService.watchedFolderPathsList.isEmpty {
                        Text("No accessible folders. Check permissions above.")
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

                settingsSection(title: "Index Status") {
                    Text("Files are indexed and stored on this Mac. Moss API key is used for semantic search locally.")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    settingsRow(label: "Status", value: searchService.statusMessage)
                    settingsRow(label: "Session docs", value: "\(searchService.sessionDocCount)")
                    settingsRow(label: "Files indexed", value: "\(searchService.indexedFileCount)")
                    settingsRow(label: "Chunks indexed", value: "\(searchService.indexedChunkCount)")
                    settingsRow(label: "Skipped", value: "\(searchService.skippedFileCount)")
                    settingsRow(label: "Storage", value: searchService.sessionStatusMessage)
                    if let date = searchService.lastLocalCacheSaveDate {
                        settingsRow(label: "Last saved", value: date.formatted(date: .abbreviated, time: .shortened))
                    }
                    if let date = searchService.lastIndexedDate {
                        settingsRow(label: "Last indexed", value: date.formatted(date: .abbreviated, time: .shortened))
                    }
                    if searchService.isIndexing {
                        HStack {
                            ProgressView().controlSize(.small)
                            Text("Background indexing in progress...")
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

                settingsSection(title: "Search") {
                    Picker("Search style", selection: $settings.searchAlpha) {
                        Text("Keyword-heavy").tag(0.4)
                        Text("Balanced").tag(0.75)
                        Text("Semantic").tag(0.95)
                    }
                    .pickerStyle(.segmented)
                    Text("Controls how Moss blends keyword and semantic matching.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                settingsSection(title: "About") {
                    settingsRow(label: "Version", value: "1.0.0")
                    settingsRow(label: "Pet assets", value: CapvoltPetAssets.isAvailable ? "Loaded" : "Missing")
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
                .multilineTextAlignment(.trailing)
        }
    }

    private func saveSettings() {
        settings.save()
        searchService.updateSettings(settings)
        statusMessage = "Settings saved."
    }

    private func saveCredentials() {
        let id = credentialProjectID.trimmingCharacters(in: .whitespacesAndNewlines)
        let key = credentialProjectKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty, !key.isEmpty else {
            statusMessage = "Enter both Project ID and Project Key."
            return
        }
        do {
            try KeychainHelper.save(account: "project_id", value: id)
            try KeychainHelper.save(account: "project_key", value: key)
            credentialProjectKey = ""
            statusMessage = "Credentials saved."
            Task { await searchService.retryInitialize() }
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
        }
    }

    private func clearCredentials() {
        try? KeychainHelper.delete(account: "project_id")
        try? KeychainHelper.delete(account: "project_key")
        credentialProjectID = ""
        credentialProjectKey = ""
        statusMessage = "Credentials cleared."
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
