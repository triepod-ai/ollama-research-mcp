/**
 * Proposed Tool Description Updates Based on Testing Insights
 *
 * Key improvements:
 * 1. Decision-first guidance (WHEN to use, not just WHAT it does)
 * 2. Known issue warnings (template tokens, timeouts)
 * 3. Model compatibility matrix
 * 4. Prescriptive parameter recommendations
 * 5. Performance expectations
 */

export const PROPOSED_TOOL_UPDATES = {
  // Primary usage tools
  run: {
    name: 'run',
    description: `PREFERRED for single responses, code generation, clean output. Returns plain text without artifacts.
Best for: Code (qwen2.5-coder, 90s timeout), analysis (120s timeout), creative writing (high temp).
Why use: No template tokens, no JSON wrapper, no extra explanations.
Models: ALL work well, especially qwen2.5-coder for code.
Faster than chat_completion, more reliable output.`,

    parameters: {
      name: {
        description: "Model name (qwen2.5-coder for code, llama3.2:1b for speed)"
      },
      prompt: {
        description: "Your prompt text (single request, not conversation)"
      },
      temperature: {
        description: "0.1-0.3 for code/facts (deterministic), 0.7-1.0 for creative (varied), 1.5+ experimental"
      },
      timeout: {
        description: "60000ms default, 90000ms for code, 120000ms for analysis, 180000ms for slow models"
      },
      system: {
        description: "Optional behavior instruction (e.g., 'You are a Python expert')"
      }
    }
  },

  chat_completion: {
    name: 'chat_completion',
    description: `Multi-turn conversations with context retention. Returns JSON with choices array.
⚠️ KNOWN ISSUE: qwen2.5-coder returns template tokens (<|im_start|>) - use 'run' instead for this model.
Best for: Dialogues, iterative refinement, context-aware responses.
Works well: llama3.2:1b (2-3s), dolphin-mistral (4-5s).
Avoid: smallthinker (>120s timeouts), empty inputs (causes hallucination).
Note: Adds explanations to responses - use 'run' for clean output.`,

    parameters: {
      model: {
        description: "Model name (avoid qwen2.5-coder due to template tokens, use llama3.2:1b for speed)"
      },
      messages: {
        description: "Conversation array [{role: 'user'|'assistant'|'system', content: 'text'}]. Keep focused for performance."
      },
      temperature: {
        description: "0.1-0.3 for consistent responses, 0.5-0.7 for balanced, 1.0+ for creative variety"
      },
      max_tokens: {
        description: "Response limit: 50-200 short answers, 500-1000 code, 2000+ analysis. Too low cuts mid-sentence."
      },
      timeout: {
        description: "60000ms for quick chat, 90000ms for complex, 180000ms for smallthinker"
      }
    }
  },

  // Discovery tools
  list: {
    name: 'list',
    description: `START HERE - See all available models with sizes and dates.
Quick models: llama3.2:1b (1.2GB, 2-3s), dolphin-mistral (3.8GB, 4-5s).
Code model: qwen2.5-coder:7b (4.4GB, use with 'run' only).
Slow model: smallthinker (3.4GB, >120s - avoid if possible).
Next step: Use 'show' for details, then 'run' or 'chat_completion'.`
  },

  show: {
    name: 'show',
    description: `Get model details: context window (CRITICAL for prompt size), parameters, architecture.
Check before using: Template format (affects chat_completion), quantization (affects quality).
Important info: Context length for max prompt size, parameter count for capabilities.
Use after 'list', before choosing 'run' vs 'chat_completion'.`
  },

  // Model management tools
  pull: {
    name: 'pull',
    description: `Download model from registry. Popular choices:
Fast: llama3.2:1b (1GB, general purpose)
Code: qwen2.5-coder:7b-instruct (5GB, use with 'run')
Balanced: dolphin-mistral:7b (4GB, good for chat)
Check space before downloading large models.`
  },

  create: {
    name: 'create',
    description: `Create custom model from Modelfile. Define system prompts and parameters.
Format: FROM base_model\\nSYSTEM "custom instructions"\\nPARAMETER temperature 0.7
Use for: Specialized behaviors, preset configurations, fine-tuned responses.`
  },

  serve: {
    name: 'serve',
    description: `Start Ollama server (usually auto-starts on Windows). Default port: 11434.
Run if getting connection errors. Check with 'list' after starting.
For WSL/Docker: May need special host configuration.`
  },

  push: {
    name: 'push',
    description: `Upload custom model to registry. Requires Ollama account.
Format: namespace/modelname:tag (e.g., myusername/mymodel:latest).
Use after 'create' to share custom models.`
  },

  cp: {
    name: 'cp',
    description: `Copy model with new name. Useful for backups before modifications.
Example: Copy before experimenting with custom Modelfile changes.`
  },

  rm: {
    name: 'rm',
    description: `Delete local model to free disk space. Cannot be undone.
Check with 'list' first. Must re-download with 'pull' to use again.`
  }
};

// Helper function to generate warnings dynamically
export function getContextualWarnings(toolName: string, model?: string): string[] {
  const warnings: string[] = [];

  if (toolName === 'chat_completion') {
    if (model?.includes('qwen2.5-coder')) {
      warnings.push('⚠️ This model returns template tokens in chat_completion - use run instead');
    }
    if (model?.includes('smallthinker')) {
      warnings.push('⚠️ This model is very slow (>120s) - consider using a faster model');
    }
  }

  return warnings;
}

// Prescriptive parameter recommendations
export const PARAMETER_PRESETS = {
  code_generation: {
    tool: 'run',
    model: 'qwen2.5-coder:7b-instruct',
    temperature: 0.2,
    timeout: 90000,
    description: 'Optimized for code generation'
  },

  quick_chat: {
    tool: 'chat_completion',
    model: 'llama3.2:1b',
    temperature: 0.7,
    timeout: 60000,
    max_tokens: 500,
    description: 'Fast conversational responses'
  },

  analysis: {
    tool: 'run',
    model: 'dolphin-mistral:7b',
    temperature: 0.3,
    timeout: 120000,
    description: 'Deep analysis and reasoning'
  },

  creative_writing: {
    tool: 'run',
    model: 'llama3.2:1b',
    temperature: 1.0,
    timeout: 60000,
    description: 'Creative and varied output'
  }
};

// Model compatibility matrix
export const MODEL_COMPATIBILITY = {
  'llama3.2:1b': {
    run: 'excellent',
    chat_completion: 'excellent',
    speed: 'fast',
    response_time: '2-3s',
    best_for: ['quick tasks', 'general purpose', 'conversations']
  },

  'qwen2.5-coder:7b-instruct': {
    run: 'excellent',
    chat_completion: 'broken', // template tokens issue
    speed: 'medium',
    response_time: '5-8s',
    best_for: ['code generation', 'technical tasks'],
    warning: 'Use run only - chat_completion returns template tokens'
  },

  'dolphin-mistral:7b': {
    run: 'excellent',
    chat_completion: 'good',
    speed: 'medium',
    response_time: '4-5s',
    best_for: ['general purpose', 'analysis', 'conversations']
  },

  'smallthinker:latest': {
    run: 'slow',
    chat_completion: 'slow',
    speed: 'very slow',
    response_time: '>120s',
    best_for: ['complex reasoning if you can wait'],
    warning: 'Extremely slow - consider alternatives'
  }
};

// Decision helper function
export function recommendTool(useCase: string): {tool: string, reason: string} {
  const recommendations: Record<string, {tool: string, reason: string}> = {
    'code': {
      tool: 'run',
      reason: 'Clean output without template tokens, especially for qwen2.5-coder'
    },
    'conversation': {
      tool: 'chat_completion',
      reason: 'Maintains context across turns (but avoid qwen2.5-coder)'
    },
    'single_response': {
      tool: 'run',
      reason: 'Faster and cleaner output without JSON wrapper'
    },
    'analysis': {
      tool: 'run',
      reason: 'Direct output without extra explanations'
    },
    'iterative': {
      tool: 'chat_completion',
      reason: 'Can refine responses based on feedback'
    }
  };

  return recommendations[useCase] || {
    tool: 'run',
    reason: 'Default recommendation for clean, reliable output'
  };
}