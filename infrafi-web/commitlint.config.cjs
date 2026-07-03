module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // Disable conventional commit rules since we use custom [DAWN-xxx] format
    'type-enum': [0], // Disabled - handled by our custom validation
    'type-case': [0], // Disabled - handled by our custom validation
    'type-empty': [0], // Disabled - handled by our custom validation
    'scope-case': [0], // Disabled - not used in our format
    'subject-case': [0], // Disabled - handled by our custom validation
    'subject-empty': [0], // Disabled - handled by our custom validation
    'subject-full-stop': [0], // Disabled - handled by our custom validation

    // Keep some useful rules
    'header-max-length': [2, 'always', 200], // Increased to allow longer headers
    'header-min-length': [2, 'always', 10],
    'body-max-line-length': [0], // Disabled - allow longer descriptions
    'body-leading-blank': [2, 'always'], // Require blank line before body
    'footer-leading-blank': [2, 'always'] // Require blank line before footer
  }
}
