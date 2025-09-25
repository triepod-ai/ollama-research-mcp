# Development Documentation

Comprehensive guide for developers extending and contributing to the MCP Ollama Research Tool.

## 🚀 Getting Started

### Prerequisites

- **Node.js 18+** (v20+ recommended)
- **TypeScript 5.0+**
- **Ollama** installed and running locally
- **Git** for version control

### Development Setup

1. **Clone and Setup**
```bash
git clone <repository-url>
cd mcp-ollama
npm install
```

2. **Install Development Dependencies**
```bash
# Install type definitions and testing tools
npm install --save-dev @types/jest jest ts-jest
npm install --save-dev @types/node typescript
```

3. **Configure Ollama Environment**
```bash
# Ensure Ollama is running
ollama serve

# Pull some test models
ollama pull llama3.2:1b
ollama pull qwen2.5:7b
ollama pull mistral:7b
```

4. **Build and Test**
```bash
# Build the project
npm run build

# Run tests
npm test

# Start development server
npm run watch
```

### Development Workflow

```bash
# Development cycle
npm run watch          # Auto-rebuild on changes
npm run test:watch     # Auto-run tests on changes
npm run lint          # Type checking
npm run test:coverage # Coverage reporting
```

## 🏗️ Project Structure

### Source Code Organization

```
src/
├── index.ts                    # Main MCP server entry point
├── research-tool.ts           # Primary research orchestrator
├── model-selector.ts          # Intelligent model selection
├── response-analyzer.ts       # Response analysis and synthesis
├── response-formatter.ts      # Output formatting utilities
├── performance-config.ts      # Performance management
└── research-types.ts          # TypeScript type definitions
```

### Testing Structure

```
tests/
├── unit/
│   ├── model-selector.test.ts      # Model selection tests
│   ├── response-analyzer.test.ts   # Analysis algorithm tests
│   └── research-tool.test.ts       # Core logic tests
├── integration/
│   ├── mcp-server.test.ts          # MCP integration tests
│   └── ollama-integration.test.ts  # Ollama API tests
├── performance/
│   └── research-performance.test.ts # Performance benchmarks
├── e2e/
│   └── end-to-end.test.ts          # End-to-end scenarios
└── fixtures/
    ├── mock-models.json            # Test model data
    └── sample-responses.json       # Test response data
```

### Configuration Files

```
├── package.json              # Dependencies and scripts
├── tsconfig.json            # TypeScript configuration
├── jest.config.js           # Testing configuration
├── .gitignore              # Version control exclusions
└── docs/                   # Documentation
    ├── RESEARCH_TOOL_GUIDE.md
    ├── API_REFERENCE.md
    ├── ARCHITECTURE.md
    └── DEVELOPMENT.md (this file)
```

## 🧩 Component Development

### Adding New Analysis Features

#### 1. Extend Analysis Types

```typescript
// In research-types.ts
export interface CustomAnalysis {
  sentiment_analysis: {
    positive_indicators: string[];
    negative_indicators: string[];
    overall_sentiment: 'positive' | 'neutral' | 'negative';
    confidence: number;
  };
}

// Extend ResearchResult interface
export interface ResearchResult {
  // ... existing properties
  analysis: {
    // ... existing properties
    custom_analysis?: CustomAnalysis;
  };
}
```

#### 2. Implement Analysis Logic

```typescript
// In response-analyzer.ts
export class ResponseAnalyzer {
  // ... existing methods

  /**
   * Analyze sentiment across model responses
   */
  private analyzeSentiment(responses: ModelResponse[]): CustomAnalysis['sentiment_analysis'] {
    const positiveWords = ['excellent', 'great', 'beneficial', 'optimal'];
    const negativeWords = ['poor', 'problematic', 'difficult', 'challenging'];

    const sentiments = responses.map(response => {
      const text = response.response.toLowerCase();
      const positiveCount = positiveWords.filter(word => text.includes(word)).length;
      const negativeCount = negativeWords.filter(word => text.includes(word)).length;

      return {
        model: response.model,
        positive: positiveCount,
        negative: negativeCount,
        score: positiveCount - negativeCount
      };
    });

    // Aggregate sentiment
    const totalScore = sentiments.reduce((sum, s) => sum + s.score, 0);
    const avgScore = totalScore / sentiments.length;

    return {
      positive_indicators: positiveWords,
      negative_indicators: negativeWords,
      overall_sentiment: avgScore > 0.5 ? 'positive' : avgScore < -0.5 ? 'negative' : 'neutral',
      confidence: Math.abs(avgScore) / Math.max(positiveWords.length, negativeWords.length)
    };
  }

  async analyzeResponses(
    question: string,
    responses: ModelResponse[],
    focus: ResearchFocus,
    complexity: ComplexityLevel,
    enableCustomAnalysis = false
  ): Promise<ResearchResult> {
    // ... existing analysis logic

    const analysis = {
      // ... existing analysis properties
      ...(enableCustomAnalysis && {
        custom_analysis: {
          sentiment_analysis: this.analyzeSentiment(responses)
        }
      })
    };

    return {
      // ... other properties
      analysis
    };
  }
}
```

#### 3. Add Parameter Support

```typescript
// In research-types.ts
export interface ResearchRequest {
  // ... existing properties
  enable_custom_analysis?: boolean;
}

// In research-tool.ts
export class ResearchTool {
  async executeResearch(request: ResearchRequest): Promise<ResearchResult> {
    const {
      // ... existing destructuring
      enable_custom_analysis = false
    } = request;

    // ... existing logic

    const result = await this.responseAnalyzer.analyzeResponses(
      question,
      responses,
      focus,
      complexity,
      enable_custom_analysis // Pass the new parameter
    );

    return result;
  }
}
```

#### 4. Update MCP Tool Schema

```typescript
// In index.ts, update tool registration
{
  name: 'research',
  description: '...',
  inputSchema: {
    type: 'object',
    properties: {
      // ... existing properties
      enable_custom_analysis: {
        type: 'boolean',
        description: 'Enable custom analysis features like sentiment analysis',
        default: false
      }
    }
  }
}
```

### Adding New Model Selection Strategies

#### 1. Define Strategy Interface

```typescript
// In research-types.ts
export interface SelectionStrategy {
  name: string;
  description: string;
  select(criteria: ModelSelectionCriteria): Promise<ModelCapabilities[]>;
  priority: number;
}
```

#### 2. Implement Custom Strategy

```typescript
// In model-selector.ts
export class ModelSelector {
  private strategies: Map<string, SelectionStrategy> = new Map();

  constructor() {
    // Register default strategies
    this.registerStrategy(new DefaultSelectionStrategy());
    this.registerStrategy(new PerformanceOptimizedStrategy());
    this.registerStrategy(new DiversityFocusedStrategy());
  }

  registerStrategy(strategy: SelectionStrategy): void {
    this.strategies.set(strategy.name, strategy);
  }

  async selectModels(
    criteria: ModelSelectionCriteria,
    strategyName = 'default'
  ): Promise<SelectionResult> {
    const strategy = this.strategies.get(strategyName);
    if (!strategy) {
      throw new Error(`Unknown selection strategy: ${strategyName}`);
    }

    const selectedModels = await strategy.select(criteria);

    return {
      primary: selectedModels[0],
      secondary: selectedModels[1],
      tertiary: selectedModels[2],
      fallbacks: selectedModels.slice(3),
      strategy: strategyName,
      reasoning: `Selected using ${strategy.description}`
    };
  }
}

// Example custom strategy
class PerformanceOptimizedStrategy implements SelectionStrategy {
  name = 'performance-optimized';
  description = 'Prioritizes fastest response times';
  priority = 2;

  async select(criteria: ModelSelectionCriteria): Promise<ModelCapabilities[]> {
    const { availableModels, complexity, preferredCount } = criteria;

    // Filter by complexity support
    const suitable = availableModels.filter(model =>
      model.complexity.includes(complexity)
    );

    // Sort by average response time (ascending)
    const sorted = suitable.sort((a, b) =>
      a.averageResponseTime - b.averageResponseTime
    );

    // Return top performers
    return sorted.slice(0, preferredCount);
  }
}
```

### Adding New Focus Areas

#### 1. Extend Focus Type

```typescript
// In research-types.ts
export type ResearchFocus =
  | 'technical'
  | 'business'
  | 'ethical'
  | 'creative'
  | 'general'
  | 'scientific'    // New focus area
  | 'legal';        // New focus area

// Add to focus preferences
export const FOCUS_PREFERENCES: Record<ResearchFocus, string[]> = {
  // ... existing preferences
  scientific: ['llama3.2', 'qwen2.5', 'deepseek-coder', 'mistral'],
  legal: ['llama3.2', 'claude-3', 'gpt-4', 'mistral']
};
```

#### 2. Update Analysis Logic

```typescript
// In response-analyzer.ts
export class ResponseAnalyzer {
  private getFocusSpecificKeywords(focus: ResearchFocus): string[] {
    const keywords = {
      // ... existing keywords
      scientific: ['research', 'study', 'hypothesis', 'methodology', 'peer-reviewed'],
      legal: ['regulation', 'compliance', 'law', 'statute', 'precedent']
    };

    return keywords[focus] || [];
  }

  private analyzeFocusRelevance(
    responses: ModelResponse[],
    focus: ResearchFocus
  ): number {
    const keywords = this.getFocusSpecificKeywords(focus);

    const relevanceScores = responses.map(response => {
      const text = response.response.toLowerCase();
      const keywordMatches = keywords.filter(keyword =>
        text.includes(keyword)
      ).length;

      return keywordMatches / keywords.length;
    });

    return relevanceScores.reduce((sum, score) => sum + score, 0) / relevanceScores.length;
  }
}
```

## 🧪 Testing Development

### Writing Unit Tests

#### Test Structure Template

```typescript
// tests/unit/example-component.test.ts
import { describe, test, expect, beforeEach, jest } from '@jest/globals';
import { ExampleComponent } from '../../src/example-component.js';

describe('ExampleComponent', () => {
  let component: ExampleComponent;

  beforeEach(() => {
    component = new ExampleComponent();
  });

  describe('methodName', () => {
    test('should handle normal case', async () => {
      const input = { /* test input */ };
      const expected = { /* expected output */ };

      const result = await component.methodName(input);

      expect(result).toEqual(expected);
    });

    test('should handle edge case', async () => {
      const input = { /* edge case input */ };

      await expect(component.methodName(input))
        .rejects.toThrow('Expected error message');
    });

    test('should handle async operations', async () => {
      const mockFunction = jest.fn().mockResolvedValue('mock result');
      component.setDependency(mockFunction);

      const result = await component.methodName({ test: 'input' });

      expect(mockFunction).toHaveBeenCalledWith({ test: 'input' });
      expect(result).toBe('mock result');
    });
  });
});
```

#### Model Selector Test Example

```typescript
// tests/unit/model-selector.test.ts
import { describe, test, expect, beforeEach } from '@jest/globals';
import { ModelSelector } from '../../src/model-selector.js';
import { ModelCapabilities, ModelSelectionCriteria } from '../../src/research-types.js';
import { mockModels } from '../fixtures/mock-models.js';

describe('ModelSelector', () => {
  let modelSelector: ModelSelector;

  beforeEach(() => {
    modelSelector = new ModelSelector();
  });

  describe('selectModels', () => {
    test('should select models based on complexity', async () => {
      const criteria: ModelSelectionCriteria = {
        complexity: 'medium',
        focus: 'technical',
        availableModels: mockModels,
        preferredCount: 3,
        requireDiversity: true,
        maxTimeout: 180000
      };

      const result = await modelSelector.selectModels(criteria);

      expect(result.primary).toBeDefined();
      expect(result.secondary).toBeDefined();
      expect(result.tertiary).toBeDefined();
      expect(result.primary.complexity).toContain('medium');
    });

    test('should prioritize focus-specific models', async () => {
      const criteria: ModelSelectionCriteria = {
        complexity: 'simple',
        focus: 'technical',
        availableModels: mockModels,
        preferredCount: 3,
        requireDiversity: false,
        maxTimeout: 90000
      };

      const result = await modelSelector.selectModels(criteria);

      // Should prefer models with coding specialization
      expect(
        result.primary.specializations.some(spec =>
          spec.includes('code') || spec.includes('technical')
        )
      ).toBe(true);
    });
  });

  describe('parseModelCapabilities', () => {
    test('should correctly parse model metadata', () => {
      const rawModel = {
        name: 'llama3.2:7b',
        size: 7365960704,
        modified_at: '2024-01-15T10:30:00Z'
      };

      const result = modelSelector.parseModelCapabilities([rawModel]);

      expect(result).toHaveLength(1);
      expect(result[0].name).toBe('llama3.2:7b');
      expect(result[0].parameters).toBe('7B');
      expect(result[0].tier.name).toBe('large');
    });
  });
});
```

### Integration Testing

#### MCP Server Integration Test

```typescript
// tests/integration/mcp-server.test.ts
import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { spawn, ChildProcess } from 'child_process';

describe('MCP Server Integration', () => {
  let serverProcess: ChildProcess;
  let client: Client;

  beforeAll(async () => {
    // Start MCP server process
    serverProcess = spawn('node', ['build/index.js'], {
      stdio: 'pipe'
    });

    // Initialize MCP client
    const transport = new StdioClientTransport({
      reader: serverProcess.stdout!,
      writer: serverProcess.stdin!
    });

    client = new Client(
      { name: 'test-client', version: '1.0.0' },
      { capabilities: {} }
    );

    await client.connect(transport);
  }, 30000);

  afterAll(async () => {
    await client.close();
    serverProcess.kill();
  });

  test('should list available tools', async () => {
    const tools = await client.listTools();

    expect(tools.tools).toContainEqual(
      expect.objectContaining({
        name: 'research'
      })
    );
  });

  test('should execute research tool', async () => {
    const result = await client.callTool('research', {
      question: 'What is TypeScript?',
      complexity: 'simple'
    });

    expect(result.content).toHaveProperty('analysis');
    expect(result.content.analysis).toHaveProperty('convergent_themes');
    expect(result.content.responses.length).toBeGreaterThan(0);
  });
});
```

### Performance Testing

#### Benchmark Template

```typescript
// tests/performance/research-performance.test.ts
import { describe, test, expect } from '@jest/globals';
import { ResearchTool } from '../../src/research-tool.js';

describe('Research Performance', () => {
  let researchTool: ResearchTool;

  beforeEach(() => {
    researchTool = new ResearchTool();
  });

  test('should complete simple research within time limits', async () => {
    const startTime = Date.now();

    const result = await researchTool.executeResearch({
      question: 'What is Docker?',
      complexity: 'simple'
    });

    const duration = Date.now() - startTime;

    expect(duration).toBeLessThan(90000); // 90 seconds max
    expect(result.performance.total_time).toBeLessThan(90000);
    expect(result.responses.length).toBeGreaterThan(0);
  }, 120000);

  test('should handle parallel execution efficiently', async () => {
    const sequentialStart = Date.now();
    await researchTool.executeResearch({
      question: 'Compare React vs Vue',
      complexity: 'medium',
      parallel: false
    });
    const sequentialTime = Date.now() - sequentialStart;

    const parallelStart = Date.now();
    await researchTool.executeResearch({
      question: 'Compare React vs Vue',
      complexity: 'medium',
      parallel: true
    });
    const parallelTime = Date.now() - parallelStart;

    // Parallel should be at least 20% faster
    expect(parallelTime).toBeLessThan(sequentialTime * 0.8);
  }, 300000);

  test('should maintain performance under load', async () => {
    const concurrentRequests = 5;
    const promises = Array(concurrentRequests).fill(null).map(() =>
      researchTool.executeResearch({
        question: 'What is machine learning?',
        complexity: 'simple'
      })
    );

    const startTime = Date.now();
    const results = await Promise.all(promises);
    const duration = Date.now() - startTime;

    // All requests should succeed
    expect(results).toHaveLength(concurrentRequests);
    results.forEach(result => {
      expect(result.performance.successful_responses).toBeGreaterThan(0);
    });

    // Should complete within reasonable time
    expect(duration).toBeLessThan(180000); // 3 minutes for 5 concurrent requests
  }, 240000);
});
```

## 🎯 Performance Optimization

### Profiling and Monitoring

#### Performance Monitoring Setup

```typescript
// src/performance-monitor.ts
export class PerformanceMonitor {
  private metrics: Map<string, number[]> = new Map();

  startTimer(operationName: string): () => number {
    const startTime = performance.now();

    return () => {
      const duration = performance.now() - startTime;
      this.recordMetric(operationName, duration);
      return duration;
    };
  }

  recordMetric(name: string, value: number): void {
    if (!this.metrics.has(name)) {
      this.metrics.set(name, []);
    }

    const values = this.metrics.get(name)!;
    values.push(value);

    // Keep only recent measurements (last 100)
    if (values.length > 100) {
      values.shift();
    }
  }

  getMetrics(name: string): {
    avg: number;
    min: number;
    max: number;
    p95: number;
  } {
    const values = this.metrics.get(name) || [];
    if (values.length === 0) {
      return { avg: 0, min: 0, max: 0, p95: 0 };
    }

    const sorted = [...values].sort((a, b) => a - b);
    const p95Index = Math.floor(sorted.length * 0.95);

    return {
      avg: values.reduce((sum, val) => sum + val, 0) / values.length,
      min: Math.min(...values),
      max: Math.max(...values),
      p95: sorted[p95Index]
    };
  }
}
```

#### Memory Usage Monitoring

```typescript
// src/memory-monitor.ts
export class MemoryMonitor {
  private static instance: MemoryMonitor;
  private intervalId?: NodeJS.Timeout;

  static getInstance(): MemoryMonitor {
    if (!MemoryMonitor.instance) {
      MemoryMonitor.instance = new MemoryMonitor();
    }
    return MemoryMonitor.instance;
  }

  startMonitoring(intervalMs = 30000): void {
    this.intervalId = setInterval(() => {
      const usage = process.memoryUsage();

      console.log('Memory Usage:', {
        rss: `${Math.round(usage.rss / 1024 / 1024)} MB`,
        heapUsed: `${Math.round(usage.heapUsed / 1024 / 1024)} MB`,
        heapTotal: `${Math.round(usage.heapTotal / 1024 / 1024)} MB`,
        external: `${Math.round(usage.external / 1024 / 1024)} MB`
      });

      // Alert if memory usage is too high
      if (usage.heapUsed > 512 * 1024 * 1024) { // 512 MB
        console.warn('High memory usage detected:', usage);
      }
    }, intervalMs);
  }

  stopMonitoring(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = undefined;
    }
  }
}
```

### Optimization Strategies

#### Response Caching

```typescript
// src/response-cache.ts
interface CacheEntry {
  result: ResearchResult;
  timestamp: number;
  ttl: number;
}

export class ResponseCache {
  private cache: Map<string, CacheEntry> = new Map();
  private readonly defaultTTL = 300000; // 5 minutes

  private generateKey(request: ResearchRequest): string {
    const { question, complexity, focus, models } = request;
    return JSON.stringify({
      question: question.toLowerCase().trim(),
      complexity,
      focus,
      models: models?.sort()
    });
  }

  get(request: ResearchRequest): ResearchResult | null {
    const key = this.generateKey(request);
    const entry = this.cache.get(key);

    if (!entry) return null;

    const now = Date.now();
    if (now - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      return null;
    }

    return entry.result;
  }

  set(request: ResearchRequest, result: ResearchResult, ttl = this.defaultTTL): void {
    const key = this.generateKey(request);
    this.cache.set(key, {
      result,
      timestamp: Date.now(),
      ttl
    });

    // Cleanup old entries periodically
    if (this.cache.size > 100) {
      this.cleanup();
    }
  }

  private cleanup(): void {
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > entry.ttl) {
        this.cache.delete(key);
      }
    }
  }
}
```

#### Connection Pooling

```typescript
// src/connection-pool.ts
import axios, { AxiosInstance } from 'axios';

export class ConnectionPool {
  private pools: Map<string, AxiosInstance> = new Map();

  getConnection(host: string): AxiosInstance {
    if (!this.pools.has(host)) {
      const instance = axios.create({
        baseURL: host,
        timeout: 60000,
        maxRedirects: 3,
        // Connection pooling settings
        httpsAgent: {
          keepAlive: true,
          maxSockets: 10,
          maxFreeSockets: 5
        }
      });

      // Add request/response interceptors for monitoring
      instance.interceptors.request.use(config => {
        config.metadata = { startTime: Date.now() };
        return config;
      });

      instance.interceptors.response.use(
        response => {
          const duration = Date.now() - response.config.metadata.startTime;
          console.log(`Request to ${response.config.url} took ${duration}ms`);
          return response;
        },
        error => {
          console.error(`Request failed:`, error.message);
          return Promise.reject(error);
        }
      );

      this.pools.set(host, instance);
    }

    return this.pools.get(host)!;
  }
}
```

## 🔍 Debugging and Troubleshooting

### Debug Configuration

#### Environment Variables

```bash
# Enable debug logging
DEBUG=mcp-ollama:*

# Verbose MCP protocol logging
MCP_DEBUG=true

# Ollama debugging
OLLAMA_DEBUG=true

# Performance monitoring
PERFORMANCE_MONITORING=true

# Memory monitoring
MEMORY_MONITORING=true
```

#### Debug Utilities

```typescript
// src/debug-utils.ts
export class DebugUtils {
  static logRequest(request: ResearchRequest): void {
    if (process.env.DEBUG?.includes('mcp-ollama')) {
      console.log('[DEBUG] Research Request:', {
        question: request.question.substring(0, 100) + '...',
        complexity: request.complexity,
        focus: request.focus,
        models: request.models,
        parallel: request.parallel
      });
    }
  }

  static logResponse(result: ResearchResult): void {
    if (process.env.DEBUG?.includes('mcp-ollama')) {
      console.log('[DEBUG] Research Result:', {
        modelsUsed: result.models_used,
        successfulResponses: result.performance.successful_responses,
        totalTime: result.performance.total_time,
        confidenceScore: result.analysis.confidence_score
      });
    }
  }

  static logError(error: Error, context?: any): void {
    console.error('[ERROR]', error.message);
    if (context) {
      console.error('[ERROR] Context:', context);
    }
    if (error.stack) {
      console.error('[ERROR] Stack:', error.stack);
    }
  }
}
```

### Common Issues and Solutions

#### Issue: Model Selection Failures

**Symptoms:**
- "No suitable models available" errors
- Poor model matches for complexity level

**Debugging:**
```typescript
// Add debugging to model selector
export class ModelSelector {
  async selectModels(criteria: ModelSelectionCriteria): Promise<SelectionStrategy> {
    console.log('[DEBUG] Selection criteria:', criteria);

    const availableModels = criteria.availableModels;
    console.log('[DEBUG] Available models:', availableModels.map(m => ({
      name: m.name,
      tier: m.tier.name,
      complexity: m.complexity
    })));

    // ... selection logic

    console.log('[DEBUG] Selected models:', selectedModels.map(m => m.name));
    return result;
  }
}
```

**Solutions:**
1. Ensure models are properly pulled in Ollama
2. Check model tier classification logic
3. Verify complexity level mappings

#### Issue: Performance Degradation

**Symptoms:**
- Slow response times
- High memory usage
- Timeout errors

**Debugging:**
```typescript
// Add performance monitoring
const monitor = new PerformanceMonitor();

export class ResearchTool {
  async executeResearch(request: ResearchRequest): Promise<ResearchResult> {
    const endTimer = monitor.startTimer('research-execution');

    try {
      const result = await this.doResearch(request);
      const duration = endTimer();

      console.log(`Research completed in ${duration}ms`);
      console.log('Performance metrics:', monitor.getMetrics('research-execution'));

      return result;
    } catch (error) {
      endTimer();
      throw error;
    }
  }
}
```

**Solutions:**
1. Enable response caching for repeated queries
2. Use parallel execution judiciously
3. Monitor memory usage and implement cleanup
4. Adjust timeout values based on model performance

#### Issue: Analysis Quality Problems

**Symptoms:**
- Low confidence scores
- Poor theme extraction
- Inconsistent recommendations

**Debugging:**
```typescript
// Add analysis debugging
export class ResponseAnalyzer {
  async analyzeResponses(/* ... */): Promise<ResearchResult> {
    console.log('[DEBUG] Analyzing responses:', responses.map(r => ({
      model: r.model,
      confidence: r.confidence,
      tokenCount: r.tokenCount,
      responseLength: r.response.length
    })));

    const themes = this.extractThemes(responses);
    console.log('[DEBUG] Extracted themes:', themes);

    const synthesis = await this.generateSynthesis(/* ... */);
    console.log('[DEBUG] Generated synthesis length:', synthesis.length);

    return result;
  }
}
```

**Solutions:**
1. Improve prompt formatting for clearer responses
2. Adjust confidence calculation algorithms
3. Enhance theme extraction logic
4. Add more sophisticated NLP processing

## 📦 Deployment and Distribution

### Build Process

```bash
# Production build
npm run build

# Verify build
node build/index.js --version

# Test build with MCP inspector
npm run inspector
```

### Docker Development

```dockerfile
# Dockerfile.dev
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Build
RUN npm run build

# Development command
CMD ["npm", "run", "watch"]
```

### Testing in Claude Desktop

1. **Build the project**
```bash
npm run build
```

2. **Update Claude Desktop config**
```json
{
  "mcpServers": {
    "ollama-dev": {
      "command": "node",
      "args": ["/path/to/mcp-ollama/build/index.js"],
      "env": {
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "DEBUG": "mcp-ollama:*"
      }
    }
  }
}
```

3. **Restart Claude Desktop**

4. **Test with research queries**

## 🤝 Contributing Guidelines

### Code Style

- Use **TypeScript** with strict typing
- Follow **ESLint** configuration
- Use **Prettier** for formatting
- Write **JSDoc** comments for public APIs
- Prefer **async/await** over Promises

### Commit Guidelines

```bash
# Format: <type>(<scope>): <subject>

feat(research): add sentiment analysis capability
fix(model-selector): handle edge case with no available models
docs(api): update research tool schema documentation
test(integration): add MCP server integration tests
perf(cache): implement response caching system
```

### Pull Request Process

1. **Create feature branch**
```bash
git checkout -b feature/sentiment-analysis
```

2. **Implement changes with tests**
```bash
npm test
npm run lint
```

3. **Update documentation**
```bash
# Update relevant docs in /docs
# Update README if needed
```

4. **Submit PR with description**
- Clear description of changes
- Link to related issues
- Include test coverage information
- Add breaking change notes if applicable

### Code Review Checklist

- [ ] Code follows TypeScript best practices
- [ ] All tests pass and coverage is maintained
- [ ] Documentation is updated
- [ ] Performance impact is considered
- [ ] Error handling is comprehensive
- [ ] Security implications are reviewed
- [ ] MCP protocol compliance is maintained

This development guide provides a comprehensive foundation for extending and maintaining the MCP Ollama Research Tool. The modular architecture ensures that new features can be added safely while maintaining system stability and performance.