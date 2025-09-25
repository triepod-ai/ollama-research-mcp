# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Recent Updates (2025-09-25)

### Research Tool Improvements (v0.2.1)
- **Enhanced Theme Extraction**: Improved to capture 2-3 word phrase concepts instead of single words for better thematic analysis
- **Small Model Divergence**: Revolutionary perspective variation for models <8B parameters using specialized prompting, higher temperature, and unique seeds
- **Calibrated Confidence Scoring**: Model-aware confidence adjustment based on size (small: 40-45%, medium: 45-50%, large: 50-60%) with realistic 10-95% bounds

## Recent Updates (2025-09-24)

### Tool Optimization & Enhancement
- **Optimized Tool Descriptions**: Simplified, clear descriptions without emoji clutter for better discoverability
- **Enhanced Parameters**: Added missing parameters (temperature, seed, system, max_tokens, stop) to core tools
- **Workflow Integration**: Defined clear tool chaining patterns (list → show → run/chat_completion)
- **Model Recommendations**: Specific model guidance (llama3.2:1b for speed, qwen2.5-coder for code)
- **Improved Error Handling**: Better parameter validation and descriptive error messages

### SDK & Infrastructure
- **MCP SDK Upgrade**: Successfully upgraded from v0.6.0 to v1.18.1
- **TypeScript Update**: Updated to TypeScript 5.9.2
- **Compatibility**: Server maintains backward compatibility with existing Claude Desktop configurations
- **Version Bump**: Server version updated to 0.2.0 to reflect the SDK upgrade

## Build and Development Commands

```bash
# Install dependencies
npm install

# Build the TypeScript project
npm run build

# Development mode with file watching
npm run watch

# Start the server directly
npm start
# Or
node build/index.js

# Test with MCP Inspector
npm run inspector
```

## Architecture Overview

### MCP Server Implementation
This project implements a Model Context Protocol (MCP) server that bridges Claude Desktop Commander with Ollama's local LLM API. The server uses TypeScript with ES modules and communicates via stdio transport.

**Core Components:**
- **OllamaServer class** (`src/index.ts`): Main server implementation handling MCP protocol
- **Tool Handlers**: Each Ollama command maps to an MCP tool (list, run, chat_completion, etc.)
- **API Integration**: Uses axios for HTTP communication with Ollama at `http://127.0.0.1:11434`
- **Error Handling**: Comprehensive McpError wrapping for proper MCP error responses

### Key Design Patterns

**1. Tool Registration Pattern:**
All tools are registered in `setupToolHandlers()` with:
- Clear, action-oriented descriptions without emoji clutter
- Enhanced parameter schemas with usage guidance
- Workflow chaining recommendations (list → show → run/chat_completion)
- Model-specific recommendations and performance characteristics

**2. API vs CLI Integration:**
- Performance-critical operations (list, show, run, chat_completion) use direct HTTP API
- System operations (serve, create, pull, push) use CLI commands via `execAsync`
- Non-streaming mode used for compatibility and simplicity

**3. Error Handling Strategy:**
- All errors wrapped in McpError with appropriate ErrorCode
- Axios errors specially handled to extract API error messages
- Fallback to formatted error strings for unexpected errors

## Integration with Claude Desktop

Add to Claude Desktop configuration (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["L:/source-repos/mcp-ollama/build/index.js"],
      "env": {
        "OLLAMA_HOST": "http://host.docker.internal:11434"
      }
    }
  }
}
```

**Note**: For WSL/Docker environments, use `http://host.docker.internal:11434` or your host machine's IP (e.g., `http://10.0.0.225:11434`) instead of `localhost`.

## Common Workflows

### Model Discovery Workflow
1. Start with `list` tool to see available models
2. Use `show` tool to get detailed model specifications (context length, parameters)
3. Execute with `run` or `chat_completion` based on requirements

### Performance Optimization
- `llama3.2:1b`: 2-3s response time for quick tasks
- `qwen2.5-coder:7b-instruct`: 5-8s for code generation
- `smallthinker:latest`: 4-6s for analysis tasks
- Adjust timeout parameter based on prompt complexity (default: 60000ms)

### Temperature Guidelines
- **0.1-0.3**: Code generation and technical tasks
- **0.7-1.0**: Creative and conversational tasks

### Research Tool
- For meaningful divergent perspectives, use larger models (>20B parameters) - smaller models often produce empty divergent analysis

## Module System Configuration

**Type**: ES Modules (`"type": "module"` in package.json)
**TypeScript Target**: ES2022 with Node16 module resolution
**Entry Point**: `build/index.js` (compiled from `src/index.ts`)

## Environment Variables

- `OLLAMA_HOST`: Ollama API endpoint (default: `http://127.0.0.1:11434`)
  - For WSL/Docker: May need `host.docker.internal:11434`

## Troubleshooting

If JSON parsing errors occur:
1. Verify module system alignment (ES modules throughout)
2. Check that all imports use `.js` extensions for local files
3. Ensure TypeScript compilation completes without errors
4. Verify Ollama service is running and accessible at configured host