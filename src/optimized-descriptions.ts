/**
 * MCP Ollama Tool Description Optimizations - IMPLEMENTATION COMPLETE
 * Status: ✅ All optimizations successfully integrated into src/index.ts
 * Date: 2025-09-24
 * Version: 0.2.0
 */

export const IMPLEMENTATION_STATUS = {
  status: "COMPLETE",
  critical_warning_added: "✅ Template token warning in chat_completion",
  decision_guidance_added: "✅ WHEN to use each tool clearly specified",
  parameter_optimization: "✅ Specific recommendations for all parameters",
  model_compatibility: "✅ Model-specific guidance integrated",
  build_verified: "✅ TypeScript compilation successful"
};

export const OPTIMIZED_TOOL_DESCRIPTIONS = {
  run: {
    name: 'run',
    description: 'Direct model execution for analysis, code generation, and single responses. Reliable for complex tasks. Returns clean text. Use for: code analysis, detailed explanations, structured outputs.',
    usage_notes: [
      'Best for: Single comprehensive responses, code analysis, technical explanations',
      'Response: Clean text format without special tokens',
      'Models: llama3.2:1b (fast, 2-3s), qwen2.5-coder:7b (code expert, 5-8s)',
      'Timeout: Increase for complex analysis (90000-120000ms recommended)'
    ],
    examples: [
      'Code analysis and review',
      'Architecture recommendations',
      'Detailed technical explanations',
      'Single-turn Q&A'
    ]
  },

  chat_completion: {
    name: 'chat_completion',
    description: 'Conversational API for dialogue and iterative refinement. Best for chat-like interactions. May include formatting tokens with some models. Use for: conversations, iterative development, role-play.',
    usage_notes: [
      'Best for: Multi-turn dialogues, conversational AI, iterative refinement',
      'Response: JSON format with choices array, may include special tokens',
      'Models: Verify compatibility with "show" command first',
      'Warning: Some models may include chat template tokens in responses'
    ],
    examples: [
      'Multi-turn conversations',
      'Interactive debugging sessions',
      'Step-by-step tutorials',
      'Role-based interactions'
    ]
  },

  // Suggested description updates for index.ts
  optimized_descriptions: {
    run: 'Direct model execution for analysis, code generation, and single responses. Reliable for complex tasks. Returns clean text without formatting tokens. Best for: code analysis (90-120s timeout), technical explanations, structured outputs.',

    chat_completion: 'Conversational API for dialogue and iterative refinement. Returns JSON with choices array. Note: Some models may include template tokens. Best for: multi-turn conversations, interactive sessions. Verify model compatibility with "show" first.',

    show: 'Get model details including parameters, context window, capabilities, and compatibility info. Essential before using chat_completion. Shows model architecture, quantization, and template format.',

    list: 'List available models with size and modification date. Run this first to see your options. Shows model name, size (GB), and last updated time.'
  }
};

// Implementation recommendations
export const IMPLEMENTATION_SUGGESTIONS = {
  parameter_guidance: {
    run: {
      timeout: {
        simple_prompt: 60000,    // 60s for simple queries
        code_analysis: 90000,    // 90s for code analysis
        complex_analysis: 120000 // 120s for complex tasks
      },
      temperature: {
        factual: 0.1,     // Technical/factual responses
        balanced: 0.3,    // Code generation
        creative: 0.7     // Creative writing
      }
    },
    chat_completion: {
      max_tokens: {
        short_response: 500,
        normal_response: 1500,
        detailed_response: 4000
      },
      system_prompt_warning: 'Test system prompts with specific models as behavior varies'
    }
  },

  model_selection_matrix: {
    fast_simple: 'llama3.2:1b',           // 2-3s, good for simple tasks
    code_expert: 'qwen2.5-coder:7b-instruct', // 5-8s, excellent for code
    balanced: 'mistral:7b',               // 4-6s, good general purpose
    analysis: 'smallthinker:latest'       // 4-6s, good for analysis
  },

  error_handling: {
    chat_completion_tokens: 'If response contains <|im_start|> or similar tokens, try "run" instead',
    timeout_errors: 'Increase timeout for complex prompts (up to 300000ms)',
    model_not_found: 'Use "list" to see available models, "pull" to download new ones'
  }
};

// Proposed changes to handle response format issues
export const RESPONSE_HANDLING = {
  chat_completion_sanitization: `
    // Clean response from potential template tokens
    const cleanResponse = (text: string): string => {
      return text
        .replace(/<\|im_start\|>/g, '')
        .replace(/<\|im_end\|>/g, '')
        .replace(/<\|eot_id\|>/g, '')
        .trim();
    };
  `,

  format_detection: `
    // Detect if model is adding template tokens
    const hasTemplateTokens = (text: string): boolean => {
      const tokens = ['<|im_start|>', '<|im_end|>', '<|eot_id|>', ':::'];
      return tokens.some(token => text.includes(token));
    };
  `,

  tool_selection_helper: `
    // Help users choose the right tool
    const recommendTool = (useCase: string): 'run' | 'chat_completion' => {
      const runCases = ['analysis', 'review', 'explain', 'generate', 'single'];
      const chatCases = ['conversation', 'dialogue', 'iterate', 'refine', 'multi-turn'];

      const useCaseLower = useCase.toLowerCase();

      if (runCases.some(c => useCaseLower.includes(c))) return 'run';
      if (chatCases.some(c => useCaseLower.includes(c))) return 'chat_completion';

      // Default to 'run' for better reliability
      return 'run';
    };
  `
};