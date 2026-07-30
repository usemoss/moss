import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

import { IndexOptions, resolveIndexOptions } from './types.js'

export function discoverFiles(root: string, options: IndexOptions = {}): string[] {
  const opts = resolveIndexOptions(options)
  const resolvedRoot = path.resolve(root)
  if (!fs.existsSync(resolvedRoot) || !fs.statSync(resolvedRoot).isDirectory()) {
    throw new Error(`Repository root is not a directory: ${resolvedRoot}`)
  }

  const candidates = listCandidates(resolvedRoot, opts)
  return candidates
    .filter((filePath) => matchesInclude(filePath, resolvedRoot, opts.includeGlobs))
    .filter((filePath) => withinSizeLimit(filePath, opts.maxFileBytes))
    .sort()
}

function listCandidates(root: string, options: ReturnType<typeof resolveIndexOptions>): string[] {
  if (options.respectGitignore && isGitRepo(root)) {
    const tracked = gitTrackedFiles(root)
    if (tracked) {
      return tracked
    }
  }
  return walkFilesystem(root, new Set(options.excludeDirs))
}

function isGitRepo(root: string): boolean {
  return fs.existsSync(path.join(root, '.git'))
}

function gitTrackedFiles(root: string): string[] | null {
  const version = spawnSync('git', ['--version'], { encoding: 'utf8' })
  if (version.status !== 0) {
    return null
  }
  const result = spawnSync('git', ['-C', root, 'ls-files', '-z'], { encoding: 'buffer' })
  if (result.status !== 0 || !result.stdout) {
    return null
  }
  const relPaths = result.stdout.toString('utf8').split('\0').filter(Boolean)
  return relPaths
    .map((rel) => path.join(root, rel))
    .filter((filePath) => fs.existsSync(filePath) && fs.statSync(filePath).isFile())
}

function walkFilesystem(root: string, excludeDirs: Set<string>): string[] {
  const files: string[] = []
  const stack = [root]
  while (stack.length > 0) {
    const current = stack.pop()!
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name)
      if (entry.isDirectory()) {
        if (!excludeDirs.has(entry.name)) {
          stack.push(full)
        }
        continue
      }
      if (entry.isFile()) {
        files.push(full)
      }
    }
  }
  return files
}

function matchesInclude(filePath: string, root: string, includeGlobs: string[]): boolean {
  const rel = toPosix(path.relative(root, filePath))
  const name = path.basename(filePath)
  for (const pattern of includeGlobs) {
    if (globMatch(rel, pattern) || globMatch(name, pattern)) {
      return true
    }
    if (pattern.startsWith('**/') && globMatch(name, pattern.slice(3))) {
      return true
    }
  }
  return false
}

function withinSizeLimit(filePath: string, maxFileBytes: number): boolean {
  try {
    return fs.statSync(filePath).size <= maxFileBytes
  } catch {
    return false
  }
}

function toPosix(value: string): string {
  return value.split(path.sep).join('/')
}

/** Minimal glob matcher for include patterns (star and double-star globs). */
function globMatch(value: string, pattern: string): boolean {
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*/g, '{{GS}}')
    .replace(/\*/g, '[^/]*')
    .replace(/{{GS}}/g, '.*')
  return new RegExp(`^${escaped}$`).test(value)
}
