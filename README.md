# Ollama MCP Server for Claude Desktop Commander

This MCP server provides integration between Ollama and Claude Desktop Commander, allowing Claude to interact with local LLMs through the Ollama API.

## Features

- Full Ollama API integration via MCP
- Model management (pull, push, create, remove)
- Model execution with configurability
- OpenAI-compatible chat completion API

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

- `serve`: Start Ollama server
- `create`: Create a model from a Modelfile
- `show`: Show information for a model
- `run`: Run a model with a prompt
- `pull`: Pull a model from a registry
- `push`: Push a model to a registry
- `list`: List available models
- `cp`: Copy a model
- `rm`: Remove a model
- `chat_completion`: OpenAI-compatible chat completion API

## Example Usage in Claude

```
Use the ollama:pull tool to download a model:
{
  "name": "llama2"
}

Use the ollama:run tool to execute a query:
{
  "name": "llama2",
  "prompt": "Explain quantum computing in simple terms"
}

Use the ollama:chat_completion tool for chat:
{
  "model": "llama2",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "What is the meaning of life?"
    }
  ],
  "temperature": 0.7
}
```

## Requirements

- Node.js (v16+)
- Ollama installed and accessible
