export const DOMAINS = {
  CODE: 'code',
  DATA: 'data',
  STRUCTURED: 'structured',
  RAG: 'rag',
  CONVERSATION: 'conversation',
  TOOL: 'tool',
  CREATIVE: 'creative',
  SUMMARY: 'summary',
  TRANSLATION: 'translation',
  MATH: 'math',
  SCIENCE: 'science',
  MEDICAL: 'medical',
  LEGAL: 'legal',
  FINANCIAL: 'financial',
  MULTIMODAL: 'multimodal',
  GENERAL: 'general',
} as const;

export type DomainType = typeof DOMAINS[keyof typeof DOMAINS];

export const DOMAIN_DISPLAY_NAMES: Record<DomainType, string> = {
  code: 'Code',
  data: 'Data Analysis',
  structured: 'Structured Output',
  rag: 'RAG (Retrieval)',
  conversation: 'Conversation',
  tool: 'Tool Calling',
  creative: 'Creative Writing',
  summary: 'Summarization',
  translation: 'Translation',
  math: 'Mathematics',
  science: 'Science',
  medical: 'Medical',
  legal: 'Legal',
  financial: 'Financial',
  multimodal: 'Multimodal',
  general: 'General',
};

export const DOMAIN_DESCRIPTIONS: Record<DomainType, string> = {
  code: 'Programming, debugging, code generation',
  data: 'Data analysis, statistics, pandas/SQL',
  structured: 'JSON, XML, structured data extraction',
  rag: 'Retrieval-augmented generation, document Q&A',
  conversation: 'Chat, dialogue, multi-turn conversations',
  tool: 'Function calling, tool use, API interactions',
  creative: 'Creative writing, stories, poetry',
  summary: 'Text summarization, condensing content',
  translation: 'Language translation, multilingual',
  math: 'Mathematical reasoning, calculations, proofs',
  science: 'Scientific knowledge, research, experiments',
  medical: 'Healthcare, medical knowledge, clinical',
  legal: 'Legal documents, contracts, regulations',
  financial: 'Finance, accounting, investment analysis',
  multimodal: 'Images, audio, video understanding',
  general: 'General purpose, fallback domain',
};

export const DOMAIN_UI_CONFIGS: Array<{
  domain: DomainType;
  toggleName: string;
}> = [
  { domain: 'code', toggleName: 'enableCodeDomain' },
  { domain: 'data', toggleName: 'enableDataDomain' },
  { domain: 'structured', toggleName: 'enableStructuredDomain' },
  { domain: 'rag', toggleName: 'enableRagDomain' },
  { domain: 'conversation', toggleName: 'enableConversationDomain' },
  { domain: 'tool', toggleName: 'enableToolDomain' },
  { domain: 'creative', toggleName: 'enableCreativeDomain' },
  { domain: 'summary', toggleName: 'enableSummaryDomain' },
  { domain: 'translation', toggleName: 'enableTranslationDomain' },
  { domain: 'math', toggleName: 'enableMathDomain' },
  { domain: 'science', toggleName: 'enableScienceDomain' },
  { domain: 'medical', toggleName: 'enableMedicalDomain' },
  { domain: 'legal', toggleName: 'enableLegalDomain' },
  { domain: 'financial', toggleName: 'enableFinancialDomain' },
  { domain: 'multimodal', toggleName: 'enableMultimodalDomain' },
  { domain: 'general', toggleName: 'enableGeneralDomain' },
];

export const DEFAULT_COMPLEXITY_THRESHOLDS = {
  trivial: 0.25,
  simple: 0.4,
  moderate: 0.55,
  hard: 0.7,
  expert: 0.8,
} as const;

export type ComplexityThresholds = typeof DEFAULT_COMPLEXITY_THRESHOLDS;

export const getEnabledDomains = (params: Record<string, boolean>): DomainType[] => {
  return DOMAIN_UI_CONFIGS.filter(({ toggleName }) => params[toggleName]).map(
    ({ domain }) => domain
  );
};
