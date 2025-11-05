import {
  IAuthenticateGeneric,
  ICredentialTestRequest,
  ICredentialType,
  INodeProperties,
} from 'n8n-workflow';

export class cascadeflowApi implements ICredentialType {
  name = 'cascadeFlowApi';
  displayName = 'cascadeflow API';
  documentationUrl = 'https://github.com/lemony-ai/cascadeflow';
  properties: INodeProperties[] = [
    {
      displayName: 'OpenAI API Key',
      name: 'openaiApiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'API key for OpenAI (GPT-4, GPT-4o, etc.)',
      placeholder: 'sk-...',
    },
    {
      displayName: 'Anthropic API Key',
      name: 'anthropicApiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'API key for Anthropic (Claude models)',
      placeholder: 'sk-ant-...',
    },
    {
      displayName: 'Groq API Key',
      name: 'groqApiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'API key for Groq (fast Llama inference)',
      placeholder: 'gsk_...',
    },
    {
      displayName: 'Together AI API Key',
      name: 'togetherApiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'API key for Together AI',
      placeholder: '',
    },
    {
      displayName: 'HuggingFace API Key',
      name: 'huggingfaceApiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'API key for HuggingFace Inference',
      placeholder: 'hf_...',
    },
  ];

  authenticate: IAuthenticateGeneric = {
    type: 'generic',
    properties: {},
  };

  test: ICredentialTestRequest = {
    request: {
      baseURL: 'https://api.openai.com/v1',
      url: '/models',
      method: 'GET',
      headers: {
        Authorization: '=Bearer {{$credentials.openaiApiKey}}',
      },
    },
  };
}
