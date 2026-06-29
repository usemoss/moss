import Foundation
import Moss
import Contacts

// MARK: - Data models

struct IndexedSource: Identifiable, Codable {
    let id: String          // stable key (filename or contact group)
    let name: String        // display name
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

    @Published var sources:     [IndexedSource] = []
    @Published var searchHits:  [SearchHit]     = []
    @Published var status:      String          = "Not connected"
    @Published var isWorking:   Bool            = false
    @Published var cloudSynced: Bool            = false

    // ── Private Moss objects ──────────────────────────────────────────────

    private var client:  MossClient?
    private var session: MossSession?

    // Persisted source list so we survive app kills
    private let sourcesKey = "indexed_sources_v1"

    // MARK: - Setup

    func setup(projectId: String, projectKey: String) async {
        guard client == nil else { return }   // already set up
        isWorking = true
        status    = "Connecting…"
        defer { isWorking = false }

        do {
            client  = try MossClient(projectId: projectId, projectKey: projectKey)
            session = try await client!.session("personal-context")

            // Restore on-device index from disk (survives app restarts, no network)
            try? await session!.loadFromDisk(cachePath: cacheDir())

            // Restore source list from UserDefaults
            sources = loadSources()

            status = "Ready — \(session!.docCount) documents indexed"
        } catch {
            status = "Setup failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Ingest: files

    func ingestFile(url: URL) async {
        guard let session else { status = "Not connected"; return }
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

            // Build DocumentInfo objects.
            // metadata is [String: String] — store the filename so we can
            // surface it in search results.
            let docs = chunks.enumerated().map { i, text in
                DocumentInfo(
                    id: "\(filename)::chunk::\(i)",
                    text: text,
                    metadata: ["source": filename, "chunk": "\(i)"]
                )
            }

            let (added, updated) = try await session.addDocs(docs)

            // Save to disk immediately so the index survives a kill
            try await session.save(toCachePath: cacheDir())

            let source = IndexedSource(
                id:       filename,
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
        let keys: [CNKeyDescriptor] = [
            CNContactGivenNameKey   as CNKeyDescriptor,
            CNContactFamilyNameKey  as CNKeyDescriptor,
            CNContactOrganizationNameKey as CNKeyDescriptor,
            CNContactJobTitleKey    as CNKeyDescriptor,
            CNContactNoteKey        as CNKeyDescriptor,
            CNContactEmailAddressesKey as CNKeyDescriptor,
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
                if !contact.note.isEmpty { parts.append("notes: \(contact.note)") }

                docs.append(DocumentInfo(
                    id:       "contact::\(contact.identifier)",
                    text:     parts.joined(separator: ". "),
                    metadata: ["source": "Contacts", "name": name]
                ))
            }

            guard !docs.isEmpty else { status = "No contacts found."; return }

            status = "Indexing \(docs.count) contacts…"
            let (added, updated) = try await session.addDocs(docs)
            try await session.save(toCachePath: cacheDir())

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

    func search(query: String) async {
        guard let session, !query.trimmingCharacters(in: .whitespaces).isEmpty else {
            searchHits = []
            return
        }
        do {
            let result = try await session.query(query, options: .init(topK: 10))
            searchHits = result.docs.map { doc in
                SearchHit(
                    id:         doc.id,
                    sourceName: doc.metadata?["source"] ?? doc.id,
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

    // MARK: - Cloud sync

    func syncToCloud() async {
        guard let session, let client else { return }
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
        isWorking = true
        defer { isWorking = false }
        status = "Removing \(source.name)…"

        do {
            // Delete all docs whose "source" metadata matches
            let allDocs = try await session.getDocs()
            let toDelete = allDocs
                .filter { $0.metadata?["source"] == source.name || $0.id.hasPrefix("contact::") && source.kind == .contacts }
                .map(\.id)

            if !toDelete.isEmpty {
                _ = try await session.deleteDocs(toDelete)
                try await session.save(toCachePath: cacheDir())
            }

            sources.removeAll { $0.id == source.id }
            saveSources()
            status = "Removed \(source.name). Total: \(session.docCount) docs."
        } catch {
            status = "Remove failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Persistence helpers

    private func cacheDir() -> String {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].path
    }

    private func loadSources() -> [IndexedSource] {
        guard let data = UserDefaults.standard.data(forKey: sourcesKey),
              let decoded = try? JSONDecoder().decode([IndexedSource].self, from: data)
        else { return [] }
        return decoded
    }

    private func saveSources() {
        if let data = try? JSONEncoder().encode(sources) {
            UserDefaults.standard.set(data, forKey: sourcesKey)
        }
    }

    private func upsertSource(_ source: IndexedSource) {
        if let idx = sources.firstIndex(where: { $0.id == source.id }) {
            sources[idx] = source
        } else {
            sources.append(source)
        }
        saveSources()
    }
}
