import { CostMetrics, QualityMetrics, PerformanceMetrics } from './types';

export interface RequestRecord {
	timestamp: number;
	flow: string;
	cost: number;
	quality: number;
	latencyMs: number;
	tokensUsed: number;
	domain?: string;
	complexityLevel?: string;
}

export interface SessionStats {
	totalRequests: number;
	totalCost: number;
	totalSavings: number;
	averageQuality: number;
	averageLatency: number;
	acceptanceRate: number;
	flowDistribution: Record<string, number>;
	domainDistribution: Record<string, number>;
	complexityDistribution: Record<string, number>;
	timeRange: {
		start: number;
		end: number;
		durationMs: number;
	};
}

export interface TrendAnalysis {
	costTrend: 'increasing' | 'decreasing' | 'stable';
	qualityTrend: 'improving' | 'declining' | 'stable';
	acceptanceRateTrend: 'increasing' | 'decreasing' | 'stable';
	recommendations: string[];
}

export class SessionAnalytics {
	private requests: RequestRecord[] = [];
	private startTime: number = Date.now();

	addRequest(
		flow: string,
		cost: CostMetrics,
		quality: QualityMetrics,
		performance: PerformanceMetrics,
		domain?: string,
		complexityLevel?: string
	): void {
		this.requests.push({
			timestamp: Date.now(),
			flow,
			cost: cost.totalCost,
			quality: quality.qualityScore,
			latencyMs: performance.latencyMs,
			tokensUsed: cost.tokensUsed.total,
			domain,
			complexityLevel,
		});
	}

	getStats(): SessionStats {
		if (this.requests.length === 0) {
			return this.getEmptyStats();
		}

		const totalCost = this.requests.reduce((sum, r) => sum + r.cost, 0);
		const totalSavings = this.requests.reduce((sum, r) => {
			return sum + (r.flow === 'drafter_accepted' || r.flow === 'domain_specialist' ? r.cost * 0.5 : 0);
		}, 0);

		const averageQuality = this.requests.reduce((sum, r) => sum + r.quality, 0) / this.requests.length;
		const averageLatency = this.requests.reduce((sum, r) => sum + r.latencyMs, 0) / this.requests.length;

		const drafterAccepted = this.requests.filter(r =>
			r.flow === 'drafter_accepted' || r.flow === 'domain_specialist'
		).length;
		const acceptanceRate = drafterAccepted / this.requests.length;

		const flowDistribution: Record<string, number> = {};
		this.requests.forEach(r => {
			flowDistribution[r.flow] = (flowDistribution[r.flow] || 0) + 1;
		});

		const domainDistribution: Record<string, number> = {};
		this.requests.forEach(r => {
			if (r.domain) {
				domainDistribution[r.domain] = (domainDistribution[r.domain] || 0) + 1;
			}
		});

		const complexityDistribution: Record<string, number> = {};
		this.requests.forEach(r => {
			if (r.complexityLevel) {
				complexityDistribution[r.complexityLevel] = (complexityDistribution[r.complexityLevel] || 0) + 1;
			}
		});

		const timestamps = this.requests.map(r => r.timestamp);
		const start = Math.min(...timestamps);
		const end = Math.max(...timestamps);

		return {
			totalRequests: this.requests.length,
			totalCost,
			totalSavings,
			averageQuality,
			averageLatency,
			acceptanceRate,
			flowDistribution,
			domainDistribution,
			complexityDistribution,
			timeRange: {
				start,
				end,
				durationMs: end - start,
			},
		};
	}

	analyzeTrends(windowSize: number = 10): TrendAnalysis {
		if (this.requests.length < windowSize * 2) {
			return {
				costTrend: 'stable',
				qualityTrend: 'stable',
				acceptanceRateTrend: 'stable',
				recommendations: ['Need more data to analyze trends'],
			};
		}

		const recent = this.requests.slice(-windowSize);
		const previous = this.requests.slice(-windowSize * 2, -windowSize);

		const recentAvgCost = recent.reduce((sum, r) => sum + r.cost, 0) / recent.length;
		const previousAvgCost = previous.reduce((sum, r) => sum + r.cost, 0) / previous.length;
		const costChange = ((recentAvgCost - previousAvgCost) / previousAvgCost) * 100;

		const recentAvgQuality = recent.reduce((sum, r) => sum + r.quality, 0) / recent.length;
		const previousAvgQuality = previous.reduce((sum, r) => sum + r.quality, 0) / previous.length;
		const qualityChange = ((recentAvgQuality - previousAvgQuality) / previousAvgQuality) * 100;

		const recentAcceptance = recent.filter(r =>
			r.flow === 'drafter_accepted' || r.flow === 'domain_specialist'
		).length / recent.length;
		const previousAcceptance = previous.filter(r =>
			r.flow === 'drafter_accepted' || r.flow === 'domain_specialist'
		).length / previous.length;
		const acceptanceChange = ((recentAcceptance - previousAcceptance) / (previousAcceptance || 0.01)) * 100;

		const costTrend = costChange > 10 ? 'increasing' : costChange < -10 ? 'decreasing' : 'stable';
		const qualityTrend = qualityChange > 5 ? 'improving' : qualityChange < -5 ? 'declining' : 'stable';
		const acceptanceRateTrend = acceptanceChange > 10 ? 'increasing' : acceptanceChange < -10 ? 'decreasing' : 'stable';

		const recommendations: string[] = [];

		if (costTrend === 'increasing' && acceptanceRateTrend === 'decreasing') {
			recommendations.push('Consider lowering quality threshold to improve acceptance rate and reduce costs');
		}

		if (qualityTrend === 'declining') {
			recommendations.push('Quality is declining - consider raising quality threshold or using stronger models');
		}

		if (acceptanceRateTrend === 'decreasing') {
			recommendations.push('Drafter acceptance rate is decreasing - may need model tuning or threshold adjustment');
		}

		if (costTrend === 'stable' && acceptanceRateTrend === 'increasing') {
			recommendations.push('System is optimizing well - current configuration is effective');
		}

		const stats = this.getStats();
		if (stats.acceptanceRate < 0.3) {
			recommendations.push('Low acceptance rate (<30%) - consider using a stronger drafter model');
		}

		if (stats.acceptanceRate > 0.8) {
			recommendations.push('High acceptance rate (>80%) - you may be able to use a cheaper drafter model');
		}

		return {
			costTrend,
			qualityTrend,
			acceptanceRateTrend,
			recommendations,
		};
	}

	getRecentPerformance(count: number = 10): RequestRecord[] {
		return this.requests.slice(-count);
	}

	reset(): void {
		this.requests = [];
		this.startTime = Date.now();
	}

	exportData(): RequestRecord[] {
		return [...this.requests];
	}

	private getEmptyStats(): SessionStats {
		return {
			totalRequests: 0,
			totalCost: 0,
			totalSavings: 0,
			averageQuality: 0,
			averageLatency: 0,
			acceptanceRate: 0,
			flowDistribution: {},
			domainDistribution: {},
			complexityDistribution: {},
			timeRange: {
				start: this.startTime,
				end: this.startTime,
				durationMs: 0,
			},
		};
	}
}
