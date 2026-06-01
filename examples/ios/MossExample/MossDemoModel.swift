import Foundation
import Moss

/// Drives the demo screen - owns a `MossClient`, a status string, and a
/// running log of operations. UI binds to the `@Published` fields.
///
/// This sample highlights the push pathway: build an index on-device, push it
/// to the cloud with `pushIndex`, then load it back into a fresh session.
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

    // ── Push pathway example ─────────────────────────────────────────────────

    /// Highlights the push pathway end-to-end: open an on-device session, embed
    /// docs locally and query them, then `pushIndex` the session up to the
    /// cloud as a server-side index, poll until it's processed, and pull it
    /// back into a fresh session with `loadIndex`, where it queries locally.
    /// Requires network + valid credentials.
    func runSessionExample() async {
        guard let c = client else { return }
        busy = true
        appendLog("\n========== Session → push → load ==========")
        defer {
            appendLog("========== Done ==========\n")
            busy = false
        }

        let sessionName = "ios-push-\(Int(Date().timeIntervalSince1970 * 1000))"
        var session: MossSession?
        defer { session?.close() }
        var pushedName = sessionName

        do {
            // ── Build an index on-device ──────────────────────────────────
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

            try await step("deleteDocs(['ml5'])") {
                let deleted = try await s.deleteDocs(["ml5"])
                self.appendLog("    deleted=\(deleted) docCount=\(s.docCount)")
            }

            // ── Push it to the cloud ──────────────────────────────────────
            var jobId = ""
            try await step("pushIndex (local → cloud)") {
                let r = try await s.pushIndex()
                jobId = r.jobId
                pushedName = r.indexName
                self.appendLog("    job=\(r.jobId)  index=\(r.indexName)  status=\(r.status)")
            }

            try await step("poll getJobStatus until ready") {
                let done: Set<String> = ["ready", "completed", "done", "succeeded"]
                let failed: Set<String> = ["failed", "error"]
                for attempt in 1...30 {
                    let st = try await c.getJobStatus(jobId)
                    self.appendLog("    [\(attempt)] status=\(st.status)")
                    if done.contains(st.status.lowercased()) { return }
                    if failed.contains(st.status.lowercased()) {
                        throw DemoError(message: "push job failed: \(st.error ?? "unknown")")
                    }
                    try await Task.sleep(nanoseconds: 1_000_000_000)
                }
                throw DemoError(message: "push job did not finish in time")
            }

            // ── Tear down the local session, reload it from the cloud ─────
            session?.close()
            session = nil

            try await step("loadIndex (cloud → new session) + query") {
                let loaded = try await c.session(pushedName)
                defer { loaded.close() }
                let count = try await loaded.loadIndex(pushedName)
                self.appendLog("    loaded \(count) docs from cloud")
                let r = try await loaded.query("how do transformers work", options: .init(topK: 3))
                self.appendLog("    \(r.docs.count) hits in \(r.timeMs)ms")
                for (i, d) in r.docs.enumerated() {
                    self.appendLog(String(format: "      %d. [%.3f] %@", i + 1, d.score, d.id))
                }
            }

            try await step("deleteIndex (cleanup)") {
                _ = try await c.deleteIndex(pushedName)
                self.appendLog("    deleted cloud index \(pushedName)")
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

/// Lightweight error for demo-side failures (e.g. a cloud push job that never
/// reaches a ready state). `MossError` is reserved for the SDK itself.
private struct DemoError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}
