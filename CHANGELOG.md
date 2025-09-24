# Changelog

All notable changes to the MCP Ollama Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-09-24

### Changed
- Upgraded @modelcontextprotocol/sdk from v0.6.0 to v1.18.1
- Updated TypeScript from 5.3.3 to 5.9.2
- Updated @types/node from 20.11.24 to 24.5.2
- Maintained full backward compatibility with existing Claude Desktop configurations

### Fixed
- Compatibility with latest MCP SDK version

## [0.1.0] - 2025-03-23

### Added
- Initial implementation of MCP server for Ollama integration
- Full Ollama API support via MCP protocol
- Model management tools (pull, push, create, remove)
- Model execution with configurable parameters
- OpenAI-compatible chat completion API
- Support for both CLI and HTTP API operations
- Comprehensive error handling with McpError wrapping
- Performance-optimized tool handlers with tiered classification