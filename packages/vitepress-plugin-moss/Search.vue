<script setup lang="ts">
import { ref, shallowRef, computed, nextTick, watch, onBeforeUnmount, onMounted } from 'vue'
import { useData, useRouter } from 'vitepress'
import { onKeyStroke, useScrollLock, useInfiniteScroll } from '@vueuse/core'
import { useFocusTrap } from '@vueuse/integrations/useFocusTrap'
import type { SearchResult, QueryResultDocumentInfo } from '@moss-dev/moss-web'
import SearchButton from './SearchButton.vue'
import mossLogo from './MossLogo_Dark_Icon.png'

// --------- Metadata structure for Search Results ---------
interface MossMetadata {
  title: string
  path: string
  groupId: string
  type: 'page' | 'header' | 'text' | 'code'
  groupTitle: string
  displayBreadcrumb: string
  sanitizedText: string
  navigation?: string
}

// --------- UI View Model for each search hit ---------
interface ResultItemVM {
  id: string
  data: QueryResultDocumentInfo
  flatIndex: number
  htmlSnippet: string
  breadcrumb: string
  breadcrumbHtml: string
  titleHtml?: string
  navigation: string
  type: 'page' | 'header' | 'text' | 'code'
  isSynthesized?: boolean
}

// --------- UI View Model for each group of search hits ---------
interface GroupVM {
  title: string
  path: string
  headerMatch: ResultItemVM | null
  children: ResultItemVM[]
}

// --------- Configuration ---------
const { theme } = useData()
const router = useRouter()
const options = computed(() => theme.value.search?.options || {})

// --------- Open State (self-contained) ---------
const isOpen = ref(false)
const isMounted = ref(false)

// --------- Element refs ---------
const el = ref<HTMLElement>()
const searchInput = ref<HTMLInputElement>()

// --------- Input vs Search State ---------
const inputValue = ref('')
const searchQuery = ref('')

const rawResults = shallowRef<QueryResultDocumentInfo[]>([])
const displayGroups = shallowRef<GroupVM[]>([])
const flatNavigationList = shallowRef<Array<{ path: string }>>([])

const status = ref<'idle' | 'initializing' | 'ready' | 'searching' | 'processing' | 'error'>('idle')
const selectedIndex = ref(0)
const errorMessage = ref('')

// --------- Persistent Client ---------
const mossClient = shallowRef<any>(null)
let initPromise: Promise<void> | null = null
let lastQueryToken = 0

// --------- Performance Profiling ---------
const ENABLE_PROFILING = import.meta.env.VITE_MOSS_LOG_LEVEL === 'info'
let currentProfile: {
  query: string; inputTime: number; searchStartTime: number; searchEndTime: number
  processingStartTime: number; processingEndTime: number; escapeHtmlTime: number
  generateSnippetTime: number; highlightBreadcrumbTime: number; visibleGroupsTime: number; totalTime: number
} | null = null

let escapeHtmlCallCount = 0, escapeHtmlTotalTime = 0
let generateSnippetCallCount = 0, generateSnippetTotalTime = 0
let highlightBreadcrumbCallCount = 0, highlightBreadcrumbTotalTime = 0

function getTime() { return performance?.now?.() ?? Date.now() }

function logProfile() {
  if (!ENABLE_PROFILING || !currentProfile) return
  const p = currentProfile
  console.group(`[Moss Performance] "${p.query}"`)
  console.log(`Total: ${p.totalTime.toFixed(2)}ms`)
  console.log(`  ├─ Search API: ${(p.searchEndTime - p.searchStartTime).toFixed(2)}ms`)
  console.log(`  ├─ Processing: ${(p.processingEndTime - p.processingStartTime).toFixed(2)}ms`)
  console.log(`  │  ├─ escapeHtml: ${p.escapeHtmlTime.toFixed(2)}ms (${escapeHtmlCallCount} calls)`)
  console.log(`  │  ├─ generateSnippet: ${p.generateSnippetTime.toFixed(2)}ms (${generateSnippetCallCount} calls)`)
  console.log(`  │  └─ highlightBreadcrumb: ${p.highlightBreadcrumbTime.toFixed(2)}ms (${highlightBreadcrumbCallCount} calls)`)
  console.log(`  └─ visibleGroups: ${p.visibleGroupsTime.toFixed(2)}ms`)
  console.groupEnd()
  escapeHtmlCallCount = escapeHtmlTotalTime = generateSnippetCallCount = generateSnippetTotalTime = 0
  highlightBreadcrumbCallCount = highlightBreadcrumbTotalTime = 0
  currentProfile = null
}

const isLoading = computed(() => ['initializing', 'searching', 'processing'].includes(status.value))

// --------- Spinner UX smoothing ---------
const isSpinnerVisible = ref(false)
let spinnerShowTimer: ReturnType<typeof setTimeout> | null = null
let spinnerHideTimer: ReturnType<typeof setTimeout> | null = null
let spinnerShownAt: number | null = null

function clearSpinnerTimers() {
  if (spinnerShowTimer) { clearTimeout(spinnerShowTimer); spinnerShowTimer = null }
  if (spinnerHideTimer) { clearTimeout(spinnerHideTimer); spinnerHideTimer = null }
}

watch(isLoading, (loading) => {
  clearSpinnerTimers()
  if (loading) {
    spinnerShowTimer = setTimeout(() => { isSpinnerVisible.value = true; spinnerShownAt = Date.now() }, 120)
  } else {
    const elapsed = spinnerShownAt ? Date.now() - spinnerShownAt : 0
    spinnerHideTimer = setTimeout(() => { isSpinnerVisible.value = false; spinnerShownAt = null }, Math.max(0, 200 - elapsed))
  }
})

// --------- Infinite scroll ---------
const dropdownEl = ref<HTMLElement>()
const renderLimit = ref(15)

const visibleGroups = computed(() => {
  const start = ENABLE_PROFILING ? getTime() : 0
  const limit = renderLimit.value
  const result: GroupVM[] = []
  let count = 0
  for (const group of displayGroups.value) {
    if (count >= limit) break
    const newGroup: GroupVM = { ...group, children: [] }
    if (group.headerMatch) { if (count >= limit) break; count++ }
    const remaining = limit - count
    if (remaining > 0) {
      if (group.children.length <= remaining) { newGroup.children = group.children; count += group.children.length }
      else { newGroup.children = group.children.slice(0, remaining); count += remaining }
    }
    result.push(newGroup)
  }
  if (ENABLE_PROFILING && currentProfile) currentProfile.visibleGroupsTime = getTime() - start
  return result
})

useInfiniteScroll(dropdownEl, () => {
  const total = displayGroups.value.reduce((s, g) => s + (g.headerMatch ? 1 : 0) + g.children.length, 0)
  const visible = visibleGroups.value.reduce((s, g) => s + (g.headerMatch ? 1 : 0) + g.children.length, 0)
  if (visible < total) renderLimit.value += 20
}, { distance: 50 })

watch(inputValue, () => { renderLimit.value = 15 })

const maxMatchPerPage = computed(() => (options.value as any).MaxMatchPerPage ?? 2)

// --------- Helpers ---------
function escapeHtml(str: string) {
  const start = ENABLE_PROFILING ? getTime() : 0
  const result = str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
  if (ENABLE_PROFILING) { escapeHtmlCallCount++; escapeHtmlTotalTime += getTime() - start; if (currentProfile) currentProfile.escapeHtmlTime = escapeHtmlTotalTime }
  return result
}

function getTypeIcon(type: 'page' | 'header' | 'text' | 'code') {
  switch (type) {
    case 'page': return '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>'
    case 'header': return '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="12" x2="20" y2="12"></line><line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="18" x2="20" y2="18"></line></svg>'
    case 'code': return '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>'
    default: return '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"></line><line x1="4" y1="15" x2="20" y2="15"></line><line x1="10" y1="3" x2="8" y2="21"></line><line x1="16" y1="3" x2="14" y2="21"></line></svg>'
  }
}

// --------- Display groups processor ---------
function updateDisplayGroups() {
  const results = rawResults.value
  const q = searchQuery.value.trim()
  if (!q || results.length === 0) {
    displayGroups.value = []; flatNavigationList.value = []; selectedIndex.value = 0; return
  }
  const processingStart = ENABLE_PROFILING ? getTime() : 0
  if (ENABLE_PROFILING && currentProfile) currentProfile.processingStartTime = processingStart
  status.value = 'processing'

  const safeQ = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${safeQ})`, 'gi')

  const generateSnippet = (text: string): string => {
    const t0 = ENABLE_PROFILING ? getTime() : 0
    if (!text) return ''
    if (text.length <= 150) {
      const r = escapeHtml(text).replace(regex, '<span class="Moss-Match">$&</span>')
      if (ENABLE_PROFILING) { generateSnippetCallCount++; generateSnippetTotalTime += getTime() - t0; if (currentProfile) currentProfile.generateSnippetTime = generateSnippetTotalTime }
      return r
    }
    const idx = text.toLowerCase().indexOf(q.toLowerCase())
    let snippet: string
    if (idx === -1) { snippet = escapeHtml(text.slice(0, 100)) + '...' }
    else {
      let s = Math.max(0, idx - 20), e = Math.min(text.length, idx + q.length + 100)
      snippet = (s > 0 ? '...' : '') + text.slice(s, e) + (e < text.length ? '...' : '')
      snippet = escapeHtml(snippet).replace(regex, '<span class="Moss-Match">$&</span>')
    }
    if (ENABLE_PROFILING) { generateSnippetCallCount++; generateSnippetTotalTime += getTime() - t0; if (currentProfile) currentProfile.generateSnippetTime = generateSnippetTotalTime }
    return snippet
  }

  const highlightBreadcrumb = (text: string): string => {
    const t0 = ENABLE_PROFILING ? getTime() : 0
    if (!text) return ''
    const r = escapeHtml(text).replace(regex, '<span class="Moss-Match">$&</span>')
    if (ENABLE_PROFILING) { highlightBreadcrumbCallCount++; highlightBreadcrumbTotalTime += getTime() - t0; if (currentProfile) currentProfile.highlightBreadcrumbTime = highlightBreadcrumbTotalTime }
    return r
  }

  const map = new Map<string, GroupVM>()
  const navLinksPerGroup = new Map<string, Set<string>>()

  results.forEach(item => {
    const meta = item.metadata as unknown as MossMetadata
    const groupId = meta.groupId
    const navigation = meta.navigation || item.id
    if (!navLinksPerGroup.has(groupId)) navLinksPerGroup.set(groupId, new Set())
    const used = navLinksPerGroup.get(groupId)!
    if (used.has(navigation)) return

    let breadcrumb = ''
    if (meta.type !== 'page') {
      breadcrumb = meta.displayBreadcrumb || meta.title || ({ header: 'Heading', code: 'Code Block', text: 'Text' } as any)[meta.type] || 'Section'
    }

    if (!map.has(groupId)) {
      map.set(groupId, { title: meta.groupTitle || 'Documentation', path: groupId, headerMatch: null, children: [] })
    }
    const group = map.get(groupId)!
    if (meta.type !== 'page' && group.children.length >= maxMatchPerPage.value) return

    const vm: ResultItemVM = {
      id: item.id, data: item, flatIndex: 0,
      breadcrumb, breadcrumbHtml: breadcrumb ? highlightBreadcrumb(breadcrumb) : '',
      htmlSnippet: generateSnippet(meta.sanitizedText || item.text || ''),
      titleHtml: highlightBreadcrumb(meta.groupTitle || meta.title || 'Documentation'),
      navigation, type: meta.type || 'text'
    }

    if (meta.type === 'page') { if (!group.headerMatch) { group.headerMatch = vm; used.add(navigation) } }
    else { if (group.children.length < maxMatchPerPage.value) { group.children.push(vm); used.add(navigation) } }
  })

  // Ensure every group has a page-level anchor even if no type=page chunk was returned
  for (const group of map.values()) {
    if (!group.headerMatch && group.children.length > 0) {
      group.headerMatch = {
        id: group.path,
        data: null as any,
        flatIndex: 0,
        htmlSnippet: '',
        breadcrumb: '',
        breadcrumbHtml: '',
        titleHtml: highlightBreadcrumb(group.title),
        navigation: group.path,
        type: 'page',
        isSynthesized: true
      }
    }
  }

  let idx = 0
  const groups = Array.from(map.values())
  const navList: Array<{ path: string }> = []
  groups.forEach(g => {
    if (g.headerMatch) { g.headerMatch.flatIndex = idx++; navList.push({ path: g.headerMatch.navigation }) }
    g.children.forEach(c => { c.flatIndex = idx++; navList.push({ path: c.navigation }) })
  })

  if (ENABLE_PROFILING && currentProfile) currentProfile.processingEndTime = getTime()
  displayGroups.value = groups
  flatNavigationList.value = navList
  if (selectedIndex.value >= navList.length) selectedIndex.value = Math.max(0, navList.length - 1)
  status.value = 'ready'
  if (ENABLE_PROFILING && currentProfile) nextTick(() => { currentProfile!.totalTime = getTime() - currentProfile!.inputTime; logProfile() })
}

// --------- Moss Client ---------
async function initMoss() {
  if (mossClient.value || initPromise) return initPromise
  status.value = 'initializing'
  initPromise = (async () => {
    try {
      const { MossClient } = await import(/* @vite-ignore */ '@moss-dev/moss-web')
      const client = new MossClient((options.value as any).projectId, (options.value as any).projectKey)
      mossClient.value = client
      status.value = 'ready'
      client.loadIndex((options.value as any).indexName).catch(() => {})
    } catch (e) {
      status.value = 'error'
      errorMessage.value = `Failed to initialize search: ${e instanceof Error ? e.message : String(e)}`
      initPromise = null; throw e
    }
  })()
  return initPromise
}

// --------- Search ---------
const performSearch = async (q: string) => {
  const currentQuery = q.trim()
  if (!currentQuery) {
    rawResults.value = []; displayGroups.value = []; flatNavigationList.value = []; selectedIndex.value = 0; status.value = 'ready'; return
  }
  const token = ++lastQueryToken
  try { if (!mossClient.value) await initMoss() } catch { return }
  try {
    status.value = 'searching'
    const searchStart = getTime()
    if (ENABLE_PROFILING && currentProfile) currentProfile.searchStartTime = searchStart
    const topk = (options.value as any).topk ?? 20
    const response = (await mossClient.value.query((options.value as any).indexName, currentQuery, topk)) as SearchResult
    if (token !== lastQueryToken || currentQuery !== searchQuery.value.trim()) return
    if (ENABLE_PROFILING && currentProfile) currentProfile.searchEndTime = getTime()
    rawResults.value = Array.isArray(response?.docs) ? response.docs : []
    updateDisplayGroups()
    selectedIndex.value = 0
  } catch { status.value = 'error'; errorMessage.value = 'Search failed.' }
}

function onInput() {
  const q = inputValue.value
  if (ENABLE_PROFILING) {
    currentProfile = { query: q, inputTime: getTime(), searchStartTime: 0, searchEndTime: 0, processingStartTime: 0, processingEndTime: 0, escapeHtmlTime: 0, generateSnippetTime: 0, highlightBreadcrumbTime: 0, visibleGroupsTime: 0, totalTime: 0 }
  }
  searchQuery.value = q
  performSearch(q)
}

function clearSearch() {
  inputValue.value = ''; searchQuery.value = ''; rawResults.value = []; displayGroups.value = []
  flatNavigationList.value = []; selectedIndex.value = 0; status.value = 'ready'
}

// --------- Navigation ---------
function handleSelect(index: number) {
  if (index < 0 || index >= flatNavigationList.value.length) return
  const item = flatNavigationList.value[index]
  if (item?.path) { try { router.go(item.path); isOpen.value = false } catch (e) { console.error('Navigation failed:', e) } }
}

function scrollToActive() {
  nextTick(() => el.value?.querySelector('.Moss-Item[aria-selected="true"]')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
}

// --------- Focus trap & scroll lock ---------
const { activate, deactivate } = useFocusTrap(el, { immediate: false, escapeDeactivates: false })
const isLocked = useScrollLock(typeof window !== 'undefined' ? document.body : null)

watch(isOpen, (open) => {
  if (open) {
    isLocked.value = true
    nextTick(() => { activate(); searchInput.value?.focus() })
  } else {
    isLocked.value = false
    deactivate()
    clearSearch()
    status.value = 'idle'
  }
})

// --------- Keyboard shortcuts ---------
onKeyStroke('Escape', () => { isOpen.value = false })

onKeyStroke('ArrowUp', (e) => {
  if (!isOpen.value) return
  e.preventDefault()
  selectedIndex.value = Math.max(0, selectedIndex.value - 1)
  scrollToActive()
})

onKeyStroke('ArrowDown', (e) => {
  if (!isOpen.value) return
  e.preventDefault()
  selectedIndex.value = Math.min(Math.max(0, flatNavigationList.value.length - 1), selectedIndex.value + 1)
  scrollToActive()
})

onKeyStroke('Enter', (e) => {
  if (!isOpen.value) return
  e.preventDefault()
  handleSelect(selectedIndex.value)
})

onKeyStroke('k', (e) => {
  if (e.metaKey || e.ctrlKey) { e.preventDefault(); isOpen.value = !isOpen.value }
})

onKeyStroke('/', (e) => {
  const t = e.target as HTMLElement
  if (!t.isContentEditable && !['INPUT', 'SELECT', 'TEXTAREA'].includes(t.tagName)) { e.preventDefault(); isOpen.value = true }
})

onMounted(() => { isMounted.value = true; initMoss().catch(() => {}) })
onBeforeUnmount(() => { isLocked.value = false; deactivate(); clearSpinnerTimers() })
</script>

<template>
  <!-- Nav bar button -->
  <div class="moss-search-wrapper">
    <SearchButton
      :text="(options as any).search?.buttonText || 'Search'"
      :aria-label="(options as any).search?.buttonText || 'Search docs'"
      @click="isOpen = true"
    />
  </div>

  <!-- Search modal -->
  <Teleport to="body">
    <div v-if="isOpen && isMounted" ref="el" class="Moss-Container" role="dialog" aria-modal="true">
      <div class="Moss-Backdrop" @click="isOpen = false" />
      <div class="Moss-Modal">

        <header class="Moss-Header">
          <form class="Moss-Form" @submit.prevent>
            <label class="Moss-MagnifierLabel" for="moss-search-input">
              <svg v-if="isSpinnerVisible" width="20" height="20" class="Moss-Spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="4" stroke-opacity="0.3"></circle><path d="M12 2C6.48 2 2 6.48 2 12" stroke-width="4" stroke-linecap="round"></path></svg>
              <svg v-else width="20" height="20" class="Moss-SearchIcon" viewBox="0 0 20 20"><path d="M14.386 14.386l4.0877 4.0877-4.0877-4.0877c-2.9418 2.9419-7.7115 2.9419-10.6533 0-2.9419-2.9418-2.9419-7.7115 0-10.6533 2.9418-2.9419 7.7115-2.9419 10.6533 0 2.9419 2.9418 2.9419 7.7115 0 10.6533z" stroke="currentColor" fill="none" fill-rule="evenodd" stroke-linecap="round" stroke-linejoin="round"></path></svg>
            </label>
            <input id="moss-search-input" ref="searchInput" v-model="inputValue" @input="onInput" class="Moss-Input" placeholder="Search docs..." autocomplete="off" />
            <div class="Moss-Controls">
              <button v-if="inputValue" class="Moss-Reset" type="button" @click="clearSearch">
                <svg width="18" height="18" viewBox="0 0 20 20"><path d="M10 10l5.09-5.09L10 10l5.09 5.09L10 10zm0 0L4.91 4.91 10 10l-5.09 5.09L10 10z" stroke="currentColor" fill="none" fill-rule="evenodd" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              </button>
              <button v-else class="Moss-Cancel" type="button" @click="isOpen = false">Esc</button>
            </div>
          </form>
        </header>

        <div class="Moss-Dropdown" ref="dropdownEl">
          <div v-if="status === 'error'" class="Moss-State error">{{ errorMessage }}</div>
          <div v-else-if="inputValue.trim() && flatNavigationList.length === 0 && status === 'ready' && inputValue === searchQuery" class="Moss-State">
            No results for "<span class="q-text">{{ inputValue }}</span>"
          </div>

          <div class="Moss-Results" v-if="flatNavigationList.length > 0">
            <div v-for="group in visibleGroups" :key="group.path" class="Moss-Group">

              <div
                v-if="group.headerMatch"
                class="Moss-Item Moss-PageHeader"
                :class="{ 'Moss-PageHeader--synthesized': group.headerMatch.isSynthesized }"
                :aria-selected="selectedIndex === group.headerMatch.flatIndex"
                @click="handleSelect(group.headerMatch.flatIndex)"
                @mouseenter="selectedIndex = group.headerMatch.flatIndex"
              >
                <div class="Moss-IconContainer">
                  <span v-html="getTypeIcon('page')"></span>
                </div>
                <div class="Moss-Content">
                  <div class="Moss-Title" v-html="group.headerMatch?.titleHtml || group.title"></div>
                </div>
                <div class="Moss-PageMeta">
                  <span v-if="!group.headerMatch.isSynthesized" class="Moss-PageBadge">Page</span>
                  <span v-if="group.children.length > 0" class="Moss-ChildCount">{{ group.children.length }} result{{ group.children.length > 1 ? 's' : '' }}</span>
                </div>
              </div>

              <div v-if="group.children.length > 0" class="Moss-Children" :class="{ 'Moss-Children--connected': group.headerMatch }">
                <div
                  v-for="child in group.children"
                  :key="child.id"
                  class="Moss-Item Moss-ChildItem"
                  :class="`Moss-Item--${child.type}`"
                  :aria-selected="selectedIndex === child.flatIndex"
                  @click="handleSelect(child.flatIndex)"
                  @mouseenter="selectedIndex = child.flatIndex"
                >
                  <div class="Moss-IconContainer mini">
                    <span v-html="getTypeIcon(child.type || 'text')"></span>
                  </div>
                  <div class="Moss-Content">
                    <div v-if="child.breadcrumb" class="Moss-Breadcrumb" v-html="child.breadcrumbHtml || child.breadcrumb"></div>
                    <div class="Moss-Text" v-html="child.htmlSnippet"></div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

        <footer class="Moss-Footer">
          <ul class="Moss-Commands">
            <li><kbd class="Moss-Key">↵</kbd><span class="Moss-Label">select</span></li>
            <li><kbd class="Moss-Key">↓</kbd><kbd class="Moss-Key">↑</kbd><span class="Moss-Label">navigate</span></li>
            <li><kbd class="Moss-Key">esc</kbd><span class="Moss-Label">close</span></li>
          </ul>
          <div class="Moss-Logo">
            <span>Search by</span>
            <div class="MossBrand-Container">
              <img :src="mossLogo" class="MossBrand-Logo" alt="Moss" width="16" height="16" />
              <span class="MossBrand-Text">Moss</span>
            </div>
          </div>
        </footer>

      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* --- Search wrapper (nav bar) --- */
.moss-search-wrapper { display: flex; align-items: center; }
@media (min-width: 768px) { .moss-search-wrapper { flex-grow: 1; padding-left: 24px; } }
@media (min-width: 960px) { .moss-search-wrapper { padding-left: 32px; } }

/* --- Design Tokens: Light Mode --- */
.Moss-Container {
  --moss-modal-bg: #fff;
  --moss-modal-width: 680px;
  --moss-surface: #fafaf8;
  --moss-accent: #1a1a1a;
  --moss-accent-light: #333;
  --moss-title: #0a0a0a;
  --moss-text: #555;
  --moss-muted: #888;
  --moss-border: #e5e5e0;
  --moss-border-light: #d0d0c8;
  --moss-key-bg: #f5f5f2;
  --moss-key-border: #e0e0db;
  --moss-danger: #b52828;
}

/* --- Design Tokens: Dark Mode --- */
:global(.dark) .Moss-Container {
  --moss-modal-bg: #141412;
  --moss-surface: #1a1a18;
  --moss-accent: #f0f0ee;
  --moss-accent-light: #e0e0dc;
  --moss-title: #f0f0ee;
  --moss-text: #888;
  --moss-muted: #555;
  --moss-border: #222220;
  --moss-border-light: #2a2a28;
  --moss-key-bg: #1e1e1c;
  --moss-key-border: #2a2a28;
  --moss-danger: #f87171;
}

/* --- Layout --- */
.Moss-Container {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: flex-start;
  padding-top: 8vh;
  justify-content: center;
  font-family: 'Geist', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  letter-spacing: -0.011em;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.Moss-Backdrop {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  animation: moss-fade-in 0.15s ease-out;
}

.Moss-Modal {
  position: relative;
  width: calc(100% - 32px);
  max-width: var(--moss-modal-width);
  background: var(--moss-modal-bg);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  max-height: 72vh;
  overflow: hidden;
  border: 1px solid var(--moss-border);
  overscroll-behavior: contain;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.03),
    0 2px 4px rgba(0, 0, 0, 0.04),
    0 12px 32px rgba(0, 0, 0, 0.08),
    0 32px 64px -12px rgba(0, 0, 0, 0.14);
  animation: moss-modal-in 0.2s cubic-bezier(0.32, 0.72, 0, 1);
}

@keyframes moss-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes moss-modal-in {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* --- Header / Search Input --- */
.Moss-Header {
  padding: 4px 4px 0;
}

.Moss-Form {
  display: flex;
  align-items: center;
  padding: 0 16px;
  height: 56px;
  border-bottom: 1px solid var(--moss-border);
}

.Moss-MagnifierLabel {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.Moss-Input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--moss-title);
  font-size: 16px;
  font-family: inherit;
  font-weight: 400;
  margin-left: 14px;
  height: 100%;
  letter-spacing: -0.011em;
}

.Moss-Input::placeholder {
  color: var(--moss-muted);
}

.Moss-SearchIcon,
.Moss-Spinner {
  color: var(--moss-muted);
  flex-shrink: 0;
}

.Moss-Spinner {
  animation: moss-spin 0.8s linear infinite;
}

@keyframes moss-spin {
  to { transform: rotate(360deg); }
}

.Moss-Controls {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.Moss-Cancel {
  background: var(--moss-key-bg);
  border: 1px solid var(--moss-key-border);
  border-radius: 6px;
  padding: 3px 8px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  color: var(--moss-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.Moss-Cancel:hover {
  color: var(--moss-title);
  border-color: var(--moss-border-light);
}

.Moss-Reset {
  background: transparent;
  border: none;
  color: var(--moss-muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.Moss-Reset:hover {
  color: var(--moss-title);
  background: var(--moss-surface);
}

/* --- Results Area --- */
.Moss-Dropdown {
  flex: 1;
  overflow-y: auto;
  padding: 8px 8px 12px;
  scroll-behavior: smooth;
  overscroll-behavior: contain;
  will-change: scroll-position;
}

.Moss-State {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  color: var(--moss-muted);
  font-size: 13.5px;
  gap: 4px;
}

.Moss-State.error {
  color: var(--moss-danger);
}

.q-text {
  font-style: italic;
  color: var(--moss-text);
}

/* --- Result Groups --- */
.Moss-Group {
  margin-bottom: 6px;
  background: var(--moss-surface);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--moss-border);
  content-visibility: auto;
  contain-intrinsic-size: 50px;
}

.Moss-Item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.12s ease, border-color 0.12s ease;
  border-left: 3px solid transparent;
}

.Moss-Item:hover {
  background: color-mix(in srgb, var(--moss-accent) 5%, var(--moss-surface));
}

.Moss-Item[aria-selected="true"] {
  background: var(--moss-accent);
  border-left-color: var(--moss-accent);
}

.Moss-Item[aria-selected="true"] * {
  color: #fff !important;
}

/* --- Page Header Items --- */
.Moss-PageHeader {
  background: transparent;
  border-bottom: none;
}

.Moss-PageHeader .Moss-Title {
  font-weight: 600;
  font-size: 13.5px;
  color: var(--moss-title);
  letter-spacing: -0.01em;
}

.Moss-PageHeader .Moss-IconContainer {
  color: var(--moss-title);
}

.Moss-PageHeader--synthesized {
  opacity: 0.72;
}

.Moss-PageHeader--synthesized .Moss-Title {
  font-weight: 500;
}

.Moss-PageMeta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  flex-shrink: 0;
}

.Moss-PageBadge {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--moss-accent);
  background: color-mix(in srgb, var(--moss-accent) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--moss-accent) 25%, transparent);
  border-radius: 5px;
  padding: 2px 6px;
  line-height: 1.4;
}

.Moss-ChildCount {
  font-size: 11px;
  color: var(--moss-muted);
  white-space: nowrap;
}

.Moss-Item[aria-selected="true"] .Moss-PageMeta * {
  color: rgba(255, 255, 255, 0.85) !important;
  background: rgba(255, 255, 255, 0.15) !important;
  border-color: rgba(255, 255, 255, 0.25) !important;
}

/* --- Child Items & Tree --- */
.Moss-Children {
  padding: 0;
  background: transparent;
}

.Moss-Children--connected {
  border-left: 1.5px solid var(--moss-border);
  margin-left: 22px;
  border-radius: 0 0 0 6px;
  padding-bottom: 4px;
}

.Moss-ChildItem {
  position: relative;
  padding-top: 5px;
  padding-bottom: 5px;
}

.Moss-Children--connected .Moss-ChildItem {
  padding-left: 28px;
}

.Moss-Children--connected .Moss-ChildItem::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 20px;
  height: 1.5px;
  background: var(--moss-border);
  transform: translateY(-50%);
}

.Moss-Children--connected .Moss-ChildItem:last-child::after {
  content: '';
  position: absolute;
  left: -1.5px;
  top: 50%;
  bottom: 0;
  width: 1.5px;
  background: var(--moss-surface);
}

/* --- Icon Colors by Type --- */
.Moss-Item--header .Moss-IconContainer { color: var(--moss-accent); }
.Moss-Item--code .Moss-IconContainer { color: #888; }
.Moss-Item--text .Moss-IconContainer { color: var(--moss-muted); }
.Moss-Item--page .Moss-IconContainer { color: var(--moss-title); }
.Moss-Item[aria-selected="true"] .Moss-IconContainer { color: #fff !important; }

:global(.dark) .Moss-Item--code .Moss-IconContainer { color: #999; }

.Moss-IconContainer {
  width: 24px;
  margin-right: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
}

.Moss-IconContainer.mini {
  width: 22px;
  margin-right: 10px;
  opacity: 0.55;
}

.Moss-Content {
  min-width: 0;
  flex: 1;
}

.Moss-Breadcrumb {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 2px;
  color: var(--moss-title);
  letter-spacing: -0.01em;
}

.Moss-Text {
  font-size: 12.5px;
  color: var(--moss-text);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-top: 1px;
}

/* --- Match Highlighting --- */
:deep(.Moss-Match) {
  color: var(--moss-accent);
  font-weight: 700;
  background: none;
  padding: 0;
  text-decoration: underline;
  text-decoration-color: var(--moss-accent);
  text-decoration-thickness: 1.5px;
  text-underline-offset: 2px;
}

.Moss-Item[aria-selected="true"] :deep(.Moss-Match) {
  color: #fff;
  text-decoration-color: rgba(255, 255, 255, 0.7);
}

/* --- Footer --- */
.Moss-Footer {
  padding: 0 16px;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--moss-border);
  background: var(--moss-modal-bg);
  color: var(--moss-muted);
  font-size: 12px;
}

.Moss-Commands {
  display: flex;
  gap: 14px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.Moss-Commands li {
  display: flex;
  align-items: center;
}

.Moss-Key {
  background: var(--moss-key-bg);
  border: 1px solid var(--moss-key-border);
  border-radius: 5px;
  padding: 2px 6px;
  font-family: inherit;
  font-size: 11px;
  font-weight: 500;
  min-width: 20px;
  text-align: center;
  margin-right: 5px;
  color: var(--moss-muted);
  line-height: 1.4;
}

.Moss-Label {
  color: var(--moss-muted);
}

.Moss-Logo {
  display: flex;
  align-items: center;
  gap: 2px;
  color: var(--moss-muted);
  font-size: 12px;
}

.MossBrand-Container {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-left: 5px;
}

.MossBrand-Logo {
  color: var(--moss-title);
  flex-shrink: 0;
}

.MossBrand-Text {
  font-weight: 700;
  font-size: 13px;
  color: var(--moss-title);
  letter-spacing: -0.02em;
}
</style>
