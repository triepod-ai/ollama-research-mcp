# Ollama MCP Tool Selection Decision Tree

## Quick Decision Guide

```
What do you need?
│
├─ See available models? → `list`
│   └─ Then: Check model details → `show`
│
├─ Single response/output?
│   ├─ Code generation? → `run` (with qwen2.5-coder)
│   ├─ Analysis task? → `run` (90-120s timeout)
│   └─ Clean output needed? → `run`
│
├─ Conversation/dialogue?
│   ├─ Using qwen2.5-coder? → ⚠️ Use `run` instead (template bug)
│   ├─ Need context retention? → `chat_completion`
│   └─ Iterative refinement? → `chat_completion`
│
├─ Download new model? → `pull`
├─ Create custom model? → `create`
├─ Start Ollama server? → `serve`
└─ Upload model? → `push`
```

## Detailed Decision Logic

### STEP 1: What's your primary goal?

#### Information Gathering
- **List models** → `list`
- **Model details** → `show`
- **Check server** → `serve`

#### Content Generation
- **Single output** → `run`
- **Conversation** → `chat_completion` (check warnings)
- **Code specifically** → `run` (always)

#### Model Management
- **Download** → `pull`
- **Create** → `create`
- **Upload** → `push`
- **Copy** → `cp`
- **Delete** → `rm`

### STEP 2: Which model are you using?

#### llama3.2:1b
- ✅ `chat_completion` - Fast, reliable
- ✅ `run` - Clean output
- **Response time**: 2-3s
- **Best for**: Quick tasks

#### qwen2.5-coder:7b-instruct
- ❌ `chat_completion` - Template token issues
- ✅ `run` - Works perfectly
- **Response time**: 5-8s
- **Best for**: Code generation

#### dolphin-mistral:7b
- ✅ `chat_completion` - Good for conversations
- ✅ `run` - Clean output
- **Response time**: 4-5s
- **Best for**: General purpose

#### smallthinker:latest
- ⚠️ Both tools - Very slow, timeouts common
- **Response time**: >120s
- **Recommendation**: Avoid or use 180s timeout

### STEP 3: What output format do you need?

#### Clean, Direct Text
→ Use `run`
- Returns only model output
- No JSON wrapper
- No extra explanations

#### Structured JSON Response
→ Use `chat_completion`
- Returns choices array
- Includes metadata
- May add explanations

#### Code Without Artifacts
→ Use `run`
- No template tokens
- Clean code output
- Proper formatting

### STEP 4: Parameter Optimization

#### For Code Tasks
```javascript
tool: "run"
model: "qwen2.5-coder:7b-instruct"
temperature: 0.1-0.3
timeout: 90000
max_tokens: 1000
```

#### For Conversations
```javascript
tool: "chat_completion"
model: "llama3.2:1b"
temperature: 0.5-0.7
timeout: 60000
messages: [/* conversation history */]
```

#### For Analysis
```javascript
tool: "run"
model: "dolphin-mistral:7b"
temperature: 0.2-0.4
timeout: 120000
system: "You are an analyst..."
```

#### For Creative Writing
```javascript
tool: "run"  // for clean output
model: "llama3.2:1b"
temperature: 0.8-1.2
timeout: 60000
```

## Common Scenarios

### "I want to generate code"
1. Use `run` (not chat_completion)
2. Model: qwen2.5-coder:7b-instruct
3. Temperature: 0.1-0.3
4. Timeout: 90000ms

### "I want a chatbot"
1. Use `chat_completion`
2. Model: llama3.2:1b or dolphin-mistral
3. Include conversation history
4. Avoid qwen2.5-coder (template issues)

### "I want to analyze text"
1. Use `run` for single analysis
2. Use `chat_completion` for iterative analysis
3. Timeout: 120000ms for complex analysis
4. Temperature: 0.2-0.4

### "I'm getting weird symbols (<|im_start|>)"
- **Problem**: Template tokens from chat_completion
- **Solution**: Switch to `run` tool
- **Most common with**: qwen2.5-coder

### "My request times out"
- **Check model**: smallthinker is very slow
- **Increase timeout**: Up to 180000ms
- **Consider**: Switching to faster model

### "I need context retention"
- **Use**: `chat_completion`
- **Include**: Previous messages in array
- **Avoid**: Very long conversations (performance degrades)

## Tool Selection Matrix

| Use Case | Tool | Model | Timeout | Notes |
|----------|------|-------|---------|-------|
| Code generation | `run` | qwen2.5-coder | 90s | Never use chat_completion |
| Quick chat | `chat_completion` | llama3.2:1b | 60s | Fast and reliable |
| Analysis | `run` | dolphin-mistral | 120s | Clean output |
| Creative | `run` | llama3.2:1b | 60s | High temperature |
| Dialogue | `chat_completion` | dolphin-mistral | 60s | Good context retention |
| Debug conversation | `chat_completion` | llama3.2:1b | 60s | Step-by-step |

## Red Flags to Avoid

🚫 **DON'T** use chat_completion with qwen2.5-coder
🚫 **DON'T** use smallthinker unless necessary
🚫 **DON'T** send empty inputs
🚫 **DON'T** use very low max_tokens (<50)
🚫 **DON'T** forget to increase timeout for analysis

## Green Flags for Success

✅ **DO** use run for code generation
✅ **DO** use chat_completion for conversations
✅ **DO** check model compatibility first
✅ **DO** set appropriate timeouts
✅ **DO** use low temperature for deterministic tasks