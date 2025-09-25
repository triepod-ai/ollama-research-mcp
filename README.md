# Ollama MCP Server for Claude Desktop Commander

A comprehensive Model Context Protocol (MCP) server that provides seamless integration between Ollama and Claude Desktop, featuring intelligent multi-model research capabilities and superior tooling experience.

## 🚀 **Revolutionary Research Capabilities**

### **Multi-Model Comparative Research Tool**
The crown jewel of this implementation - an intelligent research system that:

- **Automatically selects optimal models** based on query complexity and focus area
- **Executes parallel or sequential queries** across multiple models simultaneously
- **Provides comparative analysis** with convergent themes, divergent perspectives, and reasoning styles
- **Synthesizes insights** from different model approaches into actionable recommendations
- **Optimizes performance** with intelligent timeout management and model tier selection

### **Recent Enhancements (v0.2.1)**
- **Enhanced Theme Extraction**: Now captures meaningful 2-3 word concepts instead of single words
- **Small Model Divergence**: Revolutionary perspective variation for models <8B using specialized prompting
- **Calibrated Confidence**: Model-aware confidence scoring based on size and tier (realistic 10-95% bounds)

### **Intelligent Model Selection**
- **Complexity-Aware**: Automatically matches models to query complexity (simple/medium/complex)
- **Focus-Optimized**: Selects models based on specialization (technical/business/ethical/creative/general)
- **Performance-Balanced**: Considers response time, reliability, and model capabilities
- **Resource-Efficient**: Adaptive timeout management and parallel execution strategies

## What Sets Us Apart

### 🏆 **Most Comprehensive MCP Ollama Implementation**
Unlike other MCP Ollama servers that provide basic HTTP proxies or limited tool sets, we offer:

- **11 Complete Tools** vs 3-4 in other implementations (including advanced research tool)
- **Native MCP Protocol** integration (not HTTP wrapper)
- **Enhanced Parameter Support** with intelligent validation
- **Professional Tool Descriptions** with actionable guidance
- **Multi-Model Research Engine** for comparative analysis

### 🎯 **Superior User Experience**
- **Clear Tool Descriptions**: Action-oriented guidance without emoji clutter
- **Workflow Integration**: Defined tool chaining patterns (list → show → run/chat_completion)
- **Model Recommendations**: Specific guidance (llama3.2:1b for speed, qwen2.5-coder for code)
- **Parameter Guidance**: Temperature ranges, usage examples, and validation
- **Intelligent Research**: One-command multi-model comparative analysis

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
- **Production Testing Suite** with unit, integration, performance, and E2E tests

## Features

- **Complete Ollama API Integration** via native MCP protocol
- **Multi-Model Research Tool** with comparative analysis capabilities
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

### 🔬 **Revolutionary Research Tool**
- **`research`**: **Intelligent multi-model research tool** that queries 3 different models and provides comparative analysis. Automatically selects optimal models based on complexity (simple/medium/complex) and focus (technical/business/ethical/creative/general). Returns convergent themes, divergent perspectives, and synthesized recommendations.
  - **Parameters**: `question` (required), `complexity`, `models`, `focus`, `parallel`, `include_metadata`, `timeout`, `temperature`
  - **Best for**: Complex research questions, comparative analysis, getting diverse perspectives on topics

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

**4. Intelligent Multi-Model Research (New!):**
```json
// Simple research with automatic model selection
{
  "tool": "research",
  "question": "What are the pros and cons of microservices architecture?",
  "complexity": "medium",
  "focus": "technical"
}

// Complex research with parallel execution
{
  "tool": "research",
  "question": "How will AI impact software development in the next 5 years?",
  "complexity": "complex",
  "focus": "business",
  "parallel": true,
  "include_metadata": true,
  "temperature": 0.8
}

// Research with specific models
{
  "tool": "research",
  "question": "Explain quantum computing to a business audience",
  "models": ["llama3.2:3b", "qwen2.5:7b", "mistral:7b"],
  "complexity": "medium",
  "focus": "business"
}
```

**5. Model Management:**
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
| **Tool Count** | ✅ **11 Comprehensive Tools** | 3-4 Basic Endpoints |
| **Research Capabilities** | ✅ **Multi-Model Comparative Research** | ❌ Not Available |
| **Model Selection** | ✅ **Intelligent Selection Algorithm** | ❌ Manual Only |
| **Parameter Support** | ✅ **Enhanced (temperature, seed, system, max_tokens, stop)** | Basic Parameters |
| **Descriptions** | ✅ **Action-oriented, Clear Guidance** | Minimal/Technical |
| **Workflow Integration** | ✅ **Defined Tool Chaining** | Isolated Tools |
| **Model Recommendations** | ✅ **Specific Performance Guidance** | Generic |
| **Error Handling** | ✅ **Comprehensive McpError Integration** | Basic HTTP Errors |
| **Testing Suite** | ✅ **Production-Ready Test Coverage** | ❌ Minimal Testing |
| **Documentation** | ✅ **Professional, Example-Rich** | Basic |

### Why Choose This Implementation?

- **🎯 Best User Experience**: Clear tool descriptions and workflow guidance
- **⚡ Superior Performance**: Direct API integration, no HTTP overhead
- **🔧 Professional Quality**: Enterprise-ready error handling and validation
- **📚 Complete Documentation**: Comprehensive examples and parameter explanations
- **🚀 Active Development**: Continuously optimized based on ecosystem analysis

## 📚 Documentation

### Complete Documentation Suite

- **[Research Tool User Guide](docs/RESEARCH_TOOL_GUIDE.md)** - Comprehensive user guide for the multi-model research tool
- **[API Reference](docs/API_REFERENCE.md)** - Complete technical API documentation with schemas and examples
- **[Architecture Guide](docs/ARCHITECTURE.md)** - Technical architecture, data flow, and system design
- **[Development Guide](docs/DEVELOPMENT.md)** - Developer documentation for extending and contributing
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues, solutions, and debugging techniques

### Quick Links

- **Get Started**: Follow the [Installation](#installation) section above
- **Use Research Tool**: See [Research Tool Examples](#4-intelligent-multi-model-research-new)
- **Troubleshoot Issues**: Check the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- **Extend Functionality**: Read the [Development Guide](docs/DEVELOPMENT.md)
- **Understand Architecture**: Review the [Architecture Guide](docs/ARCHITECTURE.md)

## Testing Suite

The project includes comprehensive testing coverage:

```bash
# Run all tests
npm test

# Run specific test suites
npm run test:unit          # Unit tests for individual components
npm run test:integration   # Integration tests with MCP and Ollama
npm run test:performance   # Performance benchmarks and load tests
npm run test:e2e          # End-to-end workflow testing

# Coverage reporting
npm run test:coverage

# Continuous testing during development
npm run test:watch
```

**Test Coverage:**
- **Unit Tests**: Model selection, response analysis, research orchestration
- **Integration Tests**: MCP protocol compliance, Ollama API integration
- **Performance Tests**: Response time benchmarks, resource usage validation
- **End-to-End Tests**: Complete research workflows with real models

## Requirements

- **Node.js (v18+)** (v20+ recommended for optimal performance)
- **Ollama installed and accessible** with at least a few models pulled
- **Minimum 4GB RAM** (8GB+ recommended for complex research)
- **Available disk space** for models (varies by model size, typically 1-50GB)

### Recommended Models for Optimal Experience

```bash
# Fast models for quick responses (1-3GB each)
ollama pull llama3.2:1b
ollama pull llama3.2:3b

# Balanced models for general use (4-8GB each)
ollama pull llama3.2:7b
ollama pull qwen2.5:7b
ollama pull mistral:7b

# Specialized models for technical focus
ollama pull qwen2.5-coder:7b-instruct
ollama pull deepseek-coder:6.7b

# Large models for complex analysis (10-50GB each, optional)
ollama pull llama3.2:70b
ollama pull qwen2.5:72b
```

## Performance Characteristics

| Configuration | Response Time | Resource Usage | Best For |
|---------------|---------------|----------------|----------|
| Simple + Fast Models (1-3B) | 2-10 seconds | Low (1-2GB RAM) | Quick questions, definitions |
| Medium + Balanced Models (7B) | 10-60 seconds | Medium (4-6GB RAM) | Analysis, comparisons |
| Complex + Large Models (70B+) | 60-300 seconds | High (16GB+ RAM) | Deep research, strategy |

## Contributing

We welcome contributions to make this the most comprehensive MCP Ollama implementation available!

### Development Setup

```bash
git clone <repository-url>
cd mcp-ollama
npm install
npm run build
npm test
```

### Contribution Areas

- **Research Tool Enhancements**: New analysis types, model selection strategies
- **Performance Optimizations**: Caching, parallel processing, resource management
- **Documentation**: User guides, tutorials, examples
- **Testing**: Additional test coverage, performance benchmarks
- **Integration**: New MCP clients, deployment scenarios

See our [Development Guide](docs/DEVELOPMENT.md) for detailed contribution instructions, coding standards, and testing requirements.
