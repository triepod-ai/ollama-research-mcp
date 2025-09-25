# MCP Ollama Research Tool - Implementation Guide

## Overview

The MCP Ollama Research Tool extends your MCP server with intelligent multi-model research capabilities. It automatically selects optimal models, executes comparative analysis, and provides synthesized insights similar to your @agent-general-research-assistant methodology.

## Architecture Components

### 1. Model Selection Algorithm (`src/model-selector.ts`)

**Key Features:**
- **Dynamic Model Detection**: Automatically discovers available Ollama models and classifies their capabilities
- **Tier-Based Classification**: Fast (<7B), Large (7B-70B), Cloud (70B+) with complexity support mapping
- **Intelligent Selection**: Multi-factor scoring based on focus area, complexity requirements, and performance history
- **Fallback Strategy**: Robust fallback chains for graceful degradation

**Example Model Selection:**
```typescript
// Simple complexity - fast models prioritized
{ complexity: 'simple', focus: 'technical' }
→ [llama3.2:1b, qwen2.5-coder:3b, codellama:7b]

// Complex analysis - larger models prioritized
{ complexity: 'complex', focus: 'business' }
→ [qwen2.5:72b, llama3.2:70b, mistral:7b]
```

### 2. Response Analysis Engine (`src/response-analyzer.ts`)

**Advanced Analysis Capabilities:**
- **Convergent Theme Detection**: Identifies concepts mentioned by multiple models using keyword clustering
- **Divergence Analysis**: Finds contradictions, unique approaches, and emphasis differences
- **Reasoning Style Classification**: Analytical, creative, practical, theoretical, balanced
- **Evidence-Based Synthesis**: Generates comprehensive analysis with confidence scoring

**Analysis Workflow:**
```
Model Responses → Keyword Extraction → Theme Clustering →
Contradiction Detection → Style Analysis → Synthesis Generation
```

### 3. Research Orchestration (`src/research-tool.ts`)

**Execution Modes:**
- **Sequential**: Resource-friendly execution with better error handling
- **Parallel**: Faster results with concurrent model queries
- **Hybrid**: Adaptive execution based on system load and complexity

**Performance Optimizations:**
- Dynamic timeout calculation based on model tier and complexity
- Intelligent response confidence scoring
- Comprehensive error handling with detailed failure analysis

### 4. Performance Management (`src/performance-config.ts`)

**Resource Management:**
- **Complexity-Based Timeouts**: Simple (30s-90s), Medium (1m-3m), Complex (2m-10m)
- **Tier Multipliers**: Fast (1.0x), Large (1.8x), Cloud (2.5x)
- **Concurrency Control**: Adaptive limits based on complexity level
- **Caching Strategy**: TTL-based caching with complexity-aware expiration

## Usage Examples

### Basic Research Query
```json
{
  "question": "What are the key considerations for implementing microservices architecture?",
  "complexity": "medium",
  "focus": "technical"
}
```

### Advanced Research Configuration
```json
{
  "question": "How will AI impact business strategy in the next 5 years?",
  "complexity": "complex",
  "focus": "business",
  "models": ["qwen2.5:72b", "llama3.2:70b", "mistral:7b"],
  "parallel": true,
  "include_metadata": true,
  "temperature": 0.7
}
```

### Focus Area Optimization

**Technical Focus** → Prioritizes coding-specialized models (qwen2.5-coder, codellama)
**Business Focus** → Emphasizes instruction-following models (llama3.2, mistral)
**Ethical Focus** → Selects reasoning-capable models with balanced perspectives
**Creative Focus** → Favors models with creative writing capabilities

## Response Format

### Structured Research Result
```json
{
  "meta": {
    "version": "1.0.0",
    "timestamp": "2025-01-14T10:30:00Z",
    "query_id": "research_12345",
    "execution_mode": "sequential",
    "total_processing_time_ms": 45000
  },
  "query": {
    "question": "Research question",
    "complexity": "medium",
    "focus": "technical",
    "models_used": ["model1", "model2", "model3"]
  },
  "results": {
    "successful_responses": 3,
    "failed_responses": 0,
    "confidence_score": 0.87,
    "responses": [...]
  },
  "analysis": {
    "convergent_themes": ["theme1", "theme2"],
    "divergent_perspectives": ["perspective1"],
    "reasoning_styles": [...],
    "synthesis": "Comprehensive analysis...",
    "recommendations": ["rec1", "rec2"]
  },
  "quality": {
    "overall_score": 0.85,
    "confidence_assessment": "High confidence with good consensus"
  }
}
```

## Performance Characteristics

### Response Times by Complexity
- **Simple**: 2-15 seconds (optimized for fast models)
- **Medium**: 15-60 seconds (balanced model selection)
- **Complex**: 60-300 seconds (comprehensive analysis)

### Resource Requirements
- **Memory**: 100MB base + 50MB per concurrent model
- **CPU**: Scales with model size and parallel execution
- **Network**: Primarily local Ollama API calls

### Failure Handling
- **Model Unavailable**: Automatic fallback to next best model
- **Timeout**: Configurable per complexity level with graceful degradation
- **Partial Failure**: Continues with available responses, notes failures in results

## Integration Patterns

### Claude Desktop Integration
The research tool integrates seamlessly with your existing MCP Ollama server:

```json
// Claude Desktop usage
{
  "tool": "research",
  "arguments": {
    "question": "Your research question",
    "complexity": "medium",
    "focus": "technical"
  }
}
```

### Programmatic Usage
```typescript
const researchTool = new ResearchTool('http://127.0.0.1:11434');

const result = await researchTool.executeResearch({
  question: "What are the best practices for API design?",
  complexity: 'medium',
  focus: 'technical',
  parallel: false
});
```

## Model Tier Classifications

### Fast Tier (< 7B parameters)
- **Purpose**: Quick responses, simple queries
- **Examples**: llama3.2:1b, qwen2.5:3b
- **Timeout Multiplier**: 1.0x
- **Best For**: Simple complexity tasks, rapid prototyping

### Large Tier (7B - 70B parameters)
- **Purpose**: Balanced capability and performance
- **Examples**: qwen2.5:7b, llama3.2:7b, mistral:7b
- **Timeout Multiplier**: 1.8x
- **Best For**: Medium complexity analysis, general research

### Cloud Tier (70B+ parameters)
- **Purpose**: Maximum capability for complex analysis
- **Examples**: qwen2.5:72b, llama3.2:70b
- **Timeout Multiplier**: 2.5x
- **Best For**: Complex reasoning, comprehensive research

## Error Recovery Strategies

### Automatic Fallbacks
1. **Primary Model Fails** → Try secondary model from selection
2. **Multiple Failures** → Use fallback chain of reliable models
3. **Network Issues** → Implement exponential backoff retry
4. **Timeout** → Reduce complexity or switch to faster models

### Graceful Degradation
- **Partial Responses**: Analyze available responses, note limitations
- **Quality Indicators**: Adjust confidence scores based on success rate
- **User Feedback**: Provide detailed error information and suggestions

## Configuration Options

### Environment Variables
```bash
OLLAMA_HOST=http://127.0.0.1:11434  # Ollama API endpoint
RESEARCH_CACHE_TTL=600000           # Cache TTL in milliseconds
RESEARCH_MAX_RETRIES=3              # Maximum retry attempts
RESEARCH_DEFAULT_TIMEOUT=60000      # Default timeout per model
```

### Performance Tuning
- **Parallel Execution**: Enable for faster results with sufficient resources
- **Caching**: Enable result caching for repeated queries
- **Model Selection**: Fine-tune selection criteria for your use cases
- **Timeout Adjustment**: Optimize based on your model performance

## Best Practices

### Query Design
- **Be Specific**: Clear, focused questions yield better analysis
- **Appropriate Complexity**: Match complexity to question depth
- **Focus Selection**: Choose focus area to optimize model selection

### Performance Optimization
- **Use Caching**: Enable for repeated or similar queries
- **Sequential Mode**: Default for resource-constrained environments
- **Timeout Tuning**: Adjust based on your model performance characteristics

### Result Interpretation
- **Check Confidence**: Review confidence scores and quality indicators
- **Analyze Consensus**: High convergence indicates reliable insights
- **Consider Limitations**: Review failed responses and their impact

## Troubleshooting

### Common Issues
1. **No Models Found**: Ensure Ollama is running and models are pulled
2. **All Queries Timeout**: Reduce complexity or increase timeout limits
3. **Low Confidence Scores**: Try different models or rephrase the question
4. **Memory Issues**: Reduce parallel execution or use smaller models

### Debugging Tools
- **Health Check**: Use `healthCheck()` method to verify system status
- **Performance Metrics**: Monitor query load, cache hit rates, resource usage
- **Detailed Logging**: Enable verbose logging for troubleshooting

This research tool provides a comprehensive solution for multi-model analysis, combining intelligent model selection, advanced response analysis, and robust error handling to deliver high-quality research insights.