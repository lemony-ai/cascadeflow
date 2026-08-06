/** Provider-neutral, versioned knowledge handoff for cross-model routing. */

import type { Provider } from './types';

export type KnowledgeCacheTtl = '5m' | '1h';

export interface KnowledgeSnapshot {
  content: string;
  key?: string;
  version?: string;
  enableProviderCache?: boolean;
  cacheTtl?: KnowledgeCacheTtl;
}

export interface PreparedKnowledge {
  identity: string;
  contentDigest: string;
  systemPrefix: string;
  enableProviderCache: boolean;
  cacheTtl: KnowledgeCacheTtl;
  promptCacheKey: string;
}

function fingerprint(value: string): string {
  // Two seeded FNV-1a passes keep this browser-safe and deterministic. This is
  // an identity fingerprint, not a security primitive.
  const pass = (seed: number): string => {
    let hash = seed >>> 0;
    for (let i = 0; i < value.length; i++) {
      hash ^= value.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, '0');
  };
  return `${pass(0x811c9dc5)}${pass(0x9e3779b9)}`;
}

function safeLabel(value: string): string {
  return value.trim().replace(/[^a-zA-Z0-9._:/-]+/g, '-').replace(/^-+|-+$/g, '') || 'knowledge';
}

export class KnowledgeCache {
  private entries = new Map<string, PreparedKnowledge>();
  private versionDigests = new Map<string, string>();
  private hits = 0;
  private misses = 0;
  private evictions = 0;

  constructor(private readonly maxEntries = 128) {
    if (maxEntries <= 0) throw new Error('maxEntries must be positive');
  }

  prepare(value: string | KnowledgeSnapshot): { prepared: PreparedKnowledge; localCacheHit: boolean } {
    const snapshot: KnowledgeSnapshot = typeof value === 'string' ? { content: value } : value;
    if (!snapshot.content?.trim()) throw new Error('KnowledgeSnapshot.content must be non-empty');
    if (snapshot.cacheTtl && snapshot.cacheTtl !== '5m' && snapshot.cacheTtl !== '1h') {
      throw new Error("KnowledgeSnapshot.cacheTtl must be '5m' or '1h'");
    }

    const key = safeLabel(snapshot.key ?? 'default');
    const contentDigest = fingerprint(snapshot.content);
    const version = safeLabel(snapshot.version ?? contentDigest);
    const identity = `${key}:${version}`;
    const enableProviderCache = snapshot.enableProviderCache ?? true;
    const cacheTtl = snapshot.cacheTtl ?? '5m';
    const entryKey = JSON.stringify([identity, contentDigest, enableProviderCache, cacheTtl]);
    const priorDigest = this.versionDigests.get(identity);
    if (priorDigest && priorDigest !== contentDigest) {
      throw new Error(
        'Knowledge version collision: reuse of a key/version with different content would risk stale context'
      );
    }

    const existing = this.entries.get(entryKey);
    if (existing) {
      this.entries.delete(entryKey);
      this.entries.set(entryKey, existing);
      this.hits++;
      return { prepared: existing, localCacheHit: true };
    }

    const prepared: PreparedKnowledge = {
      identity,
      contentDigest,
      systemPrefix:
        `<cascadeflow_knowledge version="${identity}">\n` +
        `${snapshot.content.trim()}\n</cascadeflow_knowledge>`,
      enableProviderCache,
      cacheTtl,
      promptCacheKey: `cascadeflow:knowledge:${fingerprint(`${identity}:${contentDigest}`)}`,
    };
    this.entries.set(entryKey, prepared);
    this.versionDigests.set(identity, contentDigest);
    this.misses++;

    if (this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next().value as string | undefined;
      if (oldest) {
        const evictedIdentity = this.entries.get(oldest)?.identity;
        this.entries.delete(oldest);
        if (
          evictedIdentity &&
          !Array.from(this.entries.values()).some(entry => entry.identity === evictedIdentity)
        ) {
          this.versionDigests.delete(evictedIdentity);
        }
        this.evictions++;
      }
    }
    return { prepared, localCacheHit: false };
  }

  clear(): void {
    this.entries.clear();
    this.versionDigests.clear();
  }

  getStats(): { size: number; hits: number; misses: number; evictions: number } {
    return { size: this.entries.size, hits: this.hits, misses: this.misses, evictions: this.evictions };
  }
}

export function providerKnowledgeCacheOptions(
  provider: Provider | string,
  prepared?: PreparedKnowledge
): Record<string, unknown> {
  if (!prepared?.enableProviderCache) return {};
  if (provider === 'openai') {
    return {
      prompt_cache_key: prepared.promptCacheKey,
      // Consumed by OpenAIProvider; it must never be forwarded as an API field.
      // GPT-5.6+ uses it to end the cache before the changing query suffix.
      _cascadeflow_knowledge_cache_prefix: prepared.systemPrefix,
    };
  }
  if (provider === 'anthropic') {
    return {
      cache_control: {
        type: 'ephemeral',
        ...(prepared.cacheTtl === '1h' ? { ttl: '1h' } : {}),
      },
    };
  }
  return {};
}
