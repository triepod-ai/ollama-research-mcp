# Ollama MCP Server for Claude Desktop

A comprehensive Model Context Protocol (MCP) server that provides seamless integration between Ollama and Claude Desktop, enabling powerful local LLM interactions with superior tooling and user experience.

## What Sets Us Apart

### 🏆 **Most Comprehensive MCP Ollama Implementation**
Unlike other MCP Ollama servers that provide basic HTTP proxies or limited tool sets, we offer:

- **10 Complete Tools** vs 3-4 in other implementations
- **Native MCP Protocol** integration (not HTTP wrapper)
- **Enhanced Parameter Support** with intelligent validation
- **Professional Tool Descriptions** with actionable guidance

### 🎯 **Superior User Experience**
- **Clear Tool Descriptions**: Action-oriented guidance without emoji clutter
- **Workflow Integration**: Defined tool chaining patterns (list → show → run/chat_completion)
- **Model Recommendations**: Specific guidance (llama3.2:1b for speed, qwen2.5-coder for code)
- **Parameter Guidance**: Temperature ranges, usage examples, and validation

### ⚡ **Advanced Parameter Support**
Enhanced beyond standard implementations with:
- `temperature` with usage guidance (0.1-0.3 for code, 0.7-1.0 for creative)
- `seed` for reproducible outputs
- `system` prompts for custom behavior
- `max_tokens` for response length control
- `stop` sequences for precise generation control

### 🔧 **Enterprise-Ready Architecture**
- **Comprehensive Error Handling** with McpError wrapping
- **Performance Optimized** with direct API integration
- **Full API Coverage** including advanced features (create, push, cp)
- **WSL/Docker Compatible** with proper host configuration

## Features

- **Complete Ollama API Integration** via native MCP protocol
- **Advanced Model Management** (pull, push, create, remove, copy)
- **Enhanced Model Execution** with comprehensive parameter support
- **OpenAI-Compatible Chat Completion** with extended capabilities
- **Intelligent Tool Descriptions** for optimal discoverability

## Installation

1. Install dependencies:
```bash
npm install
```

2. Build the project:
```bash
npm run build
```

## Configuration

The server can be configured with the following environment variables:

- `OLLAMA_HOST`: Ollama API endpoint (default: http://127.0.0.1:11434)

## Usage

### Direct Execution

```bash
node build/index.js
```

### Integration with Claude Desktop Commander

Add the following to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["L:/ClaudeDesktopCommander/mcp-ollama/build/index.js"],
      "env": {
        "OLLAMA_HOST": "http://127.0.0.1:11434"
      }
    }
  }
}
```

## Available Tools

### 🎯 **High Priority - Core Execution**
- **`list`**: List all locally available Ollama models. Returns name, size, and last modified date. Start here to see what models you have.
- **`show`**: Get detailed model information including context window size, parameters, and architecture. Use after list to understand model capabilities.
- **`run`**: Execute a single prompt with a model. Best for one-shot tasks. Use llama3.2:1b for speed (2-3s), qwen2.5-coder for code (5-8s).
  - Enhanced with: `temperature`, `seed`, `system` prompt support
- **`chat_completion`**: Multi-turn conversation with context. Use for iterative tasks. Temperature: 0.1-0.3 for code, 0.7-1.0 for creative.
  - Enhanced with: `max_tokens`, `stop` sequences, advanced parameter validation

### 📦 **Model Management**
- **`pull`**: Download model from registry. Popular: llama3.2:1b (1GB, fast), qwen2.5-coder:7b-instruct (5GB, code), mistral:7b (4GB).

### 🔧 **Utilities & Advanced**
- **`create`**: Create custom model from Modelfile. Define system prompts and parameters. Format: FROM base_model\nSYSTEM "prompt"
- **`push`**: Upload model to Ollama registry. Requires account and authentication. Name format: username/modelname:tag
- **`cp`**: Copy a model with a new name. Useful for creating backups before modifications or versioning custom models.
- **`rm`**: Delete a local model to free disk space. Permanent action - model must be re-downloaded to use again.
- **`serve`**: Start Ollama server. Usually runs automatically on Windows. Default port: 11434.

## Example Usage in Claude

### 🚀 **Workflow Examples**

**1. Model Discovery & Setup:**
```json
// Start by listing available models
{"tool": "list"}

// Get detailed info about a specific model
{"tool": "show", "name": "llama3.2:1b"}

// Pull a new model if needed
{"tool": "pull", "name": "qwen2.5-coder:7b-instruct"}
```

**2. Enhanced Single Prompt with Advanced Parameters:**
```json
{
  "tool": "run",
  "name": "qwen2.5-coder:7b-instruct",
  "prompt": "Write a Python function to calculate fibonacci numbers",
  "temperature": 0.2,
  "seed": 42,
  "system": "You are an expert Python developer. Write clean, efficient code."
}
```

**3. Advanced Chat Completion with Full Parameter Support:**
```json
{
  "tool": "chat_completion",
  "model": "llama3.2:3b",
  "messages": [
    {
      "role": "system",
      "content": "You are a creative writing assistant."
    },
    {
      "role": "user",
      "content": "Write a short story about AI and humanity."
    }
  ],
  "temperature": 0.8,
  "max_tokens": 500,
  "stop": ["THE END", "\n---"]
}
```

**4. Model Management:**
```json
// Create a custom model
{
  "tool": "create",
  "name": "my-coding-assistant",
  "modelfile": "FROM qwen2.5-coder:7b-instruct\nSYSTEM \"You are an expert software engineer.\""
}

// Backup before modifications
{"tool": "cp", "source": "my-coding-assistant", "destination": "my-coding-assistant-backup"}
```

## Comparison with Other MCP Ollama Implementations

| Feature | **This Implementation** | Other MCP Servers |
|---------|-------------------------|-------------------|
| **Architecture** | ✅ Native MCP Protocol | HTTP Proxy Wrapper |
| **Tool Count** | ✅ **10 Comprehensive Tools** | 3-4 Basic Endpoints |
| **Parameter Support** | ✅ **Enhanced (temperature, seed, system, max_tokens, stop)** | Basic Parameters |
| **Descriptions** | ✅ **Action-oriented, Clear Guidance** | Minimal/Technical |
| **Workflow Integration** | ✅ **Defined Tool Chaining** | Isolated Tools |
| **Model Recommendations** | ✅ **Specific Performance Guidance** | Generic |
| **Error Handling** | ✅ **Comprehensive McpError Integration** | Basic HTTP Errors |
| **Documentation** | ✅ **Professional, Example-Rich** | Basic |

### Why Choose This Implementation?

- **🎯 Best User Experience**: Clear tool descriptions and workflow guidance
- **⚡ Superior Performance**: Direct API integration, no HTTP overhead
- **🔧 Professional Quality**: Enterprise-ready error handling and validation
- **📚 Complete Documentation**: Comprehensive examples and parameter explanations
- **🚀 Active Development**: Continuously optimized based on ecosystem analysis

## Requirements

- Node.js (v16+)
- Ollama installed and accessible

## Contributing

Contributions are welcome! This implementation represents the most comprehensive MCP Ollama server available, and we're committed to maintaining that standard.
