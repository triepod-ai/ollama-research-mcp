# Tool Description Optimization Brainstorm

## Current State Analysis

### Problems with Current Descriptions
1. **Too Generic**: "Conversational API" doesn't tell users WHEN to use it
2. **Hidden Issues**: Template token bug not mentioned upfront
3. **No Decision Guidance**: Users must guess which tool fits their need
4. **Missing Context**: Model compatibility not addressed
5. **Vague Parameters**: "timeout in milliseconds" without recommendations

## Brainstormed Enhancement Strategies

### 1. Decision-First Descriptions
Instead of describing WHAT the tool does, lead with WHEN to use it:

**Current**: "Conversational API for dialogue and iterative refinement"
**Proposed**: "Use for: Multi-turn chats, context retention, iterative editing. Avoid for: qwen2.5-coder (template bug), single responses (use run instead)"

### 2. Traffic Light System
Add visual/textual indicators for tool reliability:

```typescript
description: "🟢 RELIABLE: chat_completion - Multi-turn conversations
🟡 CAUTION: Template tokens with qwen2.5-coder
🔴 AVOID: With smallthinker (timeouts)"
```

### 3. Prescriptive Workflow Patterns
Embed the optimal workflow directly in descriptions:

```typescript
description: "Step 1: Use 'list' to check models
Step 2: Use 'show' for context window size
Step 3: Use THIS for conversations
(For single responses, use 'run' instead)"
```

### 4. Model Compatibility Matrix
Include compatibility directly in description:

```typescript
description: "chat_completion - Conversations & iteration
✅ Works well: llama3.2, dolphin-mistral
⚠️ Issues: qwen2.5-coder (template tokens)
❌ Avoid: smallthinker (timeouts)"
```

### 5. Smart Parameter Hints
Replace generic parameter descriptions with prescriptive guidance:

**Current**: "timeout: Timeout in milliseconds"
**Proposed**: "timeout: Default 60s. Set 90s for code, 120s for analysis, 180s for smallthinker"

### 6. Use Case Routing
Structure descriptions as decision trees:

```typescript
description: "Need conversation? → Use this
Need clean output? → Use 'run'
Need code generation? → Use 'run' with qwen2.5-coder
Need quick response? → Use this with llama3.2:1b"
```

### 7. Anti-Pattern Warnings
Explicitly state what NOT to do:

```typescript
description: "chat_completion - Multi-turn conversations
⚠️ DON'T use for: Code with qwen2.5-coder, Single responses, Empty inputs
✅ DO use for: Chats, Context retention, Iterative refinement"
```

### 8. Performance Expectations
Set clear performance expectations:

```typescript
description: "chat_completion (2-8s typical)
Fast: llama3.2 (2-3s)
Medium: dolphin-mistral (4-5s)
Slow: qwen2.5-coder (5-8s)
Avoid: smallthinker (>120s)"
```

### 9. Example-Driven Descriptions
Include inline examples:

```typescript
description: "chat_completion - For conversations like:
'What's your name?' → 'I'm Claude' → 'Nice to meet you'
NOT for: 'Generate code' (use run for clean output)"
```

### 10. Contextual Intelligence
Descriptions that adapt based on common patterns:

```typescript
description: "chat_completion - Conversations & context
💡 TIP: Getting template tokens? Switch to 'run'
💡 TIP: Need code? Use 'run' with qwen2.5-coder
💡 TIP: Timeout? Increase to 120000ms"
```

## Proposed Implementation Approach

### Phase 1: Critical Warnings
Add immediate warnings for known issues:
- Template token bug with qwen2.5-coder
- Timeout issues with smallthinker
- Empty input behavior

### Phase 2: Decision Guidance
Add clear use case routing:
- When to use chat_completion vs run
- Model selection guidance
- Parameter recommendations

### Phase 3: Performance Optimization
Include performance hints:
- Response time expectations
- Timeout recommendations
- Model-specific optimizations

### Phase 4: Workflow Integration
Embed workflow patterns:
- list → show → run/chat_completion
- Fallback strategies
- Error recovery paths

## Specific Description Proposals

### run Tool
```typescript
description: "PREFERRED for: Single responses, code generation, clean output
Fastest path for: Analysis (90s timeout), code (qwen2.5-coder), creative writing
Returns: Plain text without formatting artifacts
Choose this when: You need ONE clean response without conversation"
```

### chat_completion Tool
```typescript
description: "BEST for: Multi-turn conversations with context retention
⚠️ WARNING: qwen2.5-coder returns template tokens - use 'run' instead
Works well: llama3.2 (2-3s), dolphin-mistral (4-5s)
Avoid: smallthinker (timeouts), empty inputs (hallucination risk)
Returns: JSON with choices array - may include extra explanations"
```

### list Tool
```typescript
description: "START HERE: See available models with sizes and modification dates
Next steps: Use 'show' for details, then 'run' or 'chat_completion'
Quick models: llama3.2:1b (1.2GB), dolphin-mistral (3.8GB)
Code model: qwen2.5-coder:7b-instruct (use with 'run' only)"
```

### show Tool
```typescript
description: "CRITICAL INFO: Get context window, parameters, template format
Why this matters: Context window affects prompt size limits
Check before using: chat_completion compatibility, streaming support
Key info: architecture, quantization, parameter count"
```

## Parameter Description Enhancements

### temperature
**Current**: "Creativity level: 0-2"
**Proposed**: "0.1-0.3 for code/facts (deterministic), 0.7-1.0 for creative/varied, 1.5+ experimental (may be incoherent)"

### timeout
**Current**: "Timeout in milliseconds"
**Proposed**: "60000 (1min) default - quick tasks, 90000 for code analysis, 120000 for complex prompts, 180000 for slow models like smallthinker"

### max_tokens
**Current**: "Maximum tokens to generate"
**Proposed**: "50-200 for short answers, 500-1000 for code, 2000+ for analysis. Note: May cut mid-sentence if too low"

### messages
**Current**: "Conversation history array"
**Proposed**: "Array of {role, content}. Include system message for behavior. Keep conversation focused - long contexts slow responses"

## Testing-Driven Improvements

Based on our testing, prioritize these changes:

1. **Immediate**: Warn about qwen2.5-coder template tokens in chat_completion
2. **High Priority**: Add "use run for code generation" guidance
3. **Medium Priority**: Include model-specific performance times
4. **Low Priority**: Add creative examples and use cases

## Success Metrics

How we'll know if descriptions are improved:
- Fewer failed attempts due to wrong tool selection
- Reduced template token issues
- Better timeout configuration (fewer timeouts)
- More appropriate model selection
- Cleaner output when needed

## Next Steps

1. Prioritize which improvements to implement first
2. Test new descriptions with example queries
3. Measure if tool selection improves
4. Iterate based on usage patterns
5. Consider dynamic descriptions based on user's model availability