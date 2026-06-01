import Foundation
import Moss

/// Drives the demo screen - owns a `MossClient`, a status string, and a
/// running log of operations. UI binds to the `@Published` fields.
///
/// This sample focuses on Moss's on-device sessions: documents are embedded
/// and searched entirely on the device, with no network calls.
@MainActor
final class MossDemoModel: ObservableObject {
    @Published var status: String = "starting…"
    @Published var log: String = ""
    @Published var busy: Bool = false

    var client: MossClient?

    // ── Lifecycle ──────────────────────────────────────────────────────────

    /// Construct the `MossClient` with the project credentials, which
    /// authenticate the client before any session is opened.
    func connect(projectId: String, projectKey: String) async {
        appendLog("Constructing MossClient (sdk \(MossClient.sdkVersion))…")
        busy = true
        defer { busy = false }
        do {
            client = try MossClient(projectId: projectId, projectKey: projectKey)
            appendLog("✓ Client ready.")
            status = "ready"
        } catch {
            appendLog("✗ Client init failed: \(error.localizedDescription)")
            status = "error"
        }
    }

    // ── On-device session example ────────────────────────────────────────────

    /// Walks the on-device flow end-to-end: open a session, embed a handful
    /// of docs locally with the bundled model, query against them, persist to
    /// disk, reopen, then close. No network calls - everything runs on device.
    func runSessionExample() async {
        guard let c = client else { return }
        busy = true
        appendLog("\n========== On-device session ==========")
        defer {
            appendLog("========== Done ==========\n")
            busy = false
        }

        let sessionName = "ios-local-\(Int(Date().timeIntervalSince1970 * 1000))"
        var session: MossSession?
        defer { session?.close() }

        do {
            try await step("session('\(sessionName)')") {
                session = try await c.session(sessionName)
                self.appendLog("    name=\(session?.name ?? "?")  docCount=\(session?.docCount ?? -1)")
            }
            guard let s = session else { return }

            try await step("addDocs (5 ML one-liners, embedded on-device)") {
                let docs: [DocumentInfo] = [
                    .init(id: "ml1", text: "Machine learning lets computers learn from data without being explicitly programmed."),
                    .init(id: "ml2", text: "Neural networks stack layers of weighted connections to model complex patterns."),
                    .init(id: "ml3", text: "Transformers replaced recurrent networks as the dominant sequence-modeling architecture."),
                    .init(id: "ml4", text: "Embedding models map text into vectors so semantic similarity becomes geometric distance."),
                    .init(id: "ml5", text: "Reinforcement learning trains agents through trial-and-error feedback from the environment."),
                ]
                let (added, updated) = try await s.addDocs(docs)
                self.appendLog("    added=\(added) updated=\(updated) docCount=\(s.docCount)")
            }

            try await step("query: 'how do transformers work'") {
                let r = try await s.query("how do transformers work", options: .init(topK: 3))
                self.appendLog("    \(r.docs.count) hits in \(r.timeMs)ms")
                for (i, d) in r.docs.enumerated() {
                    self.appendLog(String(format: "      %d. [%.3f] %@", i + 1, d.score, d.id))
                    self.appendLog("         \(d.text.prefix(120))")
                }
            }

            try await step("getDocs (all)") {
                let docs = try await s.getDocs()
                self.appendLog("    fetched \(docs.count) docs")
            }

            try await step("deleteDocs(['ml5'])") {
                let deleted = try await s.deleteDocs(["ml5"])
                self.appendLog("    deleted=\(deleted) docCount=\(s.docCount)")
            }

            // Persistence round-trip: write the session to disk, close the
            // handle, open a fresh session for the same name, and verify the
            // docs survived.
            let cache = NSTemporaryDirectory()
            try await step("save(toCachePath:)") {
                try await s.save(toCachePath: cache)
                self.appendLog("    saved to disk")
            }
            session?.close()
            session = nil

            try await step("reopen + loadFromDisk → expect 4 docs") {
                let restored = try await c.session(sessionName)
                let count = try await restored.loadFromDisk(cachePath: cache)
                self.appendLog("    restored \(count) docs")
                let r = try await restored.query("transformers", options: .init(topK: 2))
                self.appendLog("    re-query returned \(r.docs.count) hits")
                restored.close()
            }
        } catch {
            appendLog("✗ failure: \(error.localizedDescription)")
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    func clearLog() { log = "" }

    fileprivate func appendLog(_ line: String) {
        log += line + "\n"
    }

    /// Time-and-log wrapper around a single demo step.
    private func step(_ name: String, _ block: () async throws -> Void) async throws {
        let started = DispatchTime.now()
        appendLog("→ \(name)")
        do {
            try await block()
        } catch {
            let ms = (DispatchTime.now().uptimeNanoseconds - started.uptimeNanoseconds) / 1_000_000
            appendLog("  (\(ms)ms)")
            throw error
        }
        let ms = (DispatchTime.now().uptimeNanoseconds - started.uptimeNanoseconds) / 1_000_000
        appendLog("  (\(ms)ms)")
    }
}
