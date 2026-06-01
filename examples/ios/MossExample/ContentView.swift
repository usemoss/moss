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

    var body: some View {
        Group {
            if projectId.isEmpty || projectKey.isEmpty {
                CredentialsView(projectId: $projectId, projectKey: $projectKey)
            } else {
                MainView(
                    projectId: projectId,
                    projectKey: projectKey,
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

    @State private var draftId: String = ""
    @State private var draftKey: String = ""
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
                .multilineTextAlignment(.center)

            VStack(alignment: .leading, spacing: 8) {
                Text("Project ID").font(.caption)
                TextField("00000000-0000-0000-0000-000000000000", text: $draftId)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)

                Text("Project Key").font(.caption).padding(.top, 8)
                SecureField("moss_…", text: $draftKey)
                    .textFieldStyle(.roundedBorder)
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
    let onReset: () -> Void

    @StateObject private var demo = MossDemoModel()

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
                .accessibilityLabel("Reset credentials")
            }

            HStack(spacing: 8) {
                Button("Run Session Demo") {
                    Task { await demo.runSessionExample() }
                }
                .buttonStyle(.borderedProminent)
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
            await demo.connect(projectId: projectId, projectKey: projectKey)
        }
    }
}
