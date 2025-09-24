# Ollama MCP Agent Training Guide

## Core Principle: Parameter-Based Decision Making

Instead of memorizing specific model names, understand the relationships between model characteristics and performance.

## Model Selection Framework

### 1. Understanding Model Characteristics

**Parameter Count** (The primary indicator):
- **1-3B parameters**: Ultra-fast responses (2-4s), basic capabilities
- **7-13B parameters**: Balanced performance (4-8s), good general purpose
- **20-40B parameters**: High quality (8-15s), advanced reasoning
- **70B+ parameters**: Maximum capability (15-30s+), research-grade output

**Quantization** (Quality vs Size trade-off):
- **Q4_0**: Standard 4-bit quantization, good balance
- **Q5_K_M**: Better quality, slightly larger
- **Q8_0**: Near full quality, much larger
- **F16**: Full precision, maximum quality and size

**Context Window** (How much text can be processed):
- **4K-8K**: Basic conversations and queries
- **32K**: Extended conversations, moderate documents
- **128K+**: Large documents, extensive context retention

### 2. Parameter Optimization Strategy

#### Timeout Configuration
```
Formula: timeout = base_time + (param_billions × scaling_factor) + complexity_adjustment

Where:
- base_time = 30000ms (30s)
- scaling_factor = 2000ms per billion parameters
- complexity_adjustment = 0-60000ms based on task

Examples:
- 7B model, simple task: 30s + (7 × 2s) = 44s → use 60s
- 30B model, complex task: 30s + (30 × 2s) + 30s = 120s
- 120B model, analysis: 30s + (120 × 2s) + 60s = 330s → use 300s
```

#### Temperature Settings
```
Task Type → Temperature Range:
- Factual/Code: 0.0 - 0.3
- Technical Writing: 0.2 - 0.4
- General Q&A: 0.4 - 0.7
- Creative Writing: 0.7 - 1.2
- Brainstorming: 1.0 - 1.5
- Experimental: 1.5 - 2.0
```

#### Max Tokens Guidelines
```
Response Type → Token Count:
- Yes/No: 10-20
- Brief answer: 50-100
- Paragraph: 200-400
- Detailed explanation: 500-1000
- Essay/Analysis: 1500-3000
- Comprehensive report: 3000-10000

Rule of thumb: ~1.3 tokens per word
Safety margin: Use 50% of model's context for output
```

### 3. Model Discovery Workflow

Always follow this pattern:
1. **List** → See what's available locally
2. **Show** → Check specifications (params, context, template)
3. **Select** → Choose based on task requirements
4. **Configure** → Set parameters based on model size
5. **Execute** → Run with appropriate tool (run vs chat_completion)

### 4. Performance Indicators

**Cloud vs Local**:
- **0GB storage** = Cloud-hosted model (needs internet)
- **>0GB storage** = Local model (works offline)

**Speed Expectations**:
- Cloud models: Often faster despite size due to server hardware
- Local models: Speed inversely proportional to parameter count
- Quantization impact: Lower quantization = faster but lower quality

### 5. Common Patterns

#### Pattern: Speed Priority
```
Requirements: Fast response, basic accuracy
Selection: Smallest available model (1-7B)
Parameters: timeout=30s, temperature=0.3, max_tokens=500
```

#### Pattern: Quality Priority
```
Requirements: Best possible output, time not critical
Selection: Largest available model (30B+)
Parameters: timeout=180s, temperature=0.5, max_tokens=2000
```

#### Pattern: Balanced Approach
```
Requirements: Good quality, reasonable speed
Selection: Mid-range model (7-20B)
Parameters: timeout=90s, temperature=0.5, max_tokens=1000
```

### 6. Troubleshooting Guide

**Problem: Timeouts**
- Solution: Increase timeout by 50% or choose smaller model
- Formula: new_timeout = current_timeout × 1.5

**Problem: Template tokens in output**
- Solution: Use "run" instead of "chat_completion"
- Alternative: Check model template with "show" command

**Problem: Poor quality output**
- Solution: Try larger model or adjust temperature
- If too random: Lower temperature by 0.2
- If too repetitive: Raise temperature by 0.2

**Problem: Context exceeded**
- Solution: Check model's context with "show"
- Reduce prompt size or find model with larger context

### 7. Agent Implementation

When implementing an agent that uses Ollama:

```typescript
// Don't do this - too specific:
const MODEL_CONFIGS = {
  'llama3.2:1b': { timeout: 30000 },
  'dolphin-mistral:7b': { timeout: 60000 },
  // Hard to maintain as models change
}

// Do this - parameter-based:
function calculateTimeout(modelInfo) {
  const paramBillions = extractParamCount(modelInfo);
  const baseTimeout = 30000;
  const scalingFactor = 2000;
  return baseTimeout + (paramBillions * scalingFactor);
}

function selectTemperature(taskType) {
  const temperatureMap = {
    'code': 0.2,
    'factual': 0.3,
    'balanced': 0.5,
    'creative': 0.8,
    'experimental': 1.2
  };
  return temperatureMap[taskType] || 0.5;
}
```

### 8. Key Learning Points

1. **Model names change, principles don't**: Focus on understanding parameter relationships
2. **Size predicts speed**: Larger models = slower responses
3. **Context matters**: Check context window before long prompts
4. **Template awareness**: Some models have formatting quirks
5. **Adaptive configuration**: Let parameters guide timeout/temperature decisions
6. **Discovery first**: Always list/show before making assumptions

## Summary

Successful Ollama MCP usage isn't about knowing specific models—it's about understanding the relationships between model characteristics (parameters, quantization, context) and performance outcomes. This knowledge remains valid even as specific models come and go.

When in doubt:
1. List available models
2. Check their specifications
3. Apply the parameter-based formulas
4. Adjust based on results

This approach ensures your agent remains effective regardless of which models are available.