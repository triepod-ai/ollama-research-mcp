# Research Tool User Guide

The Research Tool is the crown jewel of the MCP Ollama server - an intelligent multi-model research system that provides comparative analysis across multiple language models.

## 🚀 Quick Start

### Basic Usage
```json
{
  "tool": "research",
  "question": "What are the benefits of TypeScript over JavaScript?"
}
```

This will:
- Automatically select 3 optimal models based on the question complexity
- Execute queries in parallel or sequential mode (optimized automatically)
- Analyze responses for convergent themes and divergent perspectives
- Provide a synthesized recommendation with confidence scoring

### Advanced Usage
```json
{
  "tool": "research",
  "question": "How should we architect a distributed system for 1M+ users?",
  "complexity": "complex",
  "focus": "technical",
  "parallel": true,
  "include_metadata": true,
  "temperature": 0.7,
  "timeout": 180000
}
```

## 📊 Parameters Reference

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | string | The research question to analyze across multiple models |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `complexity` | string | `"medium"` | Query complexity: `"simple"`, `"medium"`, `"complex"` |
| `models` | string[] | auto-selected | Specific models to use (overrides automatic selection) |
| `focus` | string | `"general"` | Research focus: `"technical"`, `"business"`, `"ethical"`, `"creative"`, `"general"` |
| `parallel` | boolean | `false` | Execute queries in parallel (faster) vs sequential (resource-friendly) |
| `include_metadata` | boolean | `false` | Include model metadata in responses |
| `timeout` | number | complexity-based | Custom timeout in milliseconds |
| `temperature` | number | `0.7` | Creativity level (0.1-1.0) |

## 🎯 Complexity Levels

### Simple Complexity
- **Use for**: Basic questions, definitions, straightforward comparisons
- **Models selected**: Fast, efficient models (1B-7B parameters)
- **Timeout**: 30-90 seconds
- **Token limit**: ~500 tokens per response
- **Example**: "What is Docker?"

```json
{
  "tool": "research",
  "question": "What is the difference between REST and GraphQL?",
  "complexity": "simple"
}
```

### Medium Complexity (Default)
- **Use for**: Analysis questions, comparisons with multiple factors, technical explanations
- **Models selected**: Balanced selection of fast and capable models (7B-14B parameters)
- **Timeout**: 60-180 seconds
- **Token limit**: ~1500 tokens per response
- **Example**: "Compare React vs Vue for enterprise applications"

```json
{
  "tool": "research",
  "question": "What are the trade-offs between microservices and monolithic architecture?",
  "complexity": "medium",
  "focus": "technical"
}
```

### Complex Complexity
- **Use for**: Deep analysis, multi-faceted questions, strategic decisions, research synthesis
- **Models selected**: Larger, more capable models (13B+ parameters)
- **Timeout**: 120-300 seconds
- **Token limit**: ~3000 tokens per response
- **Example**: "Design a scalable ML infrastructure for a fintech startup"

```json
{
  "tool": "research",
  "question": "Analyze the long-term implications of AI on software engineering careers",
  "complexity": "complex",
  "focus": "business",
  "parallel": true
}
```

## 🎨 Focus Areas

### Technical Focus
- **Optimized for**: Code, architecture, technical decisions, engineering problems
- **Preferred models**: `codellama`, `qwen2.5-coder`, `deepseek-coder`, `starcoder`
- **Best for**: Architecture decisions, code reviews, technical comparisons

```json
{
  "tool": "research",
  "question": "How to implement distributed caching for high-throughput applications?",
  "focus": "technical",
  "complexity": "medium"
}
```

### Business Focus
- **Optimized for**: Strategy, market analysis, business decisions, ROI considerations
- **Preferred models**: `llama3.2`, `qwen2.5`, `mistral`, `gemma2`
- **Best for**: Technology adoption, business strategy, market analysis

```json
{
  "tool": "research",
  "question": "Should our company adopt Kubernetes or stick with Docker Swarm?",
  "focus": "business",
  "complexity": "medium"
}
```

### Ethical Focus
- **Optimized for**: Ethics, privacy, social impact, responsible AI
- **Preferred models**: `llama3.2`, `claude-3`, `mistral` (models with strong ethical training)
- **Best for**: AI ethics, privacy considerations, social impact analysis

```json
{
  "tool": "research",
  "question": "What are the ethical considerations of using AI for hiring decisions?",
  "focus": "ethical",
  "complexity": "complex"
}
```

### Creative Focus
- **Optimized for**: Innovation, creative solutions, brainstorming, design thinking
- **Preferred models**: `llama3.2`, `mistral-7b`, `qwen2.5`, `gemma2`
- **Best for**: Product ideation, creative problem solving, innovation strategies

```json
{
  "tool": "research",
  "question": "Generate innovative approaches to reduce cloud infrastructure costs",
  "focus": "creative",
  "temperature": 0.9
}
```

### General Focus (Default)
- **Optimized for**: Balanced analysis across multiple dimensions
- **Preferred models**: Well-rounded models suitable for various topics
- **Best for**: General research questions, broad analysis

## ⚡ Execution Modes

### Sequential Execution (Default)
- **Best for**: Resource-constrained environments, when models are already busy
- **Advantages**: Lower resource usage, predictable load
- **Disadvantages**: Slower overall execution time
- **Recommended**: Default for most use cases

### Parallel Execution
- **Best for**: Fast results, when system resources are available
- **Advantages**: Faster overall execution, better for time-sensitive research
- **Disadvantages**: Higher resource usage, potential model contention
- **Enable with**: `"parallel": true`

```json
{
  "tool": "research",
  "question": "Urgent: Compare cloud providers for our migration project",
  "parallel": true,
  "complexity": "medium"
}
```

## 📈 Understanding Results

### Response Structure
```json
{
  "question": "Your research question",
  "focus": "technical",
  "complexity": "medium",
  "timestamp": "2024-01-15T10:30:00Z",
  "models_used": ["llama3.2:7b", "qwen2.5-coder:7b", "mistral:7b"],
  "responses": [
    {
      "model": "llama3.2:7b",
      "response": "Model's detailed response...",
      "responseTime": 5432,
      "tokenCount": 342,
      "confidence": 0.85,
      "metadata": { /* if include_metadata: true */ }
    }
  ],
  "analysis": {
    "convergent_themes": [
      "All models agree that scalability is crucial",
      "Security considerations are paramount"
    ],
    "divergent_perspectives": [
      "Model A prefers microservices, Model B suggests modular monolith",
      "Different opinions on database sharding strategies"
    ],
    "reasoning_styles": [
      {
        "model": "llama3.2:7b",
        "style": "analytical",
        "characteristics": ["systematic", "evidence-based"],
        "depth": "moderate",
        "confidence": 0.87
      }
    ],
    "synthesis": "Comprehensive synthesis combining all perspectives...",
    "recommendations": [
      "Start with modular monolith for faster initial development",
      "Plan microservices migration path for future scaling"
    ],
    "confidence_score": 0.82
  },
  "performance": {
    "total_time": 12547,
    "successful_responses": 3,
    "failed_responses": 0,
    "average_response_time": 4182
  }
}
```

### Key Insights

#### Convergent Themes
- Points where **multiple models agree**
- High confidence recommendations
- Likely to be reliable insights

#### Divergent Perspectives
- Areas where **models disagree** or provide different angles
- Indicates nuanced topics requiring human judgment
- Valuable for comprehensive understanding

#### Reasoning Styles
- **Analytical**: Systematic, evidence-based approach
- **Creative**: Innovative, out-of-the-box thinking
- **Practical**: Focus on implementation and real-world constraints
- **Theoretical**: Deep conceptual analysis
- **Balanced**: Well-rounded approach across dimensions

#### Synthesis
- AI-generated summary combining all perspectives
- Balances convergent themes with divergent viewpoints
- Provides unified understanding of the topic

#### Recommendations
- Actionable next steps based on the analysis
- Prioritized by confidence and practical impact
- Consider both immediate and long-term implications

## 🛠️ Best Practices

### Asking Better Research Questions

#### ✅ Good Questions
- **Specific**: "How should we implement authentication for a multi-tenant SaaS application?"
- **Actionable**: "What database should we choose for our real-time analytics dashboard?"
- **Context-rich**: "Given our team size of 5 developers, should we use Next.js or separate React/Node.js?"

#### ❌ Avoid These Questions
- Too broad: "What's the best programming language?" (add context: "for web development", "for our startup")
- Yes/No questions: "Should we use Docker?" (ask "What are the pros and cons of Docker for our use case?")
- Outdated context: Include timeframe and current context

### Parameter Optimization

#### For Speed
```json
{
  "complexity": "simple",
  "parallel": true,
  "models": ["llama3.2:1b", "qwen2.5:3b"]  // Specify fast models
}
```

#### For Quality
```json
{
  "complexity": "complex",
  "include_metadata": true,
  "temperature": 0.3,  // Lower temperature for more focused responses
  "timeout": 300000    // Allow more time for thorough analysis
}
```

#### For Specific Expertise
```json
{
  "models": ["qwen2.5-coder:7b", "deepseek-coder:6.7b", "codellama:7b"],
  "focus": "technical"
}
```

### Interpreting Confidence Scores

- **0.9-1.0**: Very high confidence - likely reliable
- **0.7-0.9**: High confidence - generally trustworthy
- **0.5-0.7**: Medium confidence - verify independently
- **0.3-0.5**: Low confidence - use with caution
- **0.0-0.3**: Very low confidence - may be unreliable

### Common Patterns

#### Architecture Decisions
```json
{
  "question": "Should we use event-driven architecture for our e-commerce platform?",
  "complexity": "complex",
  "focus": "technical",
  "parallel": true
}
```

#### Technology Evaluation
```json
{
  "question": "Compare Tailwind CSS vs Styled Components for our design system",
  "complexity": "medium",
  "focus": "technical",
  "temperature": 0.4  // Lower temperature for objective comparison
}
```

#### Business Strategy
```json
{
  "question": "What are the risks and benefits of migrating to cloud-native architecture?",
  "complexity": "complex",
  "focus": "business",
  "include_metadata": true
}
```

## 🚨 Troubleshooting

### Common Issues

#### "No suitable models available"
- **Cause**: No models match the requested complexity level
- **Solution**: Lower complexity level or ensure you have appropriate models installed
- **Prevention**: Run `list` tool first to check available models

#### Timeout Errors
- **Cause**: Models taking longer than expected
- **Solution**: Increase timeout parameter or use simpler complexity
- **Prevention**: Start with "simple" complexity for new topics

#### Low Confidence Scores
- **Cause**: Models uncertain or question ambiguous
- **Solution**: Refine question with more context and specificity
- **Prevention**: Follow best practices for question formulation

#### Inconsistent Results
- **Cause**: Non-deterministic behavior with high temperature
- **Solution**: Lower temperature (0.3-0.5) for more consistent results
- **Prevention**: Use appropriate temperature for your use case

### Performance Optimization

#### For Large-Scale Usage
1. **Use appropriate complexity levels** - don't over-engineer simple questions
2. **Enable parallel execution** when system resources allow
3. **Specify models explicitly** to avoid selection overhead for repeated similar queries
4. **Cache results** for frequently asked questions (implement externally)

#### For Resource-Constrained Environments
1. **Use sequential execution** (default)
2. **Prefer "simple" complexity** when possible
3. **Specify fast models** (1B-3B parameters)
4. **Set conservative timeouts**

## 🔗 Integration Examples

### With Claude Desktop
The research tool integrates seamlessly with Claude Desktop. Simply use the tool syntax in your conversation:

```
I need to research database options for my new project. Can you use the research tool to analyze PostgreSQL vs MongoDB for a content management system?
```

Claude will automatically format and execute:
```json
{
  "tool": "research",
  "question": "Compare PostgreSQL vs MongoDB for a content management system",
  "complexity": "medium",
  "focus": "technical"
}
```

### Programmatic Usage
For automated research workflows, you can integrate the MCP server programmatically using the MCP SDK.

## 📚 Advanced Topics

### Model Selection Algorithm
The research tool uses a sophisticated algorithm that considers:
- **Model capabilities** vs **question complexity**
- **Performance history** and **response times**
- **Specialization match** with focus area
- **Diversity requirements** for comprehensive analysis

### Response Analysis Pipeline
1. **Quality Assessment**: Evaluates response coherence and relevance
2. **Confidence Calculation**: Multi-factor scoring based on content quality
3. **Theme Extraction**: NLP-based identification of key themes
4. **Perspective Analysis**: Comparison across model responses
5. **Synthesis Generation**: AI-powered combination of insights

### Performance Monitoring
The tool continuously learns and optimizes by:
- Tracking model performance and reliability
- Updating selection preferences based on success rates
- Optimizing timeout values based on actual response times
- Learning from confidence score accuracy

## 🤝 Contributing

If you'd like to contribute to the research tool:

1. **Add new focus areas** by updating `FOCUS_PREFERENCES` in `research-types.ts`
2. **Improve model selection** logic in `model-selector.ts`
3. **Enhance analysis algorithms** in `response-analyzer.ts`
4. **Add performance optimizations** in `performance-config.ts`

See our [Contributing Guide](../CONTRIBUTING.md) for detailed instructions.