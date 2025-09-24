// Optimized Tool Descriptions for MCP Ollama Server
// This file contains improved tool definitions with better discoverability and usability

import { Tool } from '@modelcontextprotocol/sdk/types.js';

export const optimizedTools: Tool[] = [
  // HIGH TIER - Core Execution Tools
  {
    name: 'list',
    description: 'List all locally available Ollama models. Returns name, size, and last modified date. Start here to see what models you have.',
    inputSchema: {
      type: 'object',
      properties: {
        // No parameters needed for basic listing
      },
      additionalProperties: false,
    },
  },

  {
    name: 'show',
    description: 'Get detailed model information including context window size, parameters, and architecture. Use after list to understand model capabilities.',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Model name from list command (e.g., "llama3.2:1b", "qwen2.5-coder:7b-instruct")',
        },
      },
      required: ['name'],
      additionalProperties: false,
    },
  },

  {
    name: 'run',
    description: 'Execute a single prompt with a model. Best for one-shot tasks. Use llama3.2:1b for speed (2-3s), qwen2.5-coder for code (5-8s).',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Model name (e.g., "llama3.2:1b" for speed, "qwen2.5-coder:7b-instruct" for code)',
        },
        prompt: {
          type: 'string',
          description: 'The prompt text to send to the model',
        },
        timeout: {
          type: 'number',
          description: 'Timeout in milliseconds (default: 60000, increase for complex prompts)',
          minimum: 1000,
          maximum: 300000,
        },
      },
      required: ['name', 'prompt'],
      additionalProperties: false,
    },
  },

  {
    name: 'chat_completion',
    description: 'Multi-turn conversation with context. Use for iterative tasks. Temperature: 0.1-0.3 for code, 0.7-1.0 for creative.',
    inputSchema: {
      type: 'object',
      properties: {
        model: {
          type: 'string',
          description: 'Model name (verify context length with show first)',
        },
        messages: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              role: {
                type: 'string',
                enum: ['system', 'user', 'assistant'],
                description: 'Message role in the conversation',
              },
              content: {
                type: 'string',
                description: 'Message content',
              },
            },
            required: ['role', 'content'],
          },
          description: 'Conversation history: [{role: "system"|"user"|"assistant", content: "text"}]',
        },
        temperature: {
          type: 'number',
          description: 'Creativity level: 0.1-0.3 for code/facts, 0.7-1.0 for creative writing',
          minimum: 0,
          maximum: 2,
        },
        timeout: {
          type: 'number',
          description: 'Timeout in milliseconds (default: 60000)',
          minimum: 1000,
        },
      },
      required: ['model', 'messages'],
      additionalProperties: false,
    },
  },

  // MEDIUM TIER - Model Management
  {
    name: 'pull',
    description: 'Download model from registry. Popular: llama3.2:1b (1GB, fast), qwen2.5-coder:7b-instruct (5GB, code), mistral:7b (4GB).',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Model to download (e.g., "llama3.2:1b" for 1GB fast model, "qwen2.5-coder:7b-instruct" for code)',
        },
      },
      required: ['name'],
      additionalProperties: false,
    },
  },

  // LOW TIER - Utilities
  {
    name: 'rm',
    description: 'Delete a local model to free disk space. Permanent action - model must be re-downloaded to use again.',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Model name to remove (check with list first)',
        },
      },
      required: ['name'],
      additionalProperties: false,
    },
  },

  {
    name: 'cp',
    description: 'Copy a model with a new name. Useful for creating backups before modifications or versioning custom models.',
    inputSchema: {
      type: 'object',
      properties: {
        source: {
          type: 'string',
          description: 'Existing model name to copy',
        },
        destination: {
          type: 'string',
          description: 'New name for the copy (e.g., "my-model-backup")',
        },
      },
      required: ['source', 'destination'],
      additionalProperties: false,
    },
  },

  // ADVANCED TIER - Custom Models
  {
    name: 'create',
    description: 'Create custom model from Modelfile. Define system prompts and parameters. Format: FROM base_model\\nSYSTEM "prompt"',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Name for your custom model (e.g., "my-assistant")',
        },
        modelfile: {
          type: 'string',
          description: 'Path to Modelfile OR inline content like: FROM llama3.2:1b\\nSYSTEM "You are helpful"',
        },
      },
      required: ['name', 'modelfile'],
      additionalProperties: false,
    },
  },

  {
    name: 'push',
    description: 'Upload model to Ollama registry. Requires account and authentication. Name format: username/modelname:tag',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Model name with namespace (e.g., "username/my-model:latest")',
        },
      },
      required: ['name'],
      additionalProperties: false,
    },
  },

  // SYSTEM TIER - Infrastructure
  {
    name: 'serve',
    description: 'Start Ollama server. Usually runs automatically on Windows. Default port: 11434.',
    inputSchema: {
      type: 'object',
      properties: {},
      additionalProperties: false,
    },
  },
];

// Workflow recommendations for tool chaining
export const workflowPatterns = {
  'model-discovery': {
    description: 'Discover and understand available models',
    steps: ['list', 'show', 'run or chat_completion'],
    example: 'First list models, then show details, finally run or chat',
  },
  'model-setup': {
    description: 'Install and test new models',
    steps: ['pull', 'list', 'show', 'run'],
    example: 'Pull model from registry, verify with list, check specs with show, test with run',
  },
  'custom-model': {
    description: 'Create and test custom models',
    steps: ['create', 'list', 'run', 'cp (for backup)', 'push (optional)'],
    example: 'Create from Modelfile, test with run, backup with cp, optionally push to registry',
  },
  'model-cleanup': {
    description: 'Manage disk space',
    steps: ['list', 'rm'],
    example: 'List models to see sizes, remove unwanted models',
  },
};

// Model recommendations based on use case
export const modelRecommendations = {
  'quick-response': {
    model: 'llama3.2:1b',
    size: '1GB',
    responseTime: '2-3s',
    useCase: 'Fast responses, simple tasks, low memory usage',
  },
  'code-generation': {
    model: 'qwen2.5-coder:7b-instruct',
    size: '5GB',
    responseTime: '5-8s',
    useCase: 'Programming, code review, technical documentation',
  },
  'balanced': {
    model: 'llama3.2:3b',
    size: '2GB',
    responseTime: '3-5s',
    useCase: 'General purpose, good quality-speed balance',
  },
  'analysis': {
    model: 'mistral:7b',
    size: '4GB',
    responseTime: '4-7s',
    useCase: 'Complex reasoning, analysis, longer contexts',
  },
  'tiny': {
    model: 'phi3:mini',
    size: '2GB',
    responseTime: '2-4s',
    useCase: 'Efficient reasoning, mobile/edge deployment',
  },
};

// Temperature guidelines for different task types
export const temperatureGuide = {
  'code': {
    range: [0.1, 0.3],
    description: 'Precise, deterministic output for code generation',
  },
  'factual': {
    range: [0.2, 0.4],
    description: 'Accurate, consistent responses for facts and data',
  },
  'analysis': {
    range: [0.3, 0.5],
    description: 'Balanced reasoning for analytical tasks',
  },
  'general': {
    range: [0.5, 0.7],
    description: 'Standard conversational responses',
  },
  'creative': {
    range: [0.7, 1.0],
    description: 'Creative writing, brainstorming, varied outputs',
  },
  'experimental': {
    range: [1.0, 1.5],
    description: 'Highly creative, unpredictable outputs',
  },
};

// Common error patterns and solutions
export const errorPatterns = {
  'model_not_found': {
    error: 'Model not found',
    solution: 'Run list to see available models, or pull to download',
    tools: ['list', 'pull'],
  },
  'timeout': {
    error: 'Request timeout',
    solution: 'Increase timeout parameter or use a faster model like llama3.2:1b',
    tools: ['run', 'chat_completion'],
  },
  'out_of_memory': {
    error: 'Out of memory',
    solution: 'Use a smaller model or remove unused models with rm',
    tools: ['list', 'rm', 'pull'],
  },
  'server_not_running': {
    error: 'Connection refused',
    solution: 'Start server with serve or check if Ollama Desktop is running',
    tools: ['serve'],
  },
  'context_exceeded': {
    error: 'Context length exceeded',
    solution: 'Use show to check model context size, reduce prompt length',
    tools: ['show'],
  },
};

// Export a function to get formatted help for a specific tool
export function getToolHelp(toolName: string): string {
  const tool = optimizedTools.find(t => t.name === toolName);
  if (!tool) {
    return `Tool '${toolName}' not found. Available tools: ${optimizedTools.map(t => t.name).join(', ')}`;
  }

  let help = `\n=== ${tool.name.toUpperCase()} TOOL ===\n`;
  help += `Description: ${tool.description}\n\n`;

  // Add workflow if exists
  const workflow = Object.entries(workflowPatterns).find(([_, w]) =>
    w.steps.includes(toolName)
  );
  if (workflow) {
    help += `Workflow: ${workflow[1].description}\n`;
    help += `Steps: ${workflow[1].steps.join(' → ')}\n\n`;
  }

  // Add model recommendations for execution tools
  if (toolName === 'run' || toolName === 'chat_completion') {
    help += 'Recommended Models:\n';
    Object.entries(modelRecommendations).forEach(([key, rec]) => {
      help += `  • ${rec.model} (${rec.size}): ${rec.useCase}\n`;
    });
    help += '\n';
  }

  // Add temperature guide for chat tools
  if (toolName === 'run' || toolName === 'chat_completion') {
    help += 'Temperature Guide:\n';
    Object.entries(temperatureGuide).forEach(([key, guide]) => {
      help += `  • ${key}: ${guide.range[0]}-${guide.range[1]} - ${guide.description}\n`;
    });
  }

  return help;
}