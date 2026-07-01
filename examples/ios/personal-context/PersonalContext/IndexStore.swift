import Foundation
import Moss
import Contacts

// MARK: - Data models

struct IndexedSource: Identifiable, Codable {
    /// Stable UUID minted at ingest time — never changes, even if the file
    /// is renamed or another file with the same name is imported later.
    let id: String
    /// Human-readable display name only; not used for identity or querying.
    let name: String
    let kind: SourceKind
    let docCount: Int
    let addedAt: Date

    enum SourceKind: String, Codable {
        case file, contacts
    }
}

struct SearchHit: Identifiable {
    let id: String
    let sourceName: String
    let excerpt: String
    let score: Float
}

// MARK: - IndexStore

/// The ML layer. Owns the MossClient + MossSession and exposes
/// ingest / search / sync operations to SwiftUI views.
///
/// @MainActor means every @Published mutation runs on the main thread,
/// so SwiftUI picks up changes without extra DispatchQueue.main wrappers.
@MainActor
final class IndexStore: ObservableObject {

    // ── Published state (SwiftUI observes these) ─────────────────────────

    @Published var sources:       [IndexedSource] = []
    @Published var searchHits:    [SearchHit]     = []
    @Published var llmAnswer:     String          = ""
    @Published var isAnswering:   Bool            = false
    @Published var status:        String          = "Not connected"
    @Published var isWorking:     Bool            = false
    @Published var cloudSynced:   Bool            = false
    @Published var indexDocCount: Int             = 0

    // ── LLM ───────────────────────────────────────────────────────────────

    var openAIKey: String = ""
    var hasOpenAI: Bool { !openAIKey.isEmpty }
    var canAnswer: Bool { hasOpenAI }

    // ── Private Moss objects ──────────────────────────────────────────────

    private var client:    MossClient?
    private var session:   MossSession?

    // Current project — used to scope the cache path and UserDefaults key
    private var currentProjectId: String?

    // Incremented on every setup() and signOut(). Ingest operations capture
    // this at start and abort after each await if it has changed, preventing
    // a sign-out mid-ingest from writing into the new project's cache or
    // persisting sources under the wrong project key.
    private var sessionGeneration: Int = 0

    // sourcesKey and cacheDir are scoped by project so switching accounts
    // cannot leak one user's data into another project.
    private func sourcesKey(for projectId: String) -> String {
        "indexed_sources_v1_\(projectId)"
    }

    // MARK: - Setup

    func setup(projectId: String, projectKey: String, openAIKey: String = "") async {
        self.openAIKey = openAIKey
        guard client == nil else { return }   // already set up
        isWorking = true
        status    = "Connecting…"
        defer { isWorking = false }

        do {
            currentProjectId = projectId
            sessionGeneration += 1
            client  = try MossClient(projectId: projectId, projectKey: projectKey)
            // autoLoadOnInit: false — this app is local-first. The index is
            // restored from the on-device disk cache below. Cloud data is only
            // pulled when the user explicitly taps "Sync index to cloud" in
            // Settings, preventing an implicit network fetch on every launch
            // and keeping the Sources tab consistent with the local index.
            session = try await client!.session(
                "personal-context",
                options: SessionOptions(autoLoadOnInit: false)
            )

            // Restore on-device index from disk (survives app restarts, no network).
            // On first launch there is no cache yet — that's fine, start empty.
            try? await session!.loadFromDisk(cachePath: cacheDir(for: projectId))

            // Restore source list from UserDefaults
            sources = loadSources()

            indexDocCount = session!.docCount
            status = "Ready — \(session!.docCount) documents indexed"
        } catch {
            currentProjectId = nil
            status = "Setup failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Sign out

    /// Clears all on-device state for the current project so a subsequent
    /// call to `setup` with different credentials starts from a clean slate.
    func signOut() {
        // Stop any in-flight work
        session = nil
        client  = nil

        sessionGeneration += 1

        if let pid = currentProjectId {
            // Wipe the scoped source list
            UserDefaults.standard.removeObject(forKey: sourcesKey(for: pid))

            // Delete the scoped on-device index cache
            let dir = cacheDir(for: pid)
            try? FileManager.default.removeItem(atPath: dir)

            currentProjectId = nil
        }

        sources      = []
        searchHits   = []
        llmAnswer    = ""
        cloudSynced  = false
        status       = "Signed out"
    }

    // MARK: - Ingest: files

    func ingestFile(url: URL) async {
        guard let session else { status = "Not connected"; return }
        let generation = sessionGeneration
        isWorking = true
        defer { isWorking = false }

        // Security-scoped access needed for files picked via document picker
        let accessed = url.startAccessingSecurityScopedResource()
        defer { if accessed { url.stopAccessingSecurityScopedResource() } }

        let filename = url.lastPathComponent
        status = "Indexing \(filename)…"

        do {
            let chunks = FileIngester.chunk(url: url, filename: filename)
            guard !chunks.isEmpty else {
                status = "Could not read \(filename)"
                return
            }

            // Mint a stable UUID for this import. Two files named README.md
            // get different IDs; renaming a file does not affect its docs.
            let sourceId = UUID().uuidString

            let docs = chunks.enumerated().map { i, text in
                DocumentInfo(
                    id:   "\(sourceId)::chunk::\(i)",
                    text: text,
                    metadata: [
                        "sourceId":    sourceId,   // used for precise removal
                        "displayName": filename,   // used for display only
                        "chunk":       "\(i)",
                    ]
                )
            }

            let (added, updated) = try await session.addDocs(docs)
            guard sessionGeneration == generation else { return }

            try await session.save(toCachePath: cacheDir(for: currentProjectId ?? ""))
            guard sessionGeneration == generation else { return }

            let source = IndexedSource(
                id:       sourceId,
                name:     filename,
                kind:     .file,
                docCount: added + updated,
                addedAt:  Date()
            )
            upsertSource(source)
            status = "Indexed \(added + updated) chunks from \(filename). Total: \(session.docCount) docs."
        } catch {
            status = "Ingest failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Ingest: contacts

    func ingestContacts() async {
        guard let session else { status = "Not connected"; return }
        let generation = sessionGeneration
        isWorking = true
        defer { isWorking = false }
        status = "Requesting contacts permission…"

        let store = CNContactStore()
        let auth  = CNContactStore.authorizationStatus(for: .contacts)

        if auth == .notDetermined {
            do {
                let granted = try await store.requestAccess(for: .contacts)
                guard granted else { status = "Contacts access denied."; return }
            } catch {
                status = "Contacts error: \(error.localizedDescription)"
                return
            }
        } else if auth != .authorized {
            status = "Contacts access denied. Enable in Settings → Privacy."
            return
        }

        status = "Fetching contacts…"
        // CNContactNoteKey requires the restricted "Contacts Notes" entitlement
        // (explicit Apple approval). Omitted here so the demo builds and runs
        // for any developer without special provisioning.
        let keys: [CNKeyDescriptor] = [
            CNContactGivenNameKey        as CNKeyDescriptor,
            CNContactFamilyNameKey       as CNKeyDescriptor,
            CNContactOrganizationNameKey as CNKeyDescriptor,
            CNContactJobTitleKey         as CNKeyDescriptor,
            CNContactEmailAddressesKey   as CNKeyDescriptor,
        ]

        do {
            var docs: [DocumentInfo] = []
            let request = CNContactFetchRequest(keysToFetch: keys)
            try store.enumerateContacts(with: request) { contact, _ in
                let name = "\(contact.givenName) \(contact.familyName)".trimmingCharacters(in: .whitespaces)
                guard !name.isEmpty else { return }

                // Build a rich text blob — the more context, the better retrieval
                var parts = [name]
                if !contact.organizationName.isEmpty { parts.append("works at \(contact.organizationName)") }
                if !contact.jobTitle.isEmpty          { parts.append("title: \(contact.jobTitle)") }
                if let email = contact.emailAddresses.first {
                    parts.append("email: \(email.value as String)")
                }

                docs.append(DocumentInfo(
                    id:       "contact::\(contact.identifier)",
                    text:     parts.joined(separator: ". "),
                    metadata: [
                        "sourceId":    "contacts",   // fixed logical source
                        "displayName": name,
                    ]
                ))
            }

            guard !docs.isEmpty else { status = "No contacts found."; return }

            // Remove stale docs for contacts that have been deleted from the
            // device since the last import. Diff the incoming IDs against what
            // is already in the index so we don't leave ghost entries.
            let incomingIds = Set(docs.map(\.id))
            let existingContactIds = (try? await session.getDocs())
                .map { all in Set(all.filter { $0.id.hasPrefix("contact::") }.map(\.id)) }
                ?? []
            let stale = existingContactIds.subtracting(incomingIds)
            if !stale.isEmpty {
                _ = try await session.deleteDocs(Array(stale))
            }
            guard sessionGeneration == generation else { return }

            status = "Indexing \(docs.count) contacts…"
            let (added, updated) = try await session.addDocs(docs)
            guard sessionGeneration == generation else { return }

            try await session.save(toCachePath: cacheDir(for: currentProjectId ?? ""))
            guard sessionGeneration == generation else { return }

            let source = IndexedSource(
                id:       "contacts",
                name:     "Contacts (\(docs.count))",
                kind:     .contacts,
                docCount: added + updated,
                addedAt:  Date()
            )
            upsertSource(source)
            status = "Indexed \(added + updated) contacts. Total: \(session.docCount) docs."
        } catch {
            status = "Contacts ingest failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Search

    func search(query: String, topK: Int = 10) async {
        guard let session, !query.trimmingCharacters(in: .whitespaces).isEmpty else {
            searchHits = []
            return
        }
        do {
            let result = try await session.query(query, options: .init(topK: topK))
            searchHits = result.docs.map { doc in
                SearchHit(
                    id:         doc.id,
                    sourceName: doc.metadata?["displayName"] ?? doc.id,
                    excerpt:    String(doc.text.prefix(220)),
                    score:      doc.score
                )
            }
            status = "\(result.docs.count) results in \(result.timeMs)ms"
        } catch {
            searchHits = []
            status = "Search error: \(error.localizedDescription)"
        }
    }

    // MARK: - LLM answer (RAG: Moss retrieval → OpenAI synthesis)

    /// Retrieve top hits from Moss, then send them as context to OpenAI.
    /// Populates `llmAnswer`. `searchHits` is also populated so both views
    /// can be shown simultaneously.
    func generateAnswer(query: String) async {
        guard !query.trimmingCharacters(in: .whitespaces).isEmpty else {
            llmAnswer = ""
            return
        }
        isAnswering = true
        llmAnswer   = ""
        defer { isAnswering = false }

        // Step 1 — Moss retrieval (top 8 for LLM context)
        await search(query: query, topK: 8)
        let context = searchHits

        guard !context.isEmpty else {
            llmAnswer = "No relevant documents found for: \"\(query)\""
            return
        }

        // Step 2 — OpenAI synthesis
        do {
            let response = try await LLMService.answer(
                query:  query,
                hits:   context,
                apiKey: openAIKey
            )
            llmAnswer = response.answer
            status    = "Answer via \(response.model) · \(response.tokens) tokens"
        } catch {
            llmAnswer = "LLM error: \(error.localizedDescription)"
        }
    }

    // MARK: - Cloud sync

    func syncToCloud() async {
        guard let session, let client else { return }
        // Guard on the live doc count, not just the source list. If iOS purged
        // Application Support (shouldn't happen, but defensive), sources would
        // still be populated while the index is empty — pushing would silently
        // zero out the cloud copy.
        guard session.docCount > 0 else {
            status = "Nothing to sync — index is empty."
            return
        }
        isWorking = true
        defer { isWorking = false }
        status = "Pushing to cloud…"

        do {
            let push = try await session.pushIndex()
            // Poll until ready
            for _ in 0..<30 {
                let st = try await client.getJobStatus(push.jobId)
                if ["ready", "completed", "done", "succeeded"]
                    .contains(st.status.lowercased()) {
                    cloudSynced = true
                    status = "Synced ✓ — index: \(push.indexName)"
                    return
                }
                try await Task.sleep(nanoseconds: 1_000_000_000)
            }
            status = "Sync timed out. Try again."
        } catch {
            status = "Sync failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Remove a source

    func removeSource(_ source: IndexedSource) async {
        guard let session else { return }
        let generation = sessionGeneration
        isWorking = true
        defer { isWorking = false }
        status = "Removing \(source.name)…"

        do {
            // Filter by the stable sourceId stored in metadata, not the
            // display name, so two files with the same name stay independent.
            let allDocs = try await session.getDocs()
            let toDelete = allDocs
                .filter { doc in
                    if source.kind == .contacts {
                        return doc.id.hasPrefix("contact::")
                    }
                    return doc.metadata?["sourceId"] == source.id
                }
                .map(\.id)

            guard sessionGeneration == generation else { return }

            if !toDelete.isEmpty {
                _ = try await session.deleteDocs(toDelete)
                guard sessionGeneration == generation else { return }
                try await session.save(toCachePath: cacheDir(for: currentProjectId ?? ""))
                guard sessionGeneration == generation else { return }
            }

            sources.removeAll { $0.id == source.id }
            saveSources()
            status = "Removed \(source.name). Total: \(session.docCount) docs."
        } catch {
            status = "Remove failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Persistence helpers

    private func cacheDir(for projectId: String) -> String {
        // Application Support is not purged by iOS, unlike Caches.
        // A purged Caches dir would leave sources populated but the index
        // empty, allowing syncToCloud() to overwrite the cloud copy with
        // zero documents.
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir  = base.appendingPathComponent("moss-\(projectId)", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.path
    }

    private func loadSources() -> [IndexedSource] {
        guard let pid = currentProjectId,
              let data = UserDefaults.standard.data(forKey: sourcesKey(for: pid)),
              let decoded = try? JSONDecoder().decode([IndexedSource].self, from: data)
        else { return [] }
        return decoded
    }

    private func saveSources() {
        guard let pid = currentProjectId else { return }
        if let data = try? JSONEncoder().encode(sources) {
            UserDefaults.standard.set(data, forKey: sourcesKey(for: pid))
        }
    }

    private func upsertSource(_ source: IndexedSource) {
        if let idx = sources.firstIndex(where: { $0.id == source.id }) {
            sources[idx] = source
        } else {
            sources.append(source)
        }
        saveSources()
        indexDocCount = session?.docCount ?? 0
    }
}
