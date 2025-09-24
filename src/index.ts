#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Default Ollama API endpoint
const OLLAMA_HOST = process.env.OLLAMA_HOST || 'http://127.0.0.1:11434';
const DEFAULT_TIMEOUT = 60000; // 60 seconds default timeout

interface OllamaGenerateResponse {
  model: string;
  created_at: string;
  response: string;
  done: boolean;
}

// Helper function to format error messages
const formatError = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
};

class OllamaServer {
  private server: Server;

  constructor() {
    this.server = new Server(
      {
        name: 'ollama',
        version: '0.2.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
    
    // Error handling
    this.server.onerror = (error) => console.error('[MCP Error]', error);
    process.on('SIGINT', async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  private setupToolHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'serve',
          description: 'Start Ollama server. Usually runs automatically on Windows. Default port: 11434.',
          inputSchema: {
            type: 'object',
            properties: {},
            additionalProperties: false,
          },
        },
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
              temperature: {
                type: 'number',
                description: 'Creativity level: 0.1-0.3 for code/facts, 0.7-1.0 for creative writing',
                minimum: 0,
                maximum: 2,
              },
              seed: {
                type: 'number',
                description: 'Random seed for reproducible outputs',
              },
              system: {
                type: 'string',
                description: 'Optional system prompt to set behavior (overrides model default)',
              },
            },
            required: ['name', 'prompt'],
            additionalProperties: false,
          },
        },
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
        {
          name: 'list',
          description: 'List all locally available Ollama models. Returns name, size, and last modified date. Start here to see what models you have.',
          inputSchema: {
            type: 'object',
            properties: {},
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
                    },
                    content: {
                      type: 'string',
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
                maximum: 300000,
              },
              max_tokens: {
                type: 'number',
                description: 'Maximum tokens to generate in response',
                minimum: 1,
                maximum: 100000,
              },
              stop: {
                type: 'array',
                items: {
                  type: 'string',
                },
                description: 'Stop sequences to end generation',
              },
            },
            required: ['model', 'messages'],
            additionalProperties: false,
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      try {
        switch (request.params.name) {
          case 'serve':
            return await this.handleServe();
          case 'create':
            return await this.handleCreate(request.params.arguments);
          case 'show':
            return await this.handleShow(request.params.arguments);
          case 'run':
            return await this.handleRun(request.params.arguments);
          case 'pull':
            return await this.handlePull(request.params.arguments);
          case 'push':
            return await this.handlePush(request.params.arguments);
          case 'list':
            return await this.handleList();
          case 'cp':
            return await this.handleCopy(request.params.arguments);
          case 'rm':
            return await this.handleRemove(request.params.arguments);
          case 'chat_completion':
            return await this.handleChatCompletion(request.params.arguments);
          default:
            throw new McpError(
              ErrorCode.MethodNotFound,
              `Unknown tool: ${request.params.name}`
            );
        }
      } catch (error) {
        if (error instanceof McpError) throw error;
        throw new McpError(
          ErrorCode.InternalError,
          `Error executing ${request.params.name}: ${formatError(error)}`
        );
      }
    });
  }

  private async handleServe() {
    try {
      const { stdout, stderr } = await execAsync('ollama serve');
      return {
        content: [
          {
            type: 'text',
            text: stdout || stderr,
          },
        ],
      };
    } catch (error) {
      throw new McpError(ErrorCode.InternalError, `Failed to start Ollama server: ${formatError(error)}`);
    }
  }

  private async handleCreate(args: any) {
    try {
      const { stdout, stderr } = await execAsync(`ollama create ${args.name} -f ${args.modelfile}`);
      return {
        content: [
          {
            type: 'text',
            text: stdout || stderr,
          },
        ],
      };
    } catch (error) {
      throw new McpError(ErrorCode.InternalError, `Failed to create model: ${formatError(error)}`);
    }
  }

  private async handleShow(args: any) {
    try {
      const response = await axios.post(`${OLLAMA_HOST}/api/show`, {
        name: args.name
      });
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(response.data, null, 2),
          },
        ],
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new McpError(
          ErrorCode.InternalError,
          `Ollama API error: ${error.response?.data?.error || error.message}`
        );
      }
      throw new McpError(ErrorCode.InternalError, `Failed to show model info: ${formatError(error)}`);
    }
  }

  private async handleRun(args: any) {
    try {
      // Use non-streaming mode for simplicity and compatibility
      const response = await axios.post(
        `${OLLAMA_HOST}/api/generate`,
        {
          model: args.name,
          prompt: args.prompt,
          stream: false,
        },
        {
          timeout: args.timeout || DEFAULT_TIMEOUT,
        }
      );

      return {
        content: [
          {
            type: 'text',
            text: response.data.response,
          },
        ],
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new McpError(
          ErrorCode.InternalError,
          `Ollama API error: ${error.response?.data?.error || error.message}`
        );
      }
      throw new McpError(ErrorCode.InternalError, `Failed to run model: ${formatError(error)}`);
    }
  }

  private async handlePull(args: any) {
    try {
      const { stdout, stderr } = await execAsync(`ollama pull ${args.name}`);
      return {
        content: [
          {
            type: 'text',
            text: stdout || stderr,
          },
        ],
      };
    } catch (error) {
      throw new McpError(ErrorCode.InternalError, `Failed to pull model: ${formatError(error)}`);
    }
  }

  private async handlePush(args: any) {
    try {
      const { stdout, stderr } = await execAsync(`ollama push ${args.name}`);
      return {
        content: [
          {
            type: 'text',
            text: stdout || stderr,
          },
        ],
      };
    } catch (error) {
      throw new McpError(ErrorCode.InternalError, `Failed to push model: ${formatError(error)}`);
    }
  }

  private async handleList() {
    try {
      const response = await axios.get(`${OLLAMA_HOST}/api/tags`);
      const models = response.data.models || [];
      
      // Format output similar to CLI output
      const formattedOutput = models.map((model: any) => {
        const sizeGB = (model.size / (1024 * 1024 * 1024)).toFixed(1);
        const modifiedDate = new Date(model.modified_at).toLocaleString();
        return `${model.name}\t${model.digest.substring(0, 12)}\t${sizeGB}GB\t${modifiedDate}`;
      }).join('\n');

      return {
        content: [
          {
            type: 'text',
            text: formattedOutput || 'No models found',
          },
        ],
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new McpError(
          ErrorCode.InternalError,
          `Ollama API error: ${error.response?.data?.error || error.message}`
        );
      }
      throw new McpError(ErrorCode.InternalError, `Failed to list models: ${formatError(error)}`);
    }
  }

  private async handleCopy(args: any) {
    try {
      const { stdout, stderr } = await execAsync(`ollama cp ${args.source} ${args.destination}`);
      return {
        content: [
          {
            type: 'text',
            text: stdout || stderr,
          },
        ],
      };
    } catch (error) {
      throw new McpError(ErrorCode.InternalError, `Failed to copy model: ${formatError(error)}`);
    }
  }

  private async handleRemove(args: any) {
    try {
      const { stdout, stderr } = await execAsync(`ollama rm ${args.name}`);
      return {
        content: [
          {
            type: 'text',
            text: stdout || stderr,
          },
        ],
      };
    } catch (error) {
      throw new McpError(ErrorCode.InternalError, `Failed to remove model: ${formatError(error)}`);
    }
  }

  private async handleChatCompletion(args: any) {
    try {
      // Convert chat messages to a single prompt
      const prompt = args.messages
        .map((msg: any) => {
          switch (msg.role) {
            case 'system':
              return `System: ${msg.content}\n`;
            case 'user':
              return `User: ${msg.content}\n`;
            case 'assistant':
              return `Assistant: ${msg.content}\n`;
            default:
              return '';
          }
        })
        .join('');

      // Make request to Ollama API with configurable timeout and raw mode
      const response = await axios.post<OllamaGenerateResponse>(
        `${OLLAMA_HOST}/api/generate`,
        {
          model: args.model,
          prompt,
          stream: false,
          temperature: args.temperature,
          raw: true, // Add raw mode for more direct responses
        },
        {
          timeout: args.timeout || DEFAULT_TIMEOUT,
        }
      );

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              id: 'chatcmpl-' + Date.now(),
              object: 'chat.completion',
              created: Math.floor(Date.now() / 1000),
              model: args.model,
              choices: [
                {
                  index: 0,
                  message: {
                    role: 'assistant',
                    content: response.data.response,
                  },
                  finish_reason: 'stop',
                },
              ],
            }, null, 2),
          },
        ],
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new McpError(
          ErrorCode.InternalError,
          `Ollama API error: ${error.response?.data?.error || error.message}`
        );
      }
      throw new McpError(ErrorCode.InternalError, `Unexpected error: ${formatError(error)}`);
    }
  }

  async run() {
    // Create stdio transport only - removing problematic SSE transport
    const stdioTransport = new StdioServerTransport();
    
    // Connect stdio transport
    await this.server.connect(stdioTransport);
    
    console.error('Ollama MCP server running on stdio');
  }
}

const server = new OllamaServer();
server.run().catch(console.error);
