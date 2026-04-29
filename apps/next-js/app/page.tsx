'use client'

import { useState, useTransition, useRef, useMemo, useEffect } from 'react';
import Image from 'next/image';
import {
  Plus, Trash2, CheckCircle2, Loader2,
  Search, Zap, Database, AlertCircle, Ghost, Upload, Settings,
} from 'lucide-react';
import { MossClient, DocumentInfo, SearchResult } from '@moss-dev/moss-web';


const INITIAL_DOCS: DocumentInfo[] = [
  { id: 'doc-1', text: 'Moss is a semantic search runtime for conversational AI agents with sub-10ms retrieval latency at production scale.' },
  { id: 'doc-2', text: 'Vector embeddings transform text into high-dimensional vectors that capture semantic meaning and context relationships.' },
  { id: 'doc-3', text: 'Retrieval-Augmented Generation combines vector search with large language models for accurate, grounded responses.' },
  { id: 'doc-4', text: 'The Moss SDK is available for JavaScript, TypeScript, and Python, supporting both browser and server environments.' },
  { id: 'doc-5', text: 'Sub-10ms latency retrieval eliminates the delay between user query and LLM response, enabling true real-time interaction.' },
];

function Skeleton() {
  return (
    <div className="skeleton-card" aria-hidden>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <div className="skeleton-line medium" style={{ flex: 1 }} />
        <div className="skeleton-line short" style={{ width: '20%' }} />
      </div>
      <div className="skeleton-line long" />
      <div className="skeleton-line full" />
    </div>
  );
}

export default function MossDemo() {
  // ── Credentials ────────────────────────────────────────────────────────────
  const [credentials, setCredentials] = useState({ projectId: '', projectKey: '' });
  const [credInput, setCredInput] = useState({ projectId: '', projectKey: '' });
  const [showCreds, setShowCreds] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem('moss_credentials');
      if (saved) {
        const p = JSON.parse(saved) as { projectId: string; projectKey: string };
        if (p.projectId && p.projectKey) { setCredentials(p); setCredInput(p); setShowCreds(false); }
      }
    } catch {}
  }, []);

  const client = useMemo(() =>
    credentials.projectId && credentials.projectKey
      ? new MossClient(credentials.projectId, credentials.projectKey)
      : null,
    [credentials.projectId, credentials.projectKey]
  );

  const [docs, setDocs] = useState<DocumentInfo[]>(INITIAL_DOCS);
  const [modifiedIds, setModifiedIds] = useState<Set<string>>(new Set(INITIAL_DOCS.map(d => d.id)));
  const indexNameRef = useRef(
    `demo-index-${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`
  );
  const indexName = indexNameRef.current;
  const [isIndexLoaded, setIsIndexLoaded] = useState(false);
  const [buildState, setBuildState] = useState<'idle' | 'building' | 'done' | 'error'>('idle');
  const [buildMessage, setBuildMessage] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [alpha, setAlpha] = useState(0.5);
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const idCounter = useRef(INITIAL_DOCS.length + 1);

  const [isBuilding, startBuild] = useTransition();
  const [isSearching, startSearch] = useTransition();

  // ── Document operations ────────────────────────────────────────────────────

  const updateDocText = (id: string, newText: string) => {
    setDocs(prev => prev.map(d => d.id === id ? { ...d, text: newText } : d));
    setModifiedIds(prev => new Set(prev).add(id));
    setIsIndexLoaded(false);
  };

  const removeDoc = (id: string) => {
    setDocs(prev => prev.filter(d => d.id !== id));
    setModifiedIds(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const addNewDoc = () => {
    const newId = `doc-${idCounter.current++}`;
    setDocs(prev => [...prev, { id: newId, text: '' }]);
    setModifiedIds(prev => new Set(prev).add(newId));
  };

  // ── Index operations ───────────────────────────────────────────────────────

  const buildIndex = (singleDocId?: string) => {
    const docsToBuild = singleDocId
      ? docs.filter(d => d.id === singleDocId && d.text.trim())
      : docs.filter(d => d.text.trim());

    if (docsToBuild.length === 0) {
      setBuildState('error');
      setBuildMessage('No documents to index');
      return;
    }

    setBuildState('building');
    setBuildMessage(null);

    startBuild(async () => {
      if (!client) return;
      try {
        // Delete existing index first to avoid conflicts
        try { await client.deleteIndex(indexName); } catch {}
        await client.createIndex(indexName, docsToBuild, { modelId: 'moss-minilm' });
        setBuildState('done');
        setModifiedIds(prev => {
          const next = new Set(prev);
          docsToBuild.forEach(d => next.delete(d.id));
          return next;
        });
        setIsIndexLoaded(false);
        setSearchResults(null);
        setHasSearched(false);
      } catch (error) {
        console.error('Build index error:', error);
        setBuildState('error');
        setBuildMessage(error instanceof Error ? error.message : String(error));
      }
    });
  };

  const [isLoadingIndex, startLoadingIndex] = useTransition();

  const loadIndexIntoMemory = () => {
    if (isIndexLoaded || isLoadingIndex) return;

    startLoadingIndex(async () => {
      if (!client) return;
      try {
        await client.loadIndex(indexName);
        setIsIndexLoaded(true);
      } catch (error) {
        setSearchError(error instanceof Error ? error.message : 'Failed to load index');
      }
    });
  };

  // ── Search ─────────────────────────────────────────────────────────────────

  const runSearch = (query: string) => {
    startSearch(async () => {
      if (!client) return;
      try {
        const results = await client.query(indexName, query, { topK, alpha });
        setSearchResults(results);
      } catch (error) {
        console.error('Moss Search Error:', error);
        setSearchError(error instanceof Error ? error.message : 'An unknown error occurred');
        setSearchResults(null);
      }
    });
  };

  // Keystroke search
  useEffect(() => {
    if (!isIndexLoaded || !searchQuery.trim()) return;
    setSearchError(null);
    setHasSearched(true);
    runSearch(searchQuery);
  }, [searchQuery, isIndexLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-run immediately when topK/alpha change (no debounce needed)
  useEffect(() => {
    if (hasSearched && searchQuery.trim() && isIndexLoaded) runSearch(searchQuery);
  }, [topK, alpha]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e: { preventDefault(): void }) => {
    e.preventDefault();
    if (!searchQuery.trim() || isSearching || !isIndexLoaded) return;
    setSearchError(null);
    setHasSearched(true);
    runSearch(searchQuery);
  };

  const saveCredentials = () => {
    try { localStorage.setItem('moss_credentials', JSON.stringify(credInput)); } catch {}
    setCredentials(credInput);
    setBuildState('idle');
    setBuildMessage(null);
    setIsIndexLoaded(false);
    setSearchResults(null);
    setHasSearched(false);
    setShowCreds(false);
  };

  const validDocCount = docs.filter(d => d.text.trim()).length;
  const hasModified = modifiedIds.size > 0;

  return (
    <main>
      <div className="container">
        {/* Header */}
        <header className="logo-section">
          <div>
            <Image
              src="/moss-brand.png"
              alt="Moss Logo"
              width={320}
              height={100}
              className="logo-icon"
              priority
              style={{
                objectFit: 'contain',
                maxWidth: '100%',
                height: 'auto'
              }}
            />
          </div>
          <h1 className="title">
            Real-time semantic search for Conversational AI
          </h1>
          <p className="subtitle">
            Build and search your knowledge base with sub-10ms latency
          </p>
        </header>

        {!client ? (
          // ── Connect screen ───────────────────────────────────────────────
          <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem 0' }}>
            <div className="panel" style={{ width: '100%', maxWidth: '460px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <h2 className="panel-title">Connect your Moss account</h2>
              <p style={{ fontSize: '0.875rem', opacity: 0.65, margin: 0 }}>
                Enter your Project ID and Project Key to get started.
              </p>
              <input
                className="doc-textarea"
                style={{ padding: '0.5rem 0.75rem', borderRadius: '0.375rem' }}
                placeholder="Project ID"
                value={credInput.projectId}
                onChange={e => setCredInput(p => ({ ...p, projectId: e.target.value }))}
              />
              <input
                className="doc-textarea"
                style={{ padding: '0.5rem 0.75rem', borderRadius: '0.375rem' }}
                placeholder="Project Key"
                type="password"
                value={credInput.projectKey}
                onChange={e => setCredInput(p => ({ ...p, projectKey: e.target.value }))}
              />
              <button
                className="btn btn-primary build-button"
                onClick={saveCredentials}
                disabled={!credInput.projectId || !credInput.projectKey}
              >
                Connect
              </button>
              <p style={{ fontSize: '0.72rem', opacity: 0.45, margin: 0, textAlign: 'center' }}>
                Stored in your browser only — never sent to any server.
              </p>
            </div>
          </div>
        ) : (
          // ── Demo ─────────────────────────────────────────────────────────
          <>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowCreds(v => !v)}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
              >
                <Settings size={13} />
                {showCreds ? 'Cancel' : 'Change credentials'}
              </button>
            </div>
            {showCreds && (
              <div className="panel" style={{ marginBottom: '1.5rem', display: 'flex', gap: '0.75rem', alignItems: 'flex-end' }}>
                <input
                  className="doc-textarea"
                  style={{ flex: 1, padding: '0.5rem 0.75rem', borderRadius: '0.375rem' }}
                  placeholder="Project ID"
                  value={credInput.projectId}
                  onChange={e => setCredInput(p => ({ ...p, projectId: e.target.value }))}
                />
                <input
                  className="doc-textarea"
                  style={{ flex: 1, padding: '0.5rem 0.75rem', borderRadius: '0.375rem' }}
                  placeholder="Project Key"
                  type="password"
                  value={credInput.projectKey}
                  onChange={e => setCredInput(p => ({ ...p, projectKey: e.target.value }))}
                />
                <button
                  className="btn btn-primary"
                  onClick={saveCredentials}
                  disabled={!credInput.projectId || !credInput.projectKey}
                >
                  Save
                </button>
              </div>
            )}
        {/* Main grid */}
        <div className="demo-grid">
          {/* Left: Document editor */}
          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title">Documents</h2>
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                <span className="doc-count-badge">{validDocCount}</span>
                <button
                  className="btn add-btn"
                  onClick={addNewDoc}
                  disabled={isBuilding}
                  title="Add new document"
                >
                  <Plus size={14} /> Add
                </button>
              </div>
            </div>

            <div className="doc-list-editor">
              {docs.length === 0 && (
                <div className="doc-empty">
                  Start by adding your first document
                </div>
              )}

              {docs.map(doc => (
                <div
                  key={doc.id}
                  className={`doc-item ${modifiedIds.has(doc.id) ? 'modified' : ''}`}
                >
                  <div className="doc-header">
                    <span className="doc-id">{doc.id}</span>
                    <div className="doc-actions">
                      {modifiedIds.has(doc.id) && (
                        <button
                          className="btn-icon update"
                          onClick={() => buildIndex(doc.id)}
                          disabled={isBuilding || !doc.text.trim()}
                          title="Update this document"
                        >
                          <Upload size={14} />
                        </button>
                      )}
                      <button
                        className="btn-icon"
                        onClick={() => removeDoc(doc.id)}
                        disabled={isBuilding}
                        title="Remove document"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <textarea
                    className="doc-textarea"
                    value={doc.text}
                    onChange={e => updateDocText(doc.id, e.target.value)}
                    placeholder="Type your content here…"
                    rows={3}
                  />
                </div>
              ))}
            </div>

            {/* Build section */}
            <div className="build-section">
              <button
                className="btn btn-primary build-button"
                onClick={() => buildIndex()}
                disabled={isBuilding || validDocCount === 0 || !hasModified}
              >
                {isBuilding && <Loader2 className="spinner" size={16} />}
                {!isBuilding && <Database size={16} />}
                <span>{buildState === 'done' ? 'Rebuild' : 'Build'} Index</span>
              </button>

              {buildState === 'error' && buildMessage && (
                <div className="status-box status-error">
                  <AlertCircle size={14} />
                  <span>{buildMessage}</span>
                </div>
              )}

              {buildState === 'done' && (
                <div className="status-box status-success" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '0.2rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <CheckCircle2 size={14} />
                    Index ready to search
                  </span>
                  <span style={{ fontSize: '0.72rem', opacity: 0.6, fontFamily: 'monospace' }}>{indexName}</span>
                </div>
              )}
            </div>
          </section>

          {/* Right: Search interface */}
          <section className="panel">
            {/* Load section */}
            <div className="load-section">
              <button
                className="btn btn-secondary"
                onClick={loadIndexIntoMemory}
                disabled={isIndexLoaded || isLoadingIndex || !buildState || buildState !== 'done'}
                style={{ width: '100%' }}
              >
                {isIndexLoaded ? (
                  <>
                    <CheckCircle2 size={14} />
                    Index Loaded
                  </>
                ) : isLoadingIndex ? (
                  <>
                    <Loader2 className="spinner" size={14} />
                    Loading Index
                  </>
                ) : (
                  <>
                    <Database size={14} />
                    Load Index
                  </>
                )}
              </button>
              <div className={`load-status ${isIndexLoaded ? 'ready' : ''}`}>
                {isIndexLoaded ? '✓ Ready' : buildState === 'done' ? 'Ready to load' : 'Build first'}
              </div>
            </div>

            {/* Search */}
            <h2 className="panel-title" style={{ marginBottom: '1.5rem' }}>
              Search
            </h2>

            <form onSubmit={handleSearch} className="search-form">
              <div className={`search-group ${!isIndexLoaded ? 'disabled' : ''}`}>
                <div className="search-icon">
                  <Search size={16} />
                </div>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder={isIndexLoaded ? 'Type to search…' : 'Load index first…'}
                  disabled={!isIndexLoaded}
                />
                <div className="search-btn" style={{ pointerEvents: 'none' }}>
                  {isSearching ? <Loader2 className="spinner" size={14} /> : <Search size={14} />}
                </div>
              </div>
            </form>

            {/* Query options */}
            <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', padding: '0.75rem 0', fontSize: '0.8rem', opacity: isIndexLoaded ? 1 : 0.4 }}>
              <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <span style={{ opacity: 0.6, whiteSpace: 'nowrap' }}>Top K</span>
                <input
                  type="number"
                  min={1} max={20}
                  value={topK}
                  onChange={e => setTopK(Math.max(1, Math.min(20, Number(e.target.value))))}
                  disabled={!isIndexLoaded}
                  style={{ width: '3.5rem', padding: '0.2rem 0.4rem', borderRadius: '0.25rem', border: '1px solid var(--border)', background: 'var(--input-bg, transparent)', color: 'inherit', textAlign: 'center' }}
                />
              </label>
              <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flex: 1 }}>
                <span style={{ opacity: 0.6, whiteSpace: 'nowrap' }}>Keyword</span>
                <input
                  type="range"
                  min={0} max={1} step={0.05}
                  value={alpha}
                  onChange={e => setAlpha(Number(e.target.value))}
                  disabled={!isIndexLoaded}
                  style={{ flex: 1, accentColor: 'var(--color-primary, #6366f1)' }}
                />
                <span style={{ opacity: 0.6, whiteSpace: 'nowrap' }}>Semantic</span>
              </label>
              <span style={{ opacity: 0.4, minWidth: '2.5rem', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                α {alpha.toFixed(2)}
              </span>
            </div>

            {/* Results */}
            <div className="results-container" aria-live="polite">
              {searchError && (
                <div className="status-box status-error" style={{ marginBottom: '1rem' }}>
                  <AlertCircle size={14} />
                  {searchError}
                </div>
              )}

              {isSearching && (
                <div className="skeleton-list">
                  <Skeleton />
                  <Skeleton />
                  <Skeleton />
                </div>
              )}

              {!isSearching && searchResults?.docs.map((result) => (
                <div
                  key={result.id}
                  className="result-item"
                >
                  <div className="result-meta">
                    <span className={`result-score ${result.score < 0.75 ? 'low' : ''}`}>
                      <Zap size={12} fill="currentColor" />
                      {(result.score * 100).toFixed(0)}%
                    </span>
                    <span className="result-id">{result.id}</span>
                  </div>
                  <p className="result-text">{result.text}</p>
                </div>
              ))}

              {!isSearching && hasSearched && !searchResults?.docs.length && !searchError && (
                <div className="empty-state">
                  <Ghost size={40} />
                  <p className="empty-text">No results found. Try a different query.</p>
                </div>
              )}

              {!isSearching && !hasSearched && isIndexLoaded && (
                <div className="empty-state">
                  <Search size={40} />
                  <p className="empty-text">Ready to search your documents</p>
                </div>
              )}
            </div>
          </section>
        </div>
          </>
        )}
      </div>

      <footer>Made with ⚡ Moss</footer>
    </main>
  );
}
