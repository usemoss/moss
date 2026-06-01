import Foundation
import Moss

/// Drives the demo screen - owns a `MossClient`, a status string, and a
/// running log of operations. UI binds to the `@Published` fields.
///
/// This is intentionally a single observable object that walks the SDK's
/// public surface end-to-end. Read it top-to-bottom as a guided tour of
/// what you can do with `MossClient` and `MossSession`.
@MainActor
final class MossDemoModel: ObservableObject {
    @Published var status: String = "starting…"
    @Published var log: String = ""
    @Published var busy: Bool = false

    var client: MossClient?
    /// Index names already loaded, so we can skip the `loadIndex` call on
    /// later keystrokes.
    private var loadedIndexes: Set<String> = []
    /// Search index name remembered from `connect`, so we can re-warm it
    /// after the cloud example tears everything down via `onMemoryPressure`.
    private var searchIndex: String?

    // ── Lifecycle ────────────────────────────────────────────────────────

    /// Construct the `MossClient` and eagerly warm the search index so the
    /// first keystroke doesn't pay the `loadIndex` cost.
    func connect(projectId: String, projectKey: String, searchIndex: String) async {
        self.searchIndex = searchIndex
        appendLog("Constructing MossClient (sdk \(MossClient.sdkVersion))…")
        busy = true
        defer { busy = false }
        do {
            let c = try MossClient(projectId: projectId, projectKey: projectKey)
            client = c
            appendLog("✓ Client ready.")
            status = "warming '\(searchIndex)'…"
            await warm(c, indexName: searchIndex)
            status = "ready"
        } catch {
            appendLog("✗ Client init failed: \(error.localizedDescription)")
            status = "error"
        }
    }

    /// Pre-load an index so subsequent queries skip the `loadIndex` hop.
    private func warm(_ c: MossClient, indexName: String) async {
        let started = DispatchTime.now()
        do {
            try await c.loadIndex(indexName)
            loadedIndexes.insert(indexName)
            let ms = (DispatchTime.now().uptimeNanoseconds - started.uptimeNanoseconds) / 1_000_000
            appendLog("✓ warmed '\(indexName)' (\(ms)ms)")
        } catch {
            appendLog("⚠ warm '\(indexName)' failed: \(error.localizedDescription)")
        }
    }

    // ── Live search ────────────────────────────────────────────────────────

    /// Live-search entry point. Each call wipes the log so the panel only
    /// shows results for the current query, not a running history.
    func search(indexName: String, query: String) async {
        guard let c = client else { return }
        let trimmed = query.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        log = ""
        appendLog("[search] \"\(trimmed)\"")
        status = "searching…"
        do {
            // Load the index once; skip the call on later keystrokes.
            if !loadedIndexes.contains(indexName) {
                try await c.loadIndex(indexName)
                loadedIndexes.insert(indexName)
            }
            try Task.checkCancellation()
            let r = try await c.query(indexName, trimmed, options: .init(topK: 10))
            try Task.checkCancellation()
            appendLog("  \(r.docs.count) hits • \(r.timeMs)ms")
            for (i, d) in r.docs.enumerated() {
                appendLog(String(format: "    %d. [%.4f] %@", i + 1, d.score, d.id))
                appendLog("       \(d.text.prefix(160))")
            }
            status = "ready"
        } catch is CancellationError {
            // Superseded by a newer keystroke; silently drop.
        } catch {
            appendLog("  ✗ \(error.localizedDescription)")
            status = "error"
        }
    }

    // ── Cloud example ──────────────────────────────────────────────────────

    /// Walks every public `MossClient` method end-to-end against a freshly
    /// created throwaway index, logging timing per step. Cleans up the index
    /// when done so reruns start from a blank slate.
    func runCloudExample() async {
        guard let c = client else { return }
        busy = true
        appendLog("\n========== Cloud example ==========")
        let indexName = "ios-demo-\(Int(Date().timeIntervalSince1970 * 1000))"
        var indexCreated = false
        defer {
            if indexCreated {
                Task {
                    do {
                        _ = try await c.deleteIndex(indexName)
                        await MainActor.run { self.appendLog("✓ cleanup: deleted \(indexName)") }
                    } catch {
                        await MainActor.run { self.appendLog("⚠ cleanup failed: \(error.localizedDescription)") }
                    }
                    await MainActor.run {
                        self.appendLog("========== Done ==========\n")
                        self.busy = false
                    }
                }
            } else {
                appendLog("========== Done ==========\n")
                busy = false
            }
        }

        do {
            try await step("createIndex(\(indexName))") {
                let docs: [DocumentInfo] = [
                    .init(id: "doc1", text: "Machine learning is a subset of artificial intelligence that enables computers to learn from experience."),
                    .init(id: "doc2", text: "Deep learning uses neural networks with multiple layers to model complex patterns in data."),
                    .init(id: "doc3", text: "Natural language processing enables computers to interpret and manipulate human language."),
                    .init(id: "doc4", text: "Computer vision enables machines to interpret visual information from the world."),
                    .init(id: "doc5", text: "Reinforcement learning is where an agent learns by performing actions and receiving rewards."),
                ]
                let r = try await c.createIndex(indexName, docs: docs)
                self.appendLog("    job=\(r.jobId)  docs=\(r.docCount)")
            }
            // Mark created only after createIndex returns, so a failure there
            // doesn't trigger a cleanup delete against a non-existent index.
            indexCreated = true

            try await step("getIndex") {
                let info = try await c.getIndex(indexName)
                self.appendLog("    name=\(info.name)  status=\(info.status)  docs=\(info.docCount)  model=\(info.model.id)")
            }

            try await step("listIndexes") {
                let indexes = try await c.listIndexes()
                let first = indexes.prefix(5).map { $0.name }.joined(separator: ", ")
                self.appendLog("    \(indexes.count) indexes; first 5: \(first)")
            }

            try await step("addDocs (upsert)") {
                let added = try await c.addDocs(
                    indexName,
                    docs: [.init(id: "doc6", text: "Data science combines statistics and programming to extract insights from data.")],
                    upsert: true
                )
                self.appendLog("    job=\(added.jobId)  docs=\(added.docCount)")
            }

            try await step("getDocs") {
                let docs = try await c.getDocs(indexName)
                self.appendLog("    fetched \(docs.count) docs; ids=\(docs.map(\.id))")
            }

            try await step("loadIndex") {
                try await c.loadIndex(indexName)
                self.loadedIndexes.insert(indexName)
                self.appendLog("    loaded")
            }

            try await step("query: 'artificial intelligence and neural networks'") {
                let r = try await c.query(
                    indexName,
                    "artificial intelligence and neural networks",
                    options: .init(topK: 3)
                )
                self.appendLog("    \(r.docs.count) hits in \(r.timeMs)ms")
                for (i, d) in r.docs.enumerated() {
                    self.appendLog(String(format: "      %d. [%.3f] %@ - %@…", i + 1, d.score, d.id, String(d.text.prefix(80))))
                }
            }

            try await step("deleteDocs(doc6)") {
                let r = try await c.deleteDocs(indexName, docIds: ["doc6"])
                self.appendLog("    job=\(r.jobId)  docs=\(r.docCount)")
            }

            try await step("refreshIndex") {
                let r = try await c.refreshIndex(indexName)
                self.appendLog("    wasUpdated=\(r.wasUpdated)  \(r.previousUpdatedAt) → \(r.newUpdatedAt)")
            }

            try await step("onMemoryPressure(.critical)") {
                let unloaded = try await c.onMemoryPressure(.critical)
                self.loadedIndexes.removeAll()
                self.appendLog("    unloaded \(unloaded) indexes")
            }
        } catch {
            appendLog("✗ failure: \(error.localizedDescription)")
        }
        // Re-warm the search index so the next live-search keystroke is fast.
        if let i = searchIndex {
            await warm(c, indexName: i)
        }
    }

    // ── Local-session example ────────────────────────────────────────────

    /// Walks the on-device flow end-to-end: open a session, embed a handful
    /// of docs locally with the bundled model (no network round-trip), query
    /// against them, persist to disk, reopen, then close.
    ///
    /// Sessions are the offline-first path - everything runs on the device,
    /// so this works even with no cloud project configured.
    func runLocalSessionExample() async {
        guard let c = client else { return }
        busy = true
        appendLog("\n========== Local session ==========")
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
