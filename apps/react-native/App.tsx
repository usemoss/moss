import { useCallback, useEffect, useState } from 'react'
import {
  ActivityIndicator,
  FlatList,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import type { MossClient } from '@moss-dev/moss-web'

const INDEX_NAME = 'emoji-search-v1'

const PROJECT_ID = process.env.EXPO_PUBLIC_MOSS_PROJECT_ID ?? ''
const PROJECT_KEY = process.env.EXPO_PUBLIC_MOSS_PROJECT_KEY ?? ''

// ── Types ──────────────────────────────────────────────────────────────────

type EmojiResult = {
  id: string
  score: number
  metadata: {
    character: string
    name: string
    description: string
    tags: string
  }
}

// ── Moss client singleton ─────────────────────────────────────────────────

let _client: Promise<MossClient> | null = null

function getClient() {
  if (!_client) {
    _client = import('@moss-dev/moss-web')
      .then(({ MossClient }) => MossClient.create(PROJECT_ID, PROJECT_KEY))
      .catch(err => {
        _client = null
        throw err
      })
  }
  return _client
}

// ── App ───────────────────────────────────────────────────────────────────

export default function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<EmojiResult[]>([])
  const [isReady, setIsReady] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [initError, setInitError] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)

  // Load the index into memory on mount
  useEffect(() => {
    getClient()
      .then(c => c.loadIndex(INDEX_NAME))
      .then(() => setIsReady(true))
      .catch(e => setInitError(e instanceof Error ? e.message : 'Failed to load index'))
  }, [])

  const search = useCallback(async () => {
    if (!query.trim() || !isReady || isSearching) return
    setIsSearching(true)
    setSearchError(null)
    setHasSearched(true)
    try {
      const c = await getClient()
      const res = await c.query(INDEX_NAME, query, { topK: 10 })
      setResults(
        res.docs.map(doc => ({
          id: doc.id,
          score: doc.score,
          metadata: doc.metadata as EmojiResult['metadata'],
        }))
      )
    } catch (e) {
      setSearchError(e instanceof Error ? e.message : 'Search failed')
      setResults([])
    } finally {
      setIsSearching(false)
    }
  }, [query, isReady, isSearching])

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={s.root}>
      <StatusBar barStyle="light-content" backgroundColor="#030712" />

      {/* Header */}
      <View style={s.header}>
        <Text style={s.title}>Emoji Search</Text>
        <Text style={s.subtitle}>Semantic search · 5,034 emojis · Moss</Text>
      </View>

      {/* Search bar */}
      <View style={s.searchRow}>
        <TextInput
          style={s.input}
          value={query}
          onChangeText={setQuery}
          placeholder={isReady ? '"celebration", "sad pizza", "love"…' : 'Loading index…'}
          placeholderTextColor="#334155"
          editable={isReady}
          onSubmitEditing={search}
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="none"
        />
        <TouchableOpacity
          style={[s.btn, (!isReady || !query.trim() || isSearching) && s.btnOff]}
          onPress={search}
          disabled={!isReady || !query.trim() || isSearching}
          activeOpacity={0.75}
        >
          <Text style={s.btnText}>{isSearching ? '…' : 'Search'}</Text>
        </TouchableOpacity>
      </View>

      {/* Init error */}
      {initError && (
        <View style={s.errorBox}>
          <Text style={s.errorText}>⚠ {initError}</Text>
        </View>
      )}

      {/* Search error */}
      {searchError && (
        <View style={s.errorBox}>
          <Text style={s.errorText}>⚠ {searchError}</Text>
        </View>
      )}

      {/* Loading index */}
      {!isReady && !initError && (
        <View style={s.center}>
          <ActivityIndicator size="large" color="#3b82f6" />
          <Text style={s.hint}>Loading emoji index…</Text>
        </View>
      )}

      {/* Results */}
      {isReady && (
        <FlatList
          data={isSearching ? [] : results}
          keyExtractor={item => item.id}
          contentContainerStyle={[s.list, results.length === 0 && s.listEmpty]}
          ListHeaderComponent={
            isSearching ? (
              <View style={s.center}>
                <ActivityIndicator color="#3b82f6" />
              </View>
            ) : null
          }
          ListEmptyComponent={
            !isSearching ? (
              <View style={s.center}>
                <Text style={s.emptyEmoji}>{hasSearched ? '🤷' : '✨'}</Text>
                <Text style={s.hint}>
                  {hasSearched
                    ? 'No emojis found — try a broader search'
                    : 'Try "birthday", "spicy food", or "feeling tired"'}
                </Text>
              </View>
            ) : null
          }
          renderItem={({ item }) => <EmojiCard result={item} />}
        />
      )}
    </SafeAreaView>
  )
}

// ── EmojiCard ─────────────────────────────────────────────────────────────

function EmojiCard({ result }: { result: EmojiResult }) {
  const pct = Math.round(result.score * 100)
  const tags = result.metadata.tags.split(', ').slice(0, 4)

  return (
    <View style={s.card}>
      <Text style={s.cardEmoji}>{result.metadata.character}</Text>
      <View style={s.cardBody}>
        <View style={s.cardTop}>
          <Text style={s.cardName} numberOfLines={1}>{result.metadata.name}</Text>
          <View style={[s.scoreBadge, pct >= 75 ? s.scoreHigh : s.scoreMid]}>
            <Text style={s.scoreText}>{pct}%</Text>
          </View>
        </View>
        <Text style={s.cardDesc} numberOfLines={2}>{result.metadata.description}</Text>
        <View style={s.tagRow}>
          {tags.map(tag => (
            <View key={tag} style={s.pill}>
              <Text style={s.pillText}>{tag}</Text>
            </View>
          ))}
        </View>
      </View>
    </View>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#030712',
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 16,
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#f8fafc',
    letterSpacing: -0.4,
  },
  subtitle: {
    fontSize: 12,
    color: '#334155',
    marginTop: 2,
    letterSpacing: 0.2,
  },
  searchRow: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  input: {
    flex: 1,
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 11,
    color: '#f1f5f9',
    fontSize: 15,
  },
  btn: {
    backgroundColor: '#3b82f6',
    borderRadius: 12,
    paddingHorizontal: 18,
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 72,
  },
  btnOff: {
    opacity: 0.35,
  },
  btnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 14,
  },
  list: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 40,
  },
  listEmpty: {
    flexGrow: 1,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 14,
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
  },
  cardEmoji: {
    fontSize: 44,
    lineHeight: 52,
  },
  cardBody: {
    flex: 1,
    paddingTop: 2,
  },
  cardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    marginBottom: 4,
  },
  cardName: {
    flex: 1,
    fontSize: 11,
    fontWeight: '700',
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  scoreBadge: {
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  scoreHigh: {
    backgroundColor: 'rgba(16,185,129,0.15)',
  },
  scoreMid: {
    backgroundColor: 'rgba(245,158,11,0.12)',
  },
  scoreText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#94a3b8',
  },
  cardDesc: {
    fontSize: 13,
    color: '#94a3b8',
    lineHeight: 19,
    marginBottom: 8,
  },
  tagRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
  },
  pill: {
    backgroundColor: '#1e293b',
    borderRadius: 5,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  pillText: {
    fontSize: 10,
    color: '#475569',
    fontWeight: '600',
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyEmoji: {
    fontSize: 52,
    marginBottom: 12,
  },
  hint: {
    fontSize: 13,
    color: '#334155',
    textAlign: 'center',
    paddingHorizontal: 40,
    lineHeight: 19,
    marginTop: 8,
  },
  errorBox: {
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 12,
    backgroundColor: 'rgba(239,68,68,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.2)',
    borderRadius: 10,
  },
  errorText: {
    color: '#f87171',
    fontSize: 13,
  },
})
