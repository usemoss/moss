import SwiftUI

/// Root view. Shows credentials screen on first launch; main tabs once set up.
struct ContentView: View {
    @AppStorage("project_id")   private var projectId:   String = ""
    @AppStorage("project_key")  private var projectKey:  String = ""
    @AppStorage("openai_key")   private var openAIKey:   String = ""

    var body: some View {
        if projectId.isEmpty || projectKey.isEmpty {
            CredentialsView(
                onSave: { id, mossKey, aiKey in
                    projectId  = id
                    projectKey = mossKey
                    openAIKey  = aiKey
                }
            )
        } else {
            MainTabView(
                projectId:  projectId,
                projectKey: projectKey,
                openAIKey:  openAIKey,
                onSignOut: {
                    projectId  = ""
                    projectKey = ""
                    openAIKey  = ""
                }
            )
        }
    }
}

// MARK: - Credentials screen

struct CredentialsView: View {
    let onSave: (String, String, String) -> Void

    @State private var draftId:    String = ""
    @State private var draftKey:   String = ""
    @State private var draftAIKey: String = ""
    @State private var error:      String?

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                VStack(spacing: 6) {
                    Image(systemName: "magnifyingglass.circle.fill")
                        .font(.system(size: 56))
                        .foregroundStyle(.blue)
                    Text("Personal Context")
                        .font(.title.bold())
                    Text("Semantic search over your own files and contacts — on device.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 40)

                // ── Moss credentials ─────────────────────────────────────
                VStack(alignment: .leading, spacing: 10) {
                    sectionHeader("Moss (required)")

                    label("Project ID")
                    TextField("00000000-0000-…", text: $draftId)
                        .textFieldStyle(.roundedBorder)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    label("Project Key")
                    SecureField("moss_…", text: $draftKey)
                        .textFieldStyle(.roundedBorder)

                    Link("Get credentials at moss.dev →",
                         destination: URL(string: "https://moss.dev")!)
                        .font(.caption)
                }

                // ── OpenAI key (optional) ────────────────────────────────
                VStack(alignment: .leading, spacing: 10) {
                    sectionHeader("OpenAI (optional — for AI answers)")

                    label("API Key")
                    SecureField("sk-…", text: $draftAIKey)
                        .textFieldStyle(.roundedBorder)

                    Text("Used only for on-device Q&A synthesis. Never stored on a server.")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                if let error {
                    Text(error).foregroundStyle(.red).font(.caption)
                }

                Button("Get started") {
                    let id  = draftId.trimmingCharacters(in: .whitespaces)
                    let key = draftKey.trimmingCharacters(in: .whitespaces)
                    guard !id.isEmpty  else { error = "Moss Project ID is required.";  return }
                    guard !key.isEmpty else { error = "Moss Project Key is required."; return }
                    onSave(id, key, draftAIKey.trimmingCharacters(in: .whitespaces))
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .frame(maxWidth: .infinity)

                Spacer(minLength: 40)
            }
            .padding(.horizontal)
        }
    }

    private func sectionHeader(_ text: String) -> some View {
        Text(text)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(.primary)
    }

    private func label(_ text: String) -> some View {
        Text(text).font(.caption).foregroundStyle(.secondary)
    }
}

// MARK: - Main tab container

struct MainTabView: View {
    let projectId:  String
    let projectKey: String
    let openAIKey:  String
    let onSignOut:  () -> Void

    @StateObject private var store = IndexStore()

    var body: some View {
        TabView {
            SearchView()
                .tabItem { Label("Search",   systemImage: "magnifyingglass") }

            SourcesView(onSignOut: onSignOut)
                .tabItem { Label("Sources",  systemImage: "tray.and.arrow.down") }

            SettingsView(onSignOut: onSignOut)
                .tabItem { Label("Settings", systemImage: "gear") }
        }
        .environmentObject(store)
        .task {
            await store.setup(projectId: projectId, projectKey: projectKey, openAIKey: openAIKey)
        }
    }
}
