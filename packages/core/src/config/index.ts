/**
 * Configuration module exports
 */

export {
  type DomainConfig,
  type DomainConfigMap,
  type DomainValidationMethod,
  DEFAULT_DOMAIN_CONFIG,
  BUILTIN_DOMAIN_CONFIGS,
  createDomainConfig,
  validateDomainConfig,
  getBuiltinDomainConfig,
  validationMethodToDomain,
  domainValidationToMethod,
} from './domain-config';

export {
  type ModelRegistryEntry,
  ModelRegistry,
  defaultModelRegistry,
  getModel,
  hasModel,
} from './model-registry';
