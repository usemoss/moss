<script setup lang="ts">
import { ref, onMounted } from 'vue';

defineProps<{
  text?: string;
}>();

const isMac = ref(false);

onMounted(() => {
  isMac.value =
    typeof navigator !== 'undefined' &&
    /Mac|iPod|iPhone|iPad/.test(navigator.platform);
});
</script>

<template>
  <button
    type="button"
    class="moss-search-btn"
    aria-keyshortcuts="/ control+k meta+k"
    :aria-label="text || 'Search'"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
    <span class="moss-search-btn-text">{{ text || 'Search' }}</span>
    <span class="moss-search-btn-keys">
      <kbd>{{ isMac ? '⌘' : 'Ctrl' }}</kbd><kbd>K</kbd>
    </span>
  </button>
</template>

<style scoped>
.moss-search-btn {
  --moss-bg: #fafaf8;
  --moss-surface: #fff;
  --moss-muted: #888;
  --moss-accent: #0a0a0a;
  --moss-border: #e5e5e0;
  --moss-title: #0a0a0a;

  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 14px;
  background: var(--moss-bg);
  border: 1px solid var(--moss-border);
  border-radius: 10px;
  cursor: pointer;
  color: var(--moss-muted);
  font-family: 'Geist', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 13.5px;
  font-weight: 400;
  letter-spacing: -0.01em;
  transition: all 0.2s ease;
  white-space: nowrap;
  min-width: 200px;
}

:global(.dark) .moss-search-btn {
  --moss-bg: #0a0a0a;
  --moss-surface: #151515;
  --moss-muted: #666;
  --moss-accent: #f0f0ee;
  --moss-border: #252523;
  --moss-title: #f0f0ee;
}

.moss-search-btn:hover {
  border-color: var(--moss-accent);
  color: var(--moss-title);
  background: color-mix(in srgb, var(--moss-accent) 4%, var(--moss-bg));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--moss-accent) 8%, transparent);
}

.moss-search-btn-text {
  flex: 1;
  text-align: left;
}

@media (max-width: 767px) {
  .moss-search-btn {
    min-width: auto;
    padding: 7px 10px;
  }
  .moss-search-btn-text,
  .moss-search-btn-keys {
    display: none;
  }
}

.moss-search-btn-keys {
  display: flex;
  gap: 3px;
}

.moss-search-btn-keys kbd {
  font-family: inherit;
  font-size: 10.5px;
  font-weight: 500;
  padding: 1px 6px;
  background: var(--moss-surface);
  border: 1px solid var(--moss-border);
  border-radius: 5px;
  color: var(--moss-muted);
  line-height: 1.5;
}
</style>
