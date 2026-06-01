import Foundation
import Moss

/// Drives the demo screen - owns a `MossClient`, a status string, and a
/// running log of operations. UI binds to the `@Published` fields.
///
/// This sample uses an on-device session: build an index on-device, push it
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

    // ── On-device session example ────────────────────────────────────────────

    /// Walks an on-device session end-to-end: open a session, embed docs
    /// (with metadata) locally, then exercise the query surface - hybrid
    /// search via `alpha`, metadata filtering (`$eq`/`$and`/`$in`/`$near`),
    /// and fetch-by-id. Finally `pushIndex` the session up to the cloud,
    /// poll until it's processed, and pull it back with `loadIndex`.
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

            try await step("addDocs (6 products with metadata, embedded on-device)") {
                let docs: [DocumentInfo] = [
                    .init(id: "p1", text: "Running shoes with breathable mesh for daily training.",
                          metadata: ["category": "shoes", "brand": "swiftfit", "price": "79", "city": "new-york", "location": "40.7580,-73.9855"]),
                    .init(id: "p2", text: "Trail running shoes built for rocky mountain terrain.",
                          metadata: ["category": "shoes", "brand": "peakstride", "price": "149", "city": "seattle", "location": "47.6062,-122.3321"]),
                    .init(id: "p3", text: "Lightweight city backpack with a padded laptop compartment.",
                          metadata: ["category": "bags", "brand": "urbanpack", "price": "95", "city": "new-york", "location": "40.7505,-73.9934"]),
                    .init(id: "p4", text: "Waterproof hiking backpack with a 40-litre capacity.",
                          metadata: ["category": "bags", "brand": "peakstride", "price": "120", "city": "seattle", "location": "47.6097,-122.3331"]),
                    .init(id: "p5", text: "Cushioned walking shoes for all-day comfort.",
                          metadata: ["category": "shoes", "brand": "swiftfit", "price": "89", "city": "new-york", "location": "40.7614,-73.9776"]),
                    .init(id: "p6", text: "Insulated water bottle that keeps drinks cold for 24 hours.",
                          metadata: ["category": "accessories", "brand": "urbanpack", "price": "29", "city": "boston", "location": "42.3601,-71.0589"]),
                ]
                let (added, updated) = try await s.addDocs(docs)
                self.appendLog("    added=\(added) updated=\(updated) docCount=\(s.docCount)")
            }

            // ── Hybrid search: tune `alpha` (1.0 = pure semantic, 0.0 = pure keyword) ──
            try await step("query 'running shoes' across alpha") {
                for alpha in [Float(1.0), 0.8, 0.0] {
                    let r = try await s.query("running shoes", options: .init(topK: 3, alpha: alpha))
                    let ids = r.docs.map(\.id).joined(separator: ", ")
                    self.appendLog(String(format: "    alpha %.1f → [%@]", alpha, ids))
                }
            }

            // ── Metadata filtering: filter on any metadata field at query time ──
            try await step("filter $eq: category == shoes") {
                let filter = #"{"field":"category","condition":{"$eq":"shoes"}}"#
                self.logHits(try await s.query("comfortable footwear", options: .init(topK: 5, alpha: 0.5, filterJson: filter)))
            }

            try await step("filter $and: shoes AND price < 100") {
                let filter = #"{"$and":[{"field":"category","condition":{"$eq":"shoes"}},{"field":"price","condition":{"$lt":"100"}}]}"#
                self.logHits(try await s.query("running shoes", options: .init(topK: 5, alpha: 0.6, filterJson: filter)))
            }

            try await step("filter $in: city in [new-york]") {
                let filter = #"{"field":"city","condition":{"$in":["new-york"]}}"#
                self.logHits(try await s.query("everyday gear", options: .init(topK: 5, filterJson: filter)))
            }

            try await step("filter $near: within 5km of Times Square") {
                let filter = #"{"field":"location","condition":{"$near":"40.7580,-73.9855,5000"}}"#
                self.logHits(try await s.query("city products", options: .init(topK: 5, filterJson: filter)))
            }

            // ── Fetch specific docs by id (e.g. for graph-style traversals) ──
            try await step("getDocs(['p1','p3'])") {
                let docs = try await s.getDocs(["p1", "p3"])
                self.appendLog("    fetched \(docs.count): \(docs.map(\.id).joined(separator: ", "))")
            }

            try await step("deleteDocs(['p6'])") {
                let deleted = try await s.deleteDocs(["p6"])
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
                self.logHits(try await loaded.query("running shoes", options: .init(topK: 3)))
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

    /// Log a search result's hits, including each doc's metadata so filter
    /// results are easy to eyeball.
    fileprivate func logHits(_ r: SearchResult) {
        appendLog("    \(r.docs.count) hits in \(r.timeMs)ms")
        for (i, d) in r.docs.enumerated() {
            appendLog(String(format: "      %d. [%.3f] %@", i + 1, d.score, d.id))
            if let m = d.metadata, !m.isEmpty {
                let pairs = m.sorted { $0.key < $1.key }.map { "\($0.key)=\($0.value)" }.joined(separator: "  ")
                appendLog("         \(pairs)")
            }
        }
    }

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
