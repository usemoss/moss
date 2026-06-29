import SwiftUI

/// Root view. Shows credentials screen on first launch; main tabs once set up.
struct ContentView: View {
    @AppStorage("project_id")  private var projectId:  String = ""
    @AppStorage("project_key") private var projectKey: String = ""

    var body: some View {
        if projectId.isEmpty || projectKey.isEmpty {
            CredentialsView(
                onSave: { id, key in
                    projectId  = id
                    projectKey = key
                }
            )
        } else {
            MainTabView(
                projectId:  projectId,
                projectKey: projectKey,
                onSignOut: {
                    projectId  = ""
                    projectKey = ""
                }
            )
        }
    }
}

// MARK: - Credentials screen

struct CredentialsView: View {
    let onSave: (String, String) -> Void

    @State private var draftId:  String = ""
    @State private var draftKey: String = ""
    @State private var error:    String?

    var body: some View {
        VStack(spacing: 20) {
            Spacer()

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

            VStack(alignment: .leading, spacing: 10) {
                label("Moss Project ID")
                TextField("00000000-0000-…", text: $draftId)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                label("Moss Project Key")
                SecureField("moss_…", text: $draftKey)
                    .textFieldStyle(.roundedBorder)
            }
            .padding(.horizontal)

            if let error {
                Text(error).foregroundStyle(.red).font(.caption)
            }

            Button("Get started") {
                let id  = draftId.trimmingCharacters(in: .whitespaces)
                let key = draftKey.trimmingCharacters(in: .whitespaces)
                guard !id.isEmpty  else { error = "Project ID is required.";  return }
                guard !key.isEmpty else { error = "Project Key is required."; return }
                onSave(id, key)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)

            Link("Get credentials at moss.dev →",
                 destination: URL(string: "https://moss.dev")!)
                .font(.footnote)
                .foregroundStyle(.secondary)

            Spacer()
        }
        .padding()
    }

    private func label(_ text: String) -> some View {
        Text(text).font(.caption).foregroundStyle(.secondary)
    }
}

// MARK: - Main tab container

struct MainTabView: View {
    let projectId:  String
    let projectKey: String
    let onSignOut:  () -> Void

    @StateObject private var store = IndexStore()

    var body: some View {
        TabView {
            SearchView()
                .tabItem { Label("Search", systemImage: "magnifyingglass") }

            SourcesView(onSignOut: onSignOut)
                .tabItem { Label("Sources",  systemImage: "tray.and.arrow.down") }

            SettingsView(onSignOut: onSignOut)
                .tabItem { Label("Settings", systemImage: "gear") }
        }
        .environmentObject(store)
        .task {
            await store.setup(projectId: projectId, projectKey: projectKey)
        }
    }
}
