'use client'

import { useState, useTransition, useRef } from 'react';
import Image from 'next/image';
import {
  Plus, Trash2, CheckCircle2, Loader2,
  Search, Zap, Database, AlertCircle, Ghost, Upload,
} from 'lucide-react';
import { createMossIndex, searchMoss, loadMossIndex, type DocInput } from './actions';

const INITIAL_DOCS: DocInput[] = [
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
  const [docs, setDocs] = useState<DocInput[]>(INITIAL_DOCS);
  const [modifiedIds, setModifiedIds] = useState<Set<string>>(new Set());
  const indexName = 'demo-index';
  const [isIndexLoaded, setIsIndexLoaded] = useState(false);
  const [buildState, setBuildState] = useState<'idle' | 'building' | 'done' | 'error'>('idle');
  const [buildMessage, setBuildMessage] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
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
      const response = await createMossIndex(indexName, docsToBuild);

      if (response.success) {
        setBuildState('done');
        setModifiedIds(prev => {
          const next = new Set(prev);
          docsToBuild.forEach(d => next.delete(d.id));
          return next;
        });
        setIsIndexLoaded(false);
        setSearchResults([]);
        setHasSearched(false);
      } else {
        setBuildState('error');
        setBuildMessage(response.error);
      }
    });
  };

  const [isLoadingIndex, startLoadingIndex] = useTransition();

  const loadIndexIntoMemory = () => {
    if (isIndexLoaded || isLoadingIndex) return;

    startLoadingIndex(async () => {
      const response = await loadMossIndex(indexName);

      if (response.success) {
        setIsIndexLoaded(true);
      } else {
        setSearchError(response.error || 'Failed to load index');
      }
    });
  };

  // ── Search ─────────────────────────────────────────────────────────────────

  const handleSearch = async (e: { preventDefault(): void }) => {
    e.preventDefault();
    if (!searchQuery.trim() || isSearching || !isIndexLoaded) return;

    setSearchError(null);
    setHasSearched(true);

    startSearch(async () => {
      const response = await searchMoss(searchQuery, indexName);

      if (response.success) {
        setSearchResults(response.docs || []);
      } else {
        setSearchError(response.error);
        setSearchResults([]);
      }
    });
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
                <div className="status-box status-success">
                  <CheckCircle2 size={14} />
                  <span>Index ready to search</span>
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
                  placeholder={isIndexLoaded ? 'What would you like to know?' : 'Load index first…'}
                  disabled={!isIndexLoaded}
                />
                <button
                  type="submit"
                  className="search-btn"
                  disabled={isSearching || !isIndexLoaded || !searchQuery.trim()}
                >
                  {isSearching ? <Loader2 className="spinner" size={14} /> : <Search size={14} />}
                </button>
              </div>
            </form>

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

              {!isSearching && searchResults.map((result) => (
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

              {!isSearching && hasSearched && searchResults.length === 0 && !searchError && (
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
      </div>

      <footer>Made with ⚡ Moss</footer>
    </main>
  );
}
