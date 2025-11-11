import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { DomainDetector, DomainDetectionResult, DomainType } from './DomainDetector';

export interface DomainModels {
	code?: BaseChatModel;
	math?: BaseChatModel;
	data?: BaseChatModel;
	medical?: BaseChatModel;
	legal?: BaseChatModel;
}

export interface DomainRoutingResult {
	useDomainSpecialist: boolean;
	domainModel?: BaseChatModel;
	domain: DomainType;
	detection: DomainDetectionResult;
	reasoning: string;
}

export class DomainRouter {
	private domainModels: DomainModels;

	constructor(domainModels: DomainModels = {}) {
		this.domainModels = domainModels;
	}

	route(query: string): DomainRoutingResult {
		const detection = DomainDetector.detectDomain(query);

		if (!DomainDetector.shouldUseDomainSpecialist(detection)) {
			return {
				useDomainSpecialist: false,
				domain: detection.domain,
				detection,
				reasoning: `Using general cascade - ${detection.reasoning}`,
			};
		}

		const domainModel = this.getDomainModel(detection.domain);

		if (!domainModel) {
			const recommendation = DomainDetector.getDomainModelRecommendation(detection.domain);
			return {
				useDomainSpecialist: false,
				domain: detection.domain,
				detection,
				reasoning: `${detection.reasoning}. No domain specialist connected (recommended: ${recommendation}). Using general cascade.`,
			};
		}

		return {
			useDomainSpecialist: true,
			domainModel,
			domain: detection.domain,
			detection,
			reasoning: `${detection.reasoning}. Routing to ${detection.domain} specialist model.`,
		};
	}

	private getDomainModel(domain: DomainType): BaseChatModel | undefined {
		const modelMap: Record<DomainType, keyof DomainModels | undefined> = {
			CODE: 'code',
			MATH: 'math',
			DATA: 'data',
			MEDICAL: 'medical',
			LEGAL: 'legal',
			GENERAL: undefined,
		};

		const modelKey = modelMap[domain];
		return modelKey ? this.domainModels[modelKey] : undefined;
	}

	hasDomainModel(domain: DomainType): boolean {
		return this.getDomainModel(domain) !== undefined;
	}

	getAvailableDomains(): DomainType[] {
		const domains: DomainType[] = [];

		if (this.domainModels.code) domains.push('CODE');
		if (this.domainModels.math) domains.push('MATH');
		if (this.domainModels.data) domains.push('DATA');
		if (this.domainModels.medical) domains.push('MEDICAL');
		if (this.domainModels.legal) domains.push('LEGAL');

		return domains;
	}

	hasAnyDomainModels(): boolean {
		return this.getAvailableDomains().length > 0;
	}

	getStatistics() {
		return {
			availableDomains: this.getAvailableDomains(),
			domainModelCount: this.getAvailableDomains().length,
			hasCode: this.hasDomainModel('CODE'),
			hasMath: this.hasDomainModel('MATH'),
			hasData: this.hasDomainModel('DATA'),
			hasMedical: this.hasDomainModel('MEDICAL'),
			hasLegal: this.hasDomainModel('LEGAL'),
		};
	}
}
