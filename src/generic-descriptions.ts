// Generic, model-agnostic tool descriptions for MCP Ollama
// Focus on parameters and capabilities rather than specific models

export const genericToolDescriptions = {
  list: {
    description: 'List all locally available models with their specifications. Shows model names, sizes, modification dates, and quantization formats. Use this to discover what models are installed before running queries.',
  },

  show: {
    description: 'Get detailed specifications for any model including context window size, parameter count, quantization method, and template format. Essential for understanding model capabilities and limitations.',
  },

  run: {
    description: 'Execute a single prompt and get plain text response. Ideal for one-off queries, code generation, and analysis tasks. Returns clean output without JSON wrapping or template artifacts.',
    parameterGuidance: {
      timeout: 'Adjust based on model size and complexity - smaller models (1-7B): 30-60s, medium (7-30B): 60-120s, large (30B+): 120-300s',
      temperature: 'Controls randomness: 0.1-0.3 for factual/code tasks, 0.5-0.7 for balanced output, 1.0+ for creative content',
      max_tokens: 'Set output length: 50-200 for brief responses, 500-1500 for detailed answers, 2000+ for comprehensive analysis',
    },
  },

  chat_completion: {
    description: 'Conduct multi-turn conversations with context retention. Maintains conversation history across messages. Returns structured JSON response with choices array.',
    warnings: 'Some models may include template tokens in output - check model documentation or use "show" to verify template compatibility.',
    parameterGuidance: {
      timeout: 'Scale with model size: add 30s per 10B parameters as baseline',
      temperature: 'Same as run: lower for consistency, higher for creativity',
      max_tokens: 'Consider cumulative context when setting limits',
    },
  },

  pull: {
    description: 'Download models from Ollama registry. Model sizes vary from <1GB (fast, basic) to 100GB+ (slow, advanced). Consider available disk space and intended use case.',
    guidance: 'Smaller models (1-7B) for speed, medium (7-30B) for balance, large (30B+) for maximum capability',
  },

  create: {
    description: 'Create custom model variants with specific system prompts and parameters. Useful for specialized behaviors and consistent configurations.',
  },

  serve: {
    description: 'Start the Ollama server if not already running. Usually auto-starts on most systems.',
  },

  // Keep other tools as-is since they're already generic
};

// Agent training guidance for parameter-based decision making
export const agentTrainingGuidance = {
  modelSelection: {
    principle: 'Model size and quantization determine speed/quality trade-offs',
    guidelines: [
      'Smaller parameter counts (1-7B) = faster responses, less nuanced',
      'Medium parameter counts (7-30B) = balanced performance',
      'Large parameter counts (30B+) = highest quality, slower responses',
      'Cloud-hosted models (0GB local) = dependent on internet, often faster',
      'Quantization affects quality: higher bits = better quality but larger size',
    ],
  },

  parameterOptimization: {
    timeout: {
      formula: 'base_timeout = 30s + (parameter_billions * 2s) + (prompt_complexity_factor * 20s)',
      factors: ['model size', 'prompt length', 'task complexity', 'system load'],
    },
    temperature: {
      ranges: {
        deterministic: [0.0, 0.3],
        balanced: [0.4, 0.7],
        creative: [0.8, 1.5],
        experimental: [1.5, 2.0],
      },
      useCases: {
        'code generation': 0.1,
        'technical writing': 0.3,
        'general Q&A': 0.5,
        'creative writing': 0.8,
        'brainstorming': 1.2,
      },
    },
    max_tokens: {
      guidance: 'Estimate 1.3 tokens per word, adjust based on response needs',
      ranges: {
        'yes/no answer': 10,
        'brief explanation': 100,
        'paragraph': 300,
        'detailed answer': 1000,
        'comprehensive analysis': 3000,
        'maximum context': 'model_context_limit / 2',
      },
    },
  },

  troubleshooting: {
    timeouts: 'Increase timeout or reduce prompt complexity',
    template_tokens: 'Use "run" instead of "chat_completion" or check model template format',
    memory_errors: 'Use smaller model or quantized version',
    quality_issues: 'Increase temperature slightly or try different model',
  },
};