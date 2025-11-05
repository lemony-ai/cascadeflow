module.exports = {
	parser: '@typescript-eslint/parser',
	parserOptions: {
		ecmaVersion: 2020,
		sourceType: 'module',
	},
	plugins: ['eslint-plugin-n8n-nodes-base'],
	extends: [
		'plugin:n8n-nodes-base/nodes',
		'plugin:n8n-nodes-base/credentials',
		'plugin:n8n-nodes-base/community',
	],
	rules: {
		// Disable conflicting rules for documentationUrl
		'n8n-nodes-base/cred-class-field-documentation-url-miscased': 'off',
		'n8n-nodes-base/cred-class-field-documentation-url-not-http-url': 'off',
	},
};
