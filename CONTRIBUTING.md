# Contributing to MCP Ollama Server

Thank you for your interest in contributing to the MCP Ollama Server! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites
- Node.js v16+
- TypeScript 5.0+
- Ollama installed and running locally
- Claude Desktop (for testing MCP integration)

### Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/mcp-ollama.git
   cd mcp-ollama
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Build the project:
   ```bash
   npm run build
   ```

5. Run in development mode:
   ```bash
   npm run watch
   ```

## Code Style

- TypeScript with ES modules
- Follow existing code patterns and conventions
- Use meaningful variable and function names
- Add JSDoc comments for public APIs
- Keep tool handlers focused and single-purpose

## Testing

Before submitting a PR:

1. Test with MCP Inspector:
   ```bash
   npm run inspector
   ```

2. Test integration with Claude Desktop
3. Verify all Ollama tools work correctly
4. Check for TypeScript errors:
   ```bash
   npx tsc --noEmit
   ```

## Pull Request Process

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code style guidelines
3. Update the CHANGELOG.md with your changes
4. Commit with descriptive messages:
   ```bash
   git commit -m "feat: Add new feature description"
   ```

5. Push to your fork and create a Pull Request
6. Describe your changes and link any relevant issues

## Commit Message Format

Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include steps to reproduce for bugs
- Provide system information (OS, Node version, Ollama version)
- Include relevant logs and error messages

## Questions?

Feel free to open a discussion or issue for any questions about contributing.