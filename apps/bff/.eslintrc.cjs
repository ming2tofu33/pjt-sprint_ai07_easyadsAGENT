module.exports = {
  root: true,
  env: {
    es2022: true,
    node: true
  },
  extends: ["eslint:recommended"],
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module"
  },
  overrides: [
    {
      files: ["tests/**/*.js"],
      env: { node: true },
      globals: {
        describe: "readonly",
        expect: "readonly",
        it: "readonly",
        vi: "readonly"
      },
      rules: {
        "no-unused-vars": ["error", { args: "none", varsIgnorePattern: "^_" }]
      }
    }
  ],
  rules: {
    complexity: ["warn", 25],
    "max-lines-per-function": ["warn", { max: 120, skipBlankLines: true, skipComments: true }],
    "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    "no-console": "off"
  }
};
