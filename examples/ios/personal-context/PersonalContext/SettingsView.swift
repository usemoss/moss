import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: IndexStore
    @AppStorage("openai_key") private var openAIKey: String = ""

    let onSignOut: () -> Void

    @State private var showSyncConfirm = false
    @State private var draftAIKey:    String = ""
    @State private var editingAIKey   = false

    var body: some View {
        NavigationStack {
            List {

                // ── Index stats ───────────────────────────────────────────
                Section("Index") {
                    LabeledContent("Sources",    value: "\(store.sources.count)")
                    LabeledContent("Cloud sync", value: store.cloudSynced ? "Up to date ✓" : "Not synced")
                }

                // ── OpenAI key ────────────────────────────────────────────
                Section {
                    if editingAIKey {
                        VStack(alignment: .leading, spacing: 8) {
                            SecureField("sk-…", text: $draftAIKey)
                                .textFieldStyle(.roundedBorder)
                            HStack {
                                Button("Save") {
                                    openAIKey       = draftAIKey.trimmingCharacters(in: .whitespaces)
                                    store.openAIKey = openAIKey
                                    editingAIKey    = false
                                }
                                .buttonStyle(.borderedProminent)
                                .controlSize(.small)

                                Button("Cancel") { editingAIKey = false }
                                    .buttonStyle(.bordered)
                                    .controlSize(.small)
                            }
                        }
                        .padding(.vertical, 4)
                    } else {
                        HStack {
                            Label(
                                store.hasOpenAI ? "OpenAI key set ✓" : "Add OpenAI key",
                                systemImage: store.hasOpenAI ? "checkmark.circle.fill" : "key"
                            )
                            .foregroundStyle(store.hasOpenAI ? .green : .primary)
                            Spacer()
                            Button("Edit") {
                                draftAIKey   = openAIKey
                                editingAIKey = true
                            }
                            .font(.caption)
                            .foregroundStyle(.blue)
                        }
                    }
                } header: {
                    Text("AI Answers")
                } footer: {
                    Text("Required for the AI Answer tab. When you submit a query, Moss retrieves matching excerpts from your indexed files and contacts and sends them to OpenAI to generate an answer. Your API key is stored on this device only; the retrieved text is transmitted to OpenAI's servers.")
                }

                // ── Cloud upload ──────────────────────────────────────────
                Section {
                    Button(role: .destructive) {
                        showSyncConfirm = true
                    } label: {
                        Label("Replace cloud index", systemImage: "icloud.and.arrow.up")
                    }
                    .disabled(store.isWorking || store.sources.isEmpty || store.indexDocCount == 0)
                } footer: {
                    Text("Uploads this device's index to the cloud, replacing whatever is stored there. This does not pull or merge content from other devices first.")
                }

                // ── Account ───────────────────────────────────────────────
                Section("Account") {
                    Button(role: .destructive) {
                        store.signOut()
                        onSignOut()
                    } label: {
                        Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                }
            }
            .navigationTitle("Settings")
            .overlay {
                if store.isWorking {
                    VStack(spacing: 10) {
                        ProgressView()
                        Text(store.status).font(.caption).multilineTextAlignment(.center)
                    }
                    .padding(20)
                    .background(.regularMaterial)
                    .cornerRadius(14)
                }
            }
            .confirmationDialog("Replace cloud index?", isPresented: $showSyncConfirm, titleVisibility: .visible) {
                Button("Replace", role: .destructive) { Task { await store.syncToCloud() } }
            } message: {
                Text("This replaces the cloud copy with this device's local index. Any documents added on other devices will be lost. May take up to a minute.")
            }
            .safeAreaInset(edge: .bottom) {
                Text(store.status)
                    .font(.caption2).foregroundStyle(.secondary).padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.ultraThinMaterial)
            }
        }
        .onAppear {
            store.openAIKey = openAIKey
        }
    }
}
