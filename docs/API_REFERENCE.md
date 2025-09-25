# API Reference Documentation

Complete technical reference for the MCP Ollama Research Tool API.

## 🔧 Research Tool Schema

The research tool is registered as an MCP tool with the following complete schema:

### Tool Definition
```json
{
  "name": "research",
  "description": "Intelligent multi-model research tool that queries 3 different models and provides comparative analysis. Automatically selects optimal models based on complexity (simple/medium/complex) and focus (technical/business/ethical/creative/general). Returns convergent themes, divergent perspectives, and synthesized recommendations.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "question": {
        "type": "string",
        "description": "The research question to analyze across multiple models"
      },
      "complexity": {
        "type": "string",
        "enum": ["simple", "medium", "complex"],
        "description": "Query complexity level - determines model selection and response depth",
        "default": "medium"
      },
      "models": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Specific models to use (overrides automatic selection). Must be available in Ollama."
      },
      "focus": {
        "type": "string",
        "enum": ["technical", "business", "ethical", "creative", "general"],
        "description": "Research focus area - influences model selection and analysis approach",
        "default": "general"
      },
      "parallel": {
        "type": "boolean",
        "description": "Execute queries in parallel (faster) vs sequential (resource-friendly)",
        "default": false
      },
      "include_metadata": {
        "type": "boolean",
        "description": "Include detailed model metadata in responses",
        "default": false
      },
      "timeout": {
        "type": "number",
        "description": "Custom timeout in milliseconds. Overrides complexity-based timeout.",
        "minimum": 10000,
        "maximum": 600000
      },
      "temperature": {
        "type": "number",
        "description": "Model temperature (creativity level). Range: 0.1-1.0",
        "minimum": 0.1,
        "maximum": 1.0,
        "default": 0.7
      }
    },
    "required": ["question"]
  }
}
```

## 📋 Request Format

### Basic Request
```json
{
  "tool": "research",
  "question": "What are the advantages of using TypeScript in large applications?"
}
```

### Complete Request
```json
{
  "tool": "research",
  "question": "How should we architect a microservices system for 100k+ concurrent users?",
  "complexity": "complex",
  "models": ["llama3.2:7b", "qwen2.5-coder:7b", "mistral:7b"],
  "focus": "technical",
  "parallel": true,
  "include_metadata": true,
  "timeout": 240000,
  "temperature": 0.6
}
```

## 📄 Response Format

### Success Response Structure

```typescript
interface ResearchResult {
  question: string;
  focus: ResearchFocus;
  complexity: ComplexityLevel;
  timestamp: string;
  models_used: string[];
  responses: ModelResponse[];
  analysis: {
    convergent_themes: string[];
    divergent_perspectives: string[];
    reasoning_styles: ReasoningStyle[];
    synthesis: string;
    recommendations: string[];
    confidence_score: number; // 0-1 aggregate confidence
  };
  performance: {
    total_time: number;
    successful_responses: number;
    failed_responses: number;
    average_response_time: number;
  };
  errors?: string[];
}
```

### Model Response Structure

```typescript
interface ModelResponse {
  model: string;
  response: string;
  responseTime: number; // milliseconds
  tokenCount: number; // estimated
  confidence: number; // 0-1 based on response coherence
  error?: string;
  metadata?: {
    parameters: string; // e.g., "7B", "13B"
    contextWindow: number;
    tier: string; // "fast", "large", "cloud"
    temperature: number;
  };
}
```

### Reasoning Style Structure

```typescript
interface ReasoningStyle {
  model: string;
  style: 'analytical' | 'creative' | 'practical' | 'theoretical' | 'balanced';
  characteristics: string[];
  depth: 'surface' | 'moderate' | 'deep';
  confidence: number; // 0-1
}
```

### Example Success Response

```json
{
  "question": "What are the trade-offs between GraphQL and REST APIs?",
  "focus": "technical",
  "complexity": "medium",
  "timestamp": "2024-01-15T14:30:25.123Z",
  "models_used": ["llama3.2:7b", "qwen2.5-coder:7b", "mistral:7b"],
  "responses": [
    {
      "model": "llama3.2:7b",
      "response": "GraphQL offers several advantages over REST APIs...",
      "responseTime": 4250,
      "tokenCount": 387,
      "confidence": 0.89,
      "metadata": {
        "parameters": "7B",
        "contextWindow": 8192,
        "tier": "large",
        "temperature": 0.7
      }
    },
    {
      "model": "qwen2.5-coder:7b",
      "response": "From a development perspective, GraphQL provides...",
      "responseTime": 3840,
      "tokenCount": 425,
      "confidence": 0.91
    },
    {
      "model": "mistral:7b",
      "response": "REST APIs have been the standard for many years...",
      "responseTime": 5120,
      "tokenCount": 356,
      "confidence": 0.87
    }
  ],
  "analysis": {
    "convergent_themes": [
      "GraphQL reduces over-fetching compared to REST",
      "REST is simpler to implement and debug",
      "Both have their place depending on use case"
    ],
    "divergent_perspectives": [
      "Model 1 emphasizes GraphQL's flexibility advantages",
      "Model 2 focuses on developer experience trade-offs",
      "Model 3 highlights REST's maturity and tooling"
    ],
    "reasoning_styles": [
      {
        "model": "llama3.2:7b",
        "style": "analytical",
        "characteristics": ["systematic comparison", "evidence-based"],
        "depth": "moderate",
        "confidence": 0.89
      },
      {
        "model": "qwen2.5-coder:7b",
        "style": "practical",
        "characteristics": ["implementation-focused", "real-world examples"],
        "depth": "moderate",
        "confidence": 0.91
      },
      {
        "model": "mistral:7b",
        "style": "balanced",
        "characteristics": ["considers multiple perspectives", "historical context"],
        "depth": "moderate",
        "confidence": 0.87
      }
    ],
    "synthesis": "GraphQL and REST APIs each have distinct advantages. GraphQL excels in scenarios requiring flexible data fetching and reducing over-fetching, particularly beneficial for mobile applications and complex frontend requirements. REST APIs offer simplicity, extensive tooling, and easier debugging, making them ideal for straightforward CRUD operations and when simplicity is prioritized. The choice should be based on specific project requirements: use GraphQL for complex, data-intensive applications with varying client needs, and REST for simpler, more predictable API requirements.",
    "recommendations": [
      "Consider GraphQL for mobile-first applications with complex data requirements",
      "Choose REST for simple CRUD applications or when team familiarity is limited",
      "Evaluate hybrid approaches like REST with GraphQL for specific endpoints",
      "Factor in existing infrastructure and team expertise when deciding"
    ],
    "confidence_score": 0.89
  },
  "performance": {
    "total_time": 13210,
    "successful_responses": 3,
    "failed_responses": 0,
    "average_response_time": 4403
  }
}
```

## ❌ Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "McpErrorCode",
    "message": "Human-readable error message",
    "details": "Additional error context"
  }
}
```

### Common Error Codes

#### `InvalidRequest`
- **Cause**: Malformed request or missing required parameters
- **Example**: Missing `question` parameter
```json
{
  "error": {
    "code": "InvalidRequest",
    "message": "Missing required parameter: question"
  }
}
```

#### `InternalError`
- **Cause**: Server-side processing error
- **Example**: Model selection algorithm failure
```json
{
  "error": {
    "code": "InternalError",
    "message": "Research execution failed: No suitable models available for the requested complexity level"
  }
}
```

#### `ResourceUnavailable`
- **Cause**: Ollama server unavailable or models not accessible
- **Example**: Ollama server down
```json
{
  "error": {
    "code": "ResourceUnavailable",
    "message": "Failed to fetch available models: connect ECONNREFUSED 127.0.0.1:11434"
  }
}
```

#### `Timeout`
- **Cause**: Request exceeded timeout limits
- **Example**: Complex query taking too long
```json
{
  "error": {
    "code": "Timeout",
    "message": "Research request timed out after 180000ms"
  }
}
```

### Partial Failure Handling

When some models succeed and others fail, the tool returns partial results:

```json
{
  "question": "Analysis question",
  "models_used": ["llama3.2:7b", "mistral:7b"],
  "responses": [
    {
      "model": "llama3.2:7b",
      "response": "Successful response...",
      "responseTime": 4250,
      "tokenCount": 387,
      "confidence": 0.89
    },
    {
      "model": "qwen2.5-coder:7b",
      "response": "",
      "responseTime": 0,
      "tokenCount": 0,
      "confidence": 0,
      "error": "Timeout after 60000ms"
    },
    {
      "model": "mistral:7b",
      "response": "Another successful response...",
      "responseTime": 5120,
      "tokenCount": 356,
      "confidence": 0.87
    }
  ],
  "analysis": {
    // Analysis based on successful responses only
  },
  "performance": {
    "total_time": 65120,
    "successful_responses": 2,
    "failed_responses": 1,
    "average_response_time": 4685
  },
  "errors": [
    "Model qwen2.5-coder:7b failed: Timeout after 60000ms"
  ]
}
```

## ⚙️ Configuration Parameters

### Complexity-Based Defaults

```typescript
const COMPLEXITY_TIMEOUTS = {
  simple: {
    base: 30000,  // 30 seconds
    max: 90000    // 1.5 minutes
  },
  medium: {
    base: 60000,  // 1 minute
    max: 180000   // 3 minutes
  },
  complex: {
    base: 120000, // 2 minutes
    max: 300000   // 5 minutes
  }
};
```

### Model Tier System

```typescript
const MODEL_TIERS = {
  cloud: {
    name: 'cloud',
    minParams: 480,           // 480B+ parameters
    maxParams: Infinity,
    timeoutMultiplier: 3.0,
    complexitySupport: ['simple', 'medium', 'complex']
  },
  large: {
    name: 'large',
    minParams: 7,             // 7B-479B parameters
    maxParams: 479,
    timeoutMultiplier: 2.0,
    complexitySupport: ['simple', 'medium', 'complex']
  },
  fast: {
    name: 'fast',
    minParams: 0.1,           // 0.1B-6.9B parameters
    maxParams: 6.9,
    timeoutMultiplier: 1.0,
    complexitySupport: ['simple', 'medium']
  }
};
```

### Focus-Specific Model Preferences

```typescript
const FOCUS_PREFERENCES = {
  technical: ['codellama', 'deepseek-coder', 'qwen2.5-coder', 'starcoder'],
  business: ['llama3.2', 'qwen2.5', 'mistral', 'gemma2'],
  ethical: ['llama3.2', 'claude-3', 'gpt-4', 'mistral'],
  creative: ['llama3.2', 'mistral-7b', 'qwen2.5', 'gemma2'],
  general: ['llama3.2', 'qwen2.5', 'mistral', 'gemma2']
};
```

## 🔄 Integration Patterns

### MCP Client Integration

```typescript
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

// Initialize MCP client
const transport = new StdioClientTransport({
  command: 'node',
  args: ['path/to/mcp-ollama/build/index.js']
});

const client = new Client(
  { name: 'research-client', version: '1.0.0' },
  { capabilities: {} }
);

await client.connect(transport);

// Execute research query
const result = await client.callTool('research', {
  question: 'Compare React vs Vue for our project',
  complexity: 'medium',
  focus: 'technical'
});

console.log(result.content);
```

### HTTP Proxy Integration

While the MCP server uses stdio transport, you can wrap it with an HTTP proxy:

```typescript
import express from 'express';
import { spawn } from 'child_process';

const app = express();
app.use(express.json());

app.post('/research', async (req, res) => {
  try {
    const mcpProcess = spawn('node', ['build/index.js']);

    // Send MCP request
    mcpProcess.stdin.write(JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/call',
      params: {
        name: 'research',
        arguments: req.body
      }
    }) + '\n');

    // Handle response
    mcpProcess.stdout.on('data', (data) => {
      const response = JSON.parse(data.toString());
      res.json(response.result);
    });

  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(3000);
```

## 📊 Performance Characteristics

### Response Times by Complexity

| Complexity | Fast Models (1B-3B) | Large Models (7B-14B) | Cloud Models (70B+) |
|------------|---------------------|----------------------|---------------------|
| Simple     | 2-5 seconds        | 5-10 seconds         | 10-20 seconds       |
| Medium     | 5-15 seconds       | 15-30 seconds        | 30-60 seconds       |
| Complex    | 15-45 seconds      | 45-90 seconds        | 90-180 seconds      |

### Token Usage Estimates

| Complexity | Tokens per Model | Total Request | Analysis Overhead |
|------------|------------------|---------------|-------------------|
| Simple     | ~500 tokens      | ~1,500 tokens | ~200 tokens       |
| Medium     | ~1,500 tokens    | ~4,500 tokens | ~500 tokens       |
| Complex    | ~3,000 tokens    | ~9,000 tokens | ~1,000 tokens     |

### Parallel vs Sequential Performance

| Execution Mode | Time Savings | Resource Usage | Recommended For |
|----------------|--------------|----------------|-----------------|
| Sequential     | Baseline     | Low            | Default usage   |
| Parallel       | 40-60%       | High           | Time-critical   |

## 🧪 Testing Examples

### Unit Test Pattern

```typescript
import { ResearchTool } from '../src/research-tool.js';

describe('ResearchTool', () => {
  let researchTool: ResearchTool;

  beforeEach(() => {
    researchTool = new ResearchTool('http://localhost:11434');
  });

  test('should execute basic research query', async () => {
    const result = await researchTool.executeResearch({
      question: 'What is TypeScript?',
      complexity: 'simple'
    });

    expect(result.question).toBe('What is TypeScript?');
    expect(result.responses).toHaveLength(3);
    expect(result.analysis.confidence_score).toBeGreaterThan(0.7);
  });
});
```

### Integration Test Pattern

```typescript
import { Client } from '@modelcontextprotocol/sdk/client/index.js';

describe('MCP Research Integration', () => {
  let client: Client;

  beforeAll(async () => {
    // Setup MCP client
    client = await setupMCPClient();
  });

  test('should handle research tool call', async () => {
    const result = await client.callTool('research', {
      question: 'Compare Docker vs Podman',
      complexity: 'medium',
      focus: 'technical'
    });

    expect(result.content).toHaveProperty('analysis');
    expect(result.content.analysis.convergent_themes).toBeInstanceOf(Array);
  });
});
```

## 📝 Changelog

### Version 0.2.0
- **Added**: Multi-model research tool with comparative analysis
- **Added**: Intelligent model selection algorithm
- **Added**: Performance optimization with adaptive timeouts
- **Added**: Comprehensive error handling and partial failure support
- **Enhanced**: MCP SDK upgraded to v1.18.1
- **Enhanced**: TypeScript 5.9.2 support with ES2022 target

### Version 0.1.0
- Initial release with basic Ollama tool integration
- 10 core tools for model management and execution
- Enhanced parameter support for advanced use cases

## 🤝 Contributing

To extend the API:

1. **Add new parameters**: Update `ResearchRequest` interface in `research-types.ts`
2. **Modify selection logic**: Enhance `ModelSelector` class in `model-selector.ts`
3. **Improve analysis**: Extend `ResponseAnalyzer` class in `response-analyzer.ts`
4. **Update schema**: Modify tool registration in `index.ts`

See [Contributing Guide](../CONTRIBUTING.md) for detailed development setup.