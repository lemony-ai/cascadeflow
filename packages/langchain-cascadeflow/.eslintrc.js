module.exports = {
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
    project: './tsconfig.json',
  },
  plugins: ['@typescript-eslint'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  rules: {
    // Gradual type-safety improvements
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    '@typescript-eslint/no-var-requires': 'warn',

    // Code quality (warnings instead of errors)
    'prefer-const': 'warn',
    'no-useless-escape': 'warn',
  },
  ignorePatterns: ['dist', 'node_modules', '*.js', 'examples', '__tests__'],
};

