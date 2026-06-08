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
    // Optional: a backend token endpoint. When set, the app authenticates via
    // `BackendTokenAuthenticator` (short-lived, cached tokens) instead of the
    // static project key — the production pattern. See the README.
    @AppStorage("token_url") private var tokenURL: String = ""

    /// Ready once we have a project ID plus *some* credential — either the
    /// static project key or a backend token endpoint URL.
    private var hasCredentials: Bool {
        !projectId.isEmpty && (!projectKey.isEmpty || !tokenURL.isEmpty)
    }

    var body: some View {
        Group {
            if !hasCredentials {
                CredentialsView(projectId: $projectId, projectKey: $projectKey, tokenURL: $tokenURL)
            } else {
                MainView(
                    projectId: projectId,
                    projectKey: projectKey,
                    tokenURL: tokenURL,
                    onReset: {
                        projectId = ""
                        projectKey = ""
                        tokenURL = ""
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
    @Binding var tokenURL: String

    @State private var draftId: String = ""
    @State private var draftKey: String = ""
    @State private var draftTokenURL: String = ""
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

                Text("Token endpoint URL (optional)").font(.caption).padding(.top, 8)
                TextField("http://localhost:3456/moss-token", text: $draftTokenURL)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
                    .keyboardType(.URL)
                Text("Set this to authenticate via your backend (BackendTokenAuthenticator). Leave it blank to use the static project key.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal)

            if let error {
                Text(error).foregroundStyle(.red).font(.caption)
            }

            Button("Continue") {
                let id = draftId.trimmingCharacters(in: .whitespaces)
                let key = draftKey.trimmingCharacters(in: .whitespaces)
                let url = draftTokenURL.trimmingCharacters(in: .whitespaces)
                if id.isEmpty {
                    error = "Project ID is required."
                    return
                }
                if key.isEmpty && url.isEmpty {
                    error = "Enter a project key or a token endpoint URL."
                    return
                }
                projectId = id
                projectKey = key
                tokenURL = url
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
    let tokenURL: String
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
            await demo.connect(projectId: projectId, projectKey: projectKey, tokenURL: tokenURL)
        }
    }
}
