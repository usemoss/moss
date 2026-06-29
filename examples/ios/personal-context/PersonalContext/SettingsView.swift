import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: IndexStore
    let onSignOut: () -> Void

    @State private var showSyncConfirm  = false
    @State private var showClearConfirm = false

    var body: some View {
        NavigationStack {
            List {

                // ── Stats ─────────────────────────────────────────────────
                Section("Index") {
                    LabeledContent("Sources",   value: "\(store.sources.count)")
                    LabeledContent("Cloud sync", value: store.cloudSynced ? "Up to date ✓" : "Not synced")
                }

                // ── Cloud sync ────────────────────────────────────────────
                Section {
                    Button {
                        showSyncConfirm = true
                    } label: {
                        Label("Sync to cloud", systemImage: "icloud.and.arrow.up")
                    }
                    .disabled(store.isWorking || store.sources.isEmpty)
                } footer: {
                    Text("Pushes your on-device index to Moss cloud so you can load it on other devices. No content leaves your project.")
                }

                // ── Danger zone ───────────────────────────────────────────
                Section("Account") {
                    Button(role: .destructive) {
                        onSignOut()
                    } label: {
                        Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                }
            }
            .navigationTitle("Settings")
            .overlay {
                if store.isWorking {
                    syncingOverlay
                }
            }
            .confirmationDialog(
                "Sync to cloud?",
                isPresented: $showSyncConfirm,
                titleVisibility: .visible
            ) {
                Button("Sync") {
                    Task { await store.syncToCloud() }
                }
            } message: {
                Text("This uploads your index to Moss cloud. The operation may take a minute.")
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

    private var syncingOverlay: some View {
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
