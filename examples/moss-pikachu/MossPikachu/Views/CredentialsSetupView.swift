import SwiftUI

struct CredentialsSetupView: View {
    @State private var projectID = ""
    @State private var projectKey = ""
    @State private var errorMessage = ""
    @State private var isSaving = false

    let onSaved: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Welcome to Picklight")
                .font(.title2)
                .fontWeight(.semibold)

            Text("Picklight uses Moss for semantic search on your Mac. Your Moss API keys stay in the macOS Keychain on this machine.")
                .font(.caption)
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            Link("Get keys at moss.dev", destination: URL(string: "https://moss.dev")!)

            VStack(alignment: .leading, spacing: 8) {
                Text("Project ID")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextField("MOSS_PROJECT_ID", text: $projectID)
                    .textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Project Key")
                    .font(.caption)
                    .foregroundColor(.secondary)
                SecureField("MOSS_PROJECT_KEY", text: $projectKey)
                    .textFieldStyle(.roundedBorder)
            }

            if !errorMessage.isEmpty {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundColor(.red)
            }

            HStack {
                Spacer()
                Button(isSaving ? "Saving…" : "Save & Continue") {
                    saveCredentials()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(isSaving || projectID.trimmingCharacters(in: .whitespaces).isEmpty
                    || projectKey.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(24)
        .frame(width: 420)
    }

    private func saveCredentials() {
        let id = projectID.trimmingCharacters(in: .whitespacesAndNewlines)
        let key = projectKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty, !key.isEmpty else {
            errorMessage = "Enter both Project ID and Project Key."
            return
        }

        isSaving = true
        errorMessage = ""

        do {
            try KeychainHelper.save(account: "project_id", value: id)
            try KeychainHelper.save(account: "project_key", value: key)
            isSaving = false
            onSaved()
        } catch {
            isSaving = false
            errorMessage = error.localizedDescription
        }
    }
}
