import SwiftUI

/// Top-level view. Gates on whether we have project credentials saved.
///
/// NOTE: credentials are persisted via `@AppStorage`, which writes to plain
/// `UserDefaults`. Fine for a sample app exercising a throwaway project, but
/// NOT a pattern to copy into a real app - project keys are credentials and
/// belong in the Keychain. See this example's README for details.
struct ContentView: View {
    @AppStorage("project_id") private var projectId: String = ""
    @AppStorage("project_key") private var projectKey: String = ""
    @AppStorage("search_index") private var searchIndex: String = "example-cloud-index"

    var body: some View {
        Group {
            if projectId.isEmpty || projectKey.isEmpty {
                CredentialsView(
                    projectId: $projectId,
                    projectKey: $projectKey,
                    searchIndex: $searchIndex
                )
            } else {
                MainView(
                    projectId: projectId,
                    projectKey: projectKey,
                    searchIndex: searchIndex,
                    onReset: {
                        projectId = ""
                        projectKey = ""
                    }
                )
            }
        }
    }
}

// ── Credentials screen ──────────────────────────────────────────────────

struct CredentialsView: View {
    @Binding var projectId: String
    @Binding var projectKey: String
    @Binding var searchIndex: String

    @State private var draftId: String = ""
    @State private var draftKey: String = ""
    @State private var draftIndex: String = "example-cloud-index"
    @State private var error: String?

    var body: some View {
        VStack(spacing: 16) {
            Image("MossLogo")
                .resizable()
                .scaledToFit()
                .frame(maxHeight: 160)
                .padding(.top, 32)

            Text("Moss iOS Example")
                .font(.title2.bold())
            Text("Enter your Moss project credentials to begin.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            VStack(alignment: .leading, spacing: 8) {
                Text("Project ID").font(.caption)
                TextField("00000000-0000-0000-0000-000000000000", text: $draftId)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)

                Text("Project Key").font(.caption).padding(.top, 8)
                SecureField("moss_…", text: $draftKey)
                    .textFieldStyle(.roundedBorder)

                Text("Search index").font(.caption).padding(.top, 8)
                TextField("example-cloud-index", text: $draftIndex)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
            }
            .padding(.horizontal)

            if let error {
                Text(error).foregroundStyle(.red).font(.caption)
            }

            Button("Continue") {
                let id = draftId.trimmingCharacters(in: .whitespaces)
                let key = draftKey.trimmingCharacters(in: .whitespaces)
                if id.isEmpty || key.isEmpty {
                    error = "Both fields are required."
                    return
                }
                projectId = id
                projectKey = key
                searchIndex = draftIndex.trimmingCharacters(in: .whitespaces)
                    .ifEmpty("example-cloud-index")
            }
            .buttonStyle(.borderedProminent)
            .padding(.top)

            Spacer()
        }
        .padding()
    }
}

// ── Main demo screen ────────────────────────────────────────────────────

struct MainView: View {
    let projectId: String
    let projectKey: String
    let searchIndex: String
    let onReset: () -> Void

    @StateObject private var demo = MossDemoModel()

    @State private var query: String = ""
    /// Live-search task; cancelled on each new keystroke.
    @State private var searchTask: Task<Void, Never>?

    /// Debounce. A few ms - task cancellation does the rest.
    private let debounceMs: UInt64 = 5

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .center, spacing: 12) {
                Image("MossLogo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 48, height: 48)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Moss iOS Example").font(.headline)
                    Text(demo.status).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button(action: onReset) {
                    Image(systemName: "arrow.clockwise")
                }
            }

            TextField("Search '\(searchIndex)'…", text: $query)
                .textFieldStyle(.roundedBorder)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled(true)
                .onChange(of: query) { newValue in
                    searchTask?.cancel()
                    if newValue.trimmingCharacters(in: .whitespaces).isEmpty {
                        demo.clearLog()
                        demo.status = demo.client == nil ? "starting…" : "ready"
                        return
                    }
                    searchTask = Task {
                        try? await Task.sleep(nanoseconds: debounceMs * 1_000_000)
                        if Task.isCancelled { return }
                        await demo.search(indexName: searchIndex, query: newValue)
                    }
                }

            HStack(spacing: 8) {
                Button("Local Session") {
                    Task { await demo.runLocalSessionExample() }
                }
                .buttonStyle(.bordered)
                .disabled(demo.client == nil || demo.busy)

                Button("Cloud Example") {
                    Task { await demo.runCloudExample() }
                }
                .buttonStyle(.bordered)
                .disabled(demo.client == nil || demo.busy)

                Button("Clear Log") { demo.clearLog() }
                    .buttonStyle(.bordered)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    Text(demo.log)
                        .font(.system(.caption, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .id("log-end")
                }
                .frame(maxHeight: .infinity)
                .background(Color(uiColor: .systemGray6))
                .cornerRadius(8)
                .onChange(of: demo.log) { _ in
                    proxy.scrollTo("log-end", anchor: .bottom)
                }
            }
        }
        .padding()
        .task {
            await demo.connect(
                projectId: projectId,
                projectKey: projectKey,
                searchIndex: searchIndex
            )
        }
    }
}

// ── Helpers ─────────────────────────────────────────────────────────────

private extension String {
    func ifEmpty(_ fallback: String) -> String { isEmpty ? fallback : self }
}
