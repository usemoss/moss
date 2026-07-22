using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Moss.Interop;

namespace Moss;

/// <summary>
/// Client for Moss — fast on-device retrieval. Wraps the native <c>libmoss</c>
/// runtime and exposes an async API for index management, hybrid search, and
/// metadata filtering.
/// </summary>
/// <remarks>
/// The client owns native resources; dispose it when finished. Native calls are
/// blocking and are marshaled onto the thread pool; access to the underlying
/// handle is serialized, so a single client may be shared across tasks.
/// </remarks>
public sealed class MossClient : IDisposable
{
    private readonly NativeClient _native;
    private int _disposed;

    /// <summary>Create a client for the given Moss project credentials.</summary>
    /// <exception cref="ArgumentException">A credential is null or empty.</exception>
    /// <exception cref="MossException">The native runtime failed to initialize.</exception>
    public MossClient(string projectId, string projectKey)
    {
        if (string.IsNullOrEmpty(projectId)) throw new ArgumentException("projectId is required", nameof(projectId));
        if (string.IsNullOrEmpty(projectKey)) throw new ArgumentException("projectKey is required", nameof(projectKey));
        _native = new NativeClient(projectId, projectKey);
    }

    // ---- Management ------------------------------------------------------

    /// <summary>Create a new index and enqueue the supplied documents for indexing.</summary>
    public Task<MutationResult> CreateIndexAsync(
        string name, IEnumerable<DocumentInfo> docs, string? modelId = null, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        IReadOnlyList<DocumentInfo> list = Materialize(docs, nameof(docs));
        return Run(() => _native.CreateIndex(name, list, modelId), cancellationToken);
    }

    /// <summary>Add (or upsert) documents to an existing index.</summary>
    public Task<MutationResult> AddDocsAsync(
        string name, IEnumerable<DocumentInfo> docs, MutationOptions? options = null, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        IReadOnlyList<DocumentInfo> list = Materialize(docs, nameof(docs));
        return Run(() => _native.AddDocs(name, list, options), cancellationToken);
    }

    /// <summary>Delete documents from an index by id.</summary>
    public Task<MutationResult> DeleteDocsAsync(
        string name, IEnumerable<string> docIds, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        IReadOnlyList<string> ids = Materialize(docIds, nameof(docIds));
        return Run(() => _native.DeleteDocs(name, ids), cancellationToken);
    }

    /// <summary>Fetch documents from an index by id.</summary>
    public Task<IReadOnlyList<DocumentInfo>> GetDocsAsync(
        string name, IEnumerable<string> docIds, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        IReadOnlyList<string> ids = Materialize(docIds, nameof(docIds));
        return Run(() => _native.GetDocs(name, ids), cancellationToken);
    }

    /// <summary>Get metadata for a single index.</summary>
    public Task<IndexInfo> GetIndexAsync(string name, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        return Run(() => _native.GetIndex(name), cancellationToken);
    }

    /// <summary>List all indexes in the project.</summary>
    public Task<IReadOnlyList<IndexInfo>> ListIndexesAsync(CancellationToken cancellationToken = default)
        => Run(() => _native.ListIndexes(), cancellationToken);

    /// <summary>Delete an index. Returns true if an index was removed.</summary>
    public Task<bool> DeleteIndexAsync(string name, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        return Run(() => _native.DeleteIndex(name), cancellationToken);
    }

    /// <summary>Poll the status of an asynchronous indexing job.</summary>
    public Task<JobStatusResponse> GetJobStatusAsync(string jobId, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(jobId)) throw new ArgumentException("jobId is required", nameof(jobId));
        return Run(() => _native.GetJobStatus(jobId), cancellationToken);
    }

    // ---- Local runtime ---------------------------------------------------

    /// <summary>Load an index into the local runtime so it can be queried on-device.</summary>
    public Task<IndexInfo> LoadIndexAsync(
        string name, LoadIndexOptions? options = null, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        return Run(() => _native.LoadIndex(name, options), cancellationToken);
    }

    /// <summary>Unload a previously loaded index from the local runtime.</summary>
    public Task UnloadIndexAsync(string name, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        return Run(() => { _native.UnloadIndex(name); return true; }, cancellationToken);
    }

    /// <summary>Refresh a locally loaded index against the latest cloud state.</summary>
    public Task<RefreshResult> RefreshIndexAsync(string name, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        return Run(() => _native.RefreshIndex(name), cancellationToken);
    }

    /// <summary>Run a hybrid (lexical + semantic) query against a loaded index.</summary>
    public Task<SearchResult> QueryAsync(
        string name, string query, QueryOptions? options = null, CancellationToken cancellationToken = default)
    {
        RequireName(name);
        if (query is null) throw new ArgumentNullException(nameof(query));
        QueryOptions opts = options ?? new QueryOptions();
        return Run(() => _native.Query(name, query, opts), cancellationToken);
    }

    // ---- Helpers ---------------------------------------------------------

    private Task<T> Run<T>(Func<T> action, CancellationToken cancellationToken)
    {
        ThrowIfDisposed();
        return Task.Run(action, cancellationToken);
    }

    private static void RequireName(string name)
    {
        if (string.IsNullOrEmpty(name)) throw new ArgumentException("index name is required", nameof(name));
    }

    private static IReadOnlyList<T> Materialize<T>(IEnumerable<T> items, string paramName)
    {
        if (items is null) throw new ArgumentNullException(paramName);
        return items as IReadOnlyList<T> ?? items.ToList();
    }

    private void ThrowIfDisposed()
    {
        if (Volatile.Read(ref _disposed) != 0) throw new ObjectDisposedException(nameof(MossClient));
    }

    /// <summary>Release the native client and its resources.</summary>
    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0) return;
        _native.Dispose();
    }
}
