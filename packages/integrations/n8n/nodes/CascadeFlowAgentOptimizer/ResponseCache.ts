import { createHash } from 'crypto';
import { CascadeMetadata } from './types';

export interface CachedResponse {
	query: string;
	response: string;
	metadata: CascadeMetadata;
	timestamp: number;
	hits: number;
	hash: string;
}

export interface CacheStats {
	totalEntries: number;
	totalHits: number;
	totalMisses: number;
	hitRate: number;
	costSaved: number;
	oldestEntry: number;
	newestEntry: number;
}

export interface CacheConfig {
	enabled: boolean;
	maxEntries: number;
	ttlMs: number;
	similarityThreshold: number;
}

export class ResponseCache {
	private cache: Map<string, CachedResponse> = new Map();
	private config: CacheConfig;
	private hits: number = 0;
	private misses: number = 0;
	private costSaved: number = 0;

	constructor(config: CacheConfig) {
		this.config = config;
	}

	get(query: string): CachedResponse | null {
		if (!this.config.enabled) {
			return null;
		}

		const hash = this.hashQuery(query);
		const cached = this.cache.get(hash);

		if (!cached) {
			this.misses++;
			return null;
		}

		const age = Date.now() - cached.timestamp;
		if (age > this.config.ttlMs) {
			this.cache.delete(hash);
			this.misses++;
			return null;
		}

		cached.hits++;
		this.hits++;
		this.costSaved += cached.metadata.cost.totalCost;

		return cached;
	}

	set(query: string, response: string, metadata: CascadeMetadata): void {
		if (!this.config.enabled) {
			return;
		}

		const hash = this.hashQuery(query);

		const cached: CachedResponse = {
			query,
			response,
			metadata,
			timestamp: Date.now(),
			hits: 0,
			hash,
		};

		if (this.cache.size >= this.config.maxEntries) {
			this.evictOldest();
		}

		this.cache.set(hash, cached);
	}

	findSimilar(query: string): CachedResponse | null {
		if (!this.config.enabled) {
			return null;
		}

		const normalizedQuery = this.normalizeQuery(query);
		let bestMatch: CachedResponse | null = null;
		let bestSimilarity = 0;

		for (const cached of this.cache.values()) {
			const age = Date.now() - cached.timestamp;
			if (age > this.config.ttlMs) {
				continue;
			}

			const similarity = this.calculateSimilarity(
				normalizedQuery,
				this.normalizeQuery(cached.query)
			);

			if (similarity > bestSimilarity && similarity >= this.config.similarityThreshold) {
				bestSimilarity = similarity;
				bestMatch = cached;
			}
		}

		if (bestMatch) {
			bestMatch.hits++;
			this.hits++;
			this.costSaved += bestMatch.metadata.cost.totalCost;
		} else {
			this.misses++;
		}

		return bestMatch;
	}

	clear(): void {
		this.cache.clear();
		this.hits = 0;
		this.misses = 0;
		this.costSaved = 0;
	}

	getStats(): CacheStats {
		const entries = Array.from(this.cache.values());
		const totalRequests = this.hits + this.misses;
		const hitRate = totalRequests > 0 ? this.hits / totalRequests : 0;

		const timestamps = entries.map(e => e.timestamp);
		const oldestEntry = timestamps.length > 0 ? Math.min(...timestamps) : 0;
		const newestEntry = timestamps.length > 0 ? Math.max(...timestamps) : 0;

		return {
			totalEntries: this.cache.size,
			totalHits: this.hits,
			totalMisses: this.misses,
			hitRate,
			costSaved: this.costSaved,
			oldestEntry,
			newestEntry,
		};
	}

	getMostHit(count: number = 10): CachedResponse[] {
		return Array.from(this.cache.values())
			.sort((a, b) => b.hits - a.hits)
			.slice(0, count);
	}

	cleanupExpired(): number {
		const now = Date.now();
		let removed = 0;

		for (const [hash, cached] of this.cache.entries()) {
			const age = now - cached.timestamp;
			if (age > this.config.ttlMs) {
				this.cache.delete(hash);
				removed++;
			}
		}

		return removed;
	}

	private hashQuery(query: string): string {
		const normalized = this.normalizeQuery(query);
		return createHash('sha256').update(normalized).digest('hex');
	}

	private normalizeQuery(query: string): string {
		return query
			.toLowerCase()
			.trim()
			.replace(/\s+/g, ' ')
			.replace(/[^\w\s]/g, '');
	}

	private calculateSimilarity(str1: string, str2: string): number {
		if (str1 === str2) return 1.0;

		const longer = str1.length > str2.length ? str1 : str2;
		const shorter = str1.length > str2.length ? str2 : str1;

		if (longer.length === 0) return 1.0;

		const editDistance = this.levenshteinDistance(longer, shorter);
		return (longer.length - editDistance) / longer.length;
	}

	private levenshteinDistance(str1: string, str2: string): number {
		const matrix: number[][] = [];

		for (let i = 0; i <= str2.length; i++) {
			matrix[i] = [i];
		}

		for (let j = 0; j <= str1.length; j++) {
			matrix[0][j] = j;
		}

		for (let i = 1; i <= str2.length; i++) {
			for (let j = 1; j <= str1.length; j++) {
				if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
					matrix[i][j] = matrix[i - 1][j - 1];
				} else {
					matrix[i][j] = Math.min(
						matrix[i - 1][j - 1] + 1,
						matrix[i][j - 1] + 1,
						matrix[i - 1][j] + 1
					);
				}
			}
		}

		return matrix[str2.length][str1.length];
	}

	private evictOldest(): void {
		let oldestHash: string | null = null;
		let oldestTime = Date.now();

		for (const [hash, cached] of this.cache.entries()) {
			if (cached.timestamp < oldestTime) {
				oldestTime = cached.timestamp;
				oldestHash = hash;
			}
		}

		if (oldestHash) {
			this.cache.delete(oldestHash);
		}
	}
}
