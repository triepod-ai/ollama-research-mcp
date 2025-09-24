# Tool Description Optimization Implementation Plan

## Executive Summary

Based on comprehensive testing and analysis, we've identified critical improvements needed for the MCP Ollama tool descriptions. The current descriptions fail to guide users to the correct tool for their use case, leading to frustration and suboptimal results.

## Key Problems Identified

1. **Template Token Bug**: qwen2.5-coder returns `<|im_start|>` tokens in chat_completion
2. **Tool Confusion**: Users don't know when to use run vs chat_completion
3. **Model Incompatibilities**: Some model/tool combinations don't work well
4. **Performance Issues**: Timeout and response time expectations not set
5. **Parameter Confusion**: Generic parameter descriptions without guidance

## Proposed Solutions Overview

### 1. Decision-First Descriptions
Replace "what it does" with "when to use it":
- **Current**: "Conversational API for dialogue"
- **Proposed**: "Use for: Multi-turn chats. Avoid: qwen2.5-coder (template bug)"

### 2. Warning System Integration
Add contextual warnings directly in descriptions:
- ⚠️ Template token issues
- 🚫 Model compatibility problems
- ⏱️ Performance expectations

### 3. Prescriptive Parameter Guidance
Replace generic hints with specific recommendations:
- **Current**: "timeout: Timeout in milliseconds"
- **Proposed**: "timeout: 60s default, 90s for code, 120s for analysis"

## Implementation Priority

### Phase 1: Critical Fixes (Immediate)
1. **Add template token warning** to chat_completion description
2. **Add model-specific guidance** for qwen2.5-coder
3. **Update parameter descriptions** with specific recommendations

### Phase 2: User Experience (Week 2)
1. **Implement decision-first descriptions** for all tools
2. **Add model compatibility matrix** to descriptions
3. **Include performance expectations** (response times)

### Phase 3: Advanced Features (Week 3)
1. **Create dynamic warnings** based on model selection
2. **Add workflow patterns** (list → show → run/chat)
3. **Include example use cases** in descriptions

## Detailed Implementation

### 1. Updated Tool Descriptions

#### run Tool
```typescript
description: `PREFERRED for single responses, code generation, clean output.
Best for: Code (qwen2.5-coder, 90s timeout), analysis (120s timeout), creative writing.
Returns: Plain text without artifacts or template tokens.
Models: ALL work well, especially qwen2.5-coder for code.
Choose this when you need ONE clean response without conversation.`
```

#### chat_completion Tool
```typescript
description: `Multi-turn conversations with context retention.
⚠️ WARNING: qwen2.5-coder returns template tokens - use 'run' instead.
Best for: Dialogues, iterative refinement, context-aware responses.
Works well: llama3.2:1b (2-3s), dolphin-mistral (4-5s).
Returns: JSON with choices array - may include extra explanations.`
```

### 2. Enhanced Parameter Descriptions

#### temperature
```typescript
description: "0.1-0.3 for code/facts (deterministic), 0.7-1.0 for creative (varied), 1.5+ experimental"
```

#### timeout
```typescript
description: "60000ms default, 90000ms for code analysis, 120000ms for complex tasks, 180000ms for slow models"
```

### 3. Model Compatibility Integration

Add model-specific guidance directly in tool descriptions:

```typescript
// In chat_completion tool
if (model === 'qwen2.5-coder') {
  warning = '⚠️ This model returns template tokens - use run tool instead';
}
if (model === 'smallthinker') {
  warning = '⚠️ Very slow model (>120s) - increase timeout or use alternatives';
}
```

## Code Changes Required

### 1. Update index.ts Tool Definitions
Replace existing descriptions with proposed versions:

```typescript
// In setupToolHandlers() function
{
  name: 'run',
  description: PROPOSED_TOOL_UPDATES.run.description,
  inputSchema: {
    // Updated parameter descriptions
    temperature: {
      description: PROPOSED_TOOL_UPDATES.run.parameters.temperature.description
    }
  }
}
```

### 2. Add Warning System
Create helper function for contextual warnings:

```typescript
function addContextualWarnings(toolName: string, description: string): string {
  const warnings = getWarningsForTool(toolName);
  return warnings.length > 0 ?
    `${description}\n\n⚠️ WARNINGS:\n${warnings.join('\n')}` :
    description;
}
```

### 3. Model Compatibility Check
Add runtime validation:

```typescript
function validateModelToolCombination(model: string, tool: string): string[] {
  const issues: string[] = [];
  if (tool === 'chat_completion' && model.includes('qwen2.5-coder')) {
    issues.push('Template token issue detected - consider using run tool instead');
  }
  return issues;
}
```

## Success Metrics

### Quantitative
- Reduce chat_completion + qwen2.5-coder usage by 80%
- Increase run tool usage for code generation by 50%
- Reduce timeout errors by 60%
- Improve appropriate model selection by 70%

### Qualitative
- Users report clearer tool selection guidance
- Fewer frustrated reports about template tokens
- More successful first attempts
- Better parameter configuration

## Testing Plan

### 1. A/B Testing
- Test original vs updated descriptions
- Measure success rate of first attempts
- Track tool selection patterns

### 2. User Journey Testing
- Simulate common use cases:
  - "I want to generate code"
  - "I want a conversation"
  - "I need analysis"
- Measure if users select optimal tools

### 3. Performance Testing
- Monitor timeout reduction
- Track response quality improvements
- Measure parameter optimization adoption

## Implementation Timeline

### Week 1
- [ ] Update run and chat_completion descriptions
- [ ] Add template token warnings
- [ ] Update parameter descriptions
- [ ] Test with qwen2.5-coder specifically

### Week 2
- [ ] Add model compatibility matrix
- [ ] Implement decision-first descriptions for all tools
- [ ] Add performance expectations
- [ ] Create user testing scenarios

### Week 3
- [ ] Implement dynamic warnings
- [ ] Add workflow guidance
- [ ] Include example use cases
- [ ] Full integration testing

## Risk Assessment

### Low Risk
- Description updates (easily reversible)
- Parameter description improvements
- Adding warnings

### Medium Risk
- Changing tool selection behavior
- User adaptation period
- Documentation synchronization

### Mitigation Strategies
- Gradual rollout
- A/B testing
- Feedback collection
- Easy rollback capability

## Next Steps

1. **Prioritize Phase 1 changes** for immediate implementation
2. **Create test scenarios** for validation
3. **Update descriptions** in index.ts
4. **Test with real use cases** to validate improvements
5. **Gather user feedback** on changes
6. **Iterate based on results**

## Conclusion

The proposed optimization transforms tool descriptions from generic documentation into prescriptive user guidance. By addressing the template token issue, providing model-specific recommendations, and offering clear decision criteria, users will achieve better results with fewer attempts.

The implementation focuses on immediate pain points while establishing a foundation for continued improvement based on usage data and user feedback.