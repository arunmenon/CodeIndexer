# Claude Code Guidelines for CodeIndexer

## Code Standards
- Always use descriptive variable names
- When fixing code, first try to understand the existing patterns and maintain consistency
- Follow existing code style and naming conventions

## Testing Guidelines
- Always use existing scripts and tools for testing - don't create new scripts
- Ensure that scripts and tools are generic enough to handle different repositories
- Look for integration tests and end-to-end tests in the codebase before creating new ones
- Run full e2e tests when making changes to the pipeline or tree-sitter integration
- Test against multiple languages when making parser changes

## Git Workflow
- Keep commits focused on specific changes
- Use descriptive commit messages that explain the WHY not just the WHAT
- Never include "Claude Code" or other references to AI in commit messages
- Push only relevant changes to branches
- Remember to pull latest changes before pushing