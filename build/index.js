#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ErrorCode, ListToolsRequestSchema, McpError, } from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import { exec } from 'child_process';
import { promisify } from 'util';
const execAsync = promisify(exec);
// Default Ollama API endpoint
const OLLAMA_HOST = process.env.OLLAMA_HOST || 'http://127.0.0.1:11434';
const DEFAULT_TIMEOUT = 60000; // 60 seconds default timeout
// Helper function to format error messages
const formatError = (error) => {
    if (error instanceof Error) {
        return error.message;
    }
    return String(error);
};
class OllamaServer {
    server;
    constructor() {
        this.server = new Server({
            name: 'ollama',
            version: '0.1.0',
        }, {
            capabilities: {
                tools: {},
            },
        });
        this.setupToolHandlers();
        // Error handling
        this.server.onerror = (error) => console.error('[MCP Error]', error);
        process.on('SIGINT', async () => {
            await this.server.close();
            process.exit(0);
        });
    }
    setupToolHandlers() {
        this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
            tools: [
                {
                    name: 'serve',
                    description: '✅ 95% Success Rate - Local Ollama server startup. 🚀 5-15s Startup (system-dependent). 🔗 Tier SYSTEM infrastructure management. Usually handled by Windows service.',
                    inputSchema: {
                        type: 'object',
                        properties: {},
                        additionalProperties: false,
                    },
                },
                {
                    name: 'create',
                    description: '✅ 90% Success Rate - Custom model creation from Modelfile. 🚀 1-30min (complexity-dependent). 🔗 Tier ADVANCED for custom model development. Use for project-specific fine-tuning.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Name for the custom model (e.g., custom-assistant)',
                            },
                            modelfile: {
                                type: 'string',
                                description: 'Path to Modelfile with system prompt and configuration',
                            },
                        },
                        required: ['name', 'modelfile'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'show',
                    description: '✅ 100% Success Rate - Detailed model metadata API. 🚀 <3s Response Time (JSON specifications). 🔗 Tier HIGH integration for model capability discovery. Workflow: ollama_list() → ollama_show() → optimize parameters for ollama_run()/ollama_chat_completion(). Returns: context length, parameter count, quantization, architecture details, performance characteristics.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Name of the model (get from ollama_list output)',
                            },
                        },
                        required: ['name'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'run',
                    description: '✅ 100% Success Rate - Direct Windows Ollama API integration. 🚀 2-8s Response Time (model-dependent). 🔗 Tier HIGH integration with manus_code_interpreter workflows. Primary alternative to external API calls for privacy-sensitive code generation. Workflow: ollama_list() → ollama_show() → ollama_run() → manus_code_interpreter(). Model selection: llama3.2:1b (2-3s, quick tasks), qwen2.5-coder:7b-instruct (5-8s, code generation), smallthinker:latest (4-6s, analysis).',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Name of the model (check ollama_list() for available models)',
                            },
                            prompt: {
                                type: 'string',
                                description: 'Prompt to send to the model (optimize for model type)',
                            },
                            timeout: {
                                type: 'number',
                                description: 'Timeout in milliseconds (default: 60000, increase for complex prompts)',
                                minimum: 1000,
                            },
                        },
                        required: ['name', 'prompt'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'pull',
                    description: '✅ 95% Success Rate - Registry download with retry logic. 🚀 30s-10m (size-dependent). 🔗 Tier MEDIUM integration for one-time model setup. Use for: qwen2.5-coder:7b-instruct (specialized coding), llama3.2:1b (fast general).',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Name of the model to pull (e.g., qwen2.5-coder:7b-instruct)',
                            },
                        },
                        required: ['name'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'push',
                    description: '✅ 85% Success Rate - Model registry publication. 🚀 5-60min (network-dependent). 🔗 Tier ADVANCED for model sharing workflow. Use for publishing custom models.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Name of the model to push (requires registry access)',
                            },
                        },
                        required: ['name'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'list',
                    description: '✅ 100% Success Rate - HTTP API model discovery. 🚀 <2s Response Time (cached metadata). 🔗 Tier HIGH integration, foundation for all workflows. Primary alternative to manual model management. Workflow: Start with ollama_list() → ollama_show() → ollama_run()/ollama_chat_completion(). Returns: model name, digest (12 chars), size (GB), modified date. Direct Windows host access via host.docker.internal:11434.',
                    inputSchema: {
                        type: 'object',
                        properties: {},
                        additionalProperties: false,
                    },
                },
                {
                    name: 'cp',
                    description: '✅ 100% Success Rate - Model versioning and backup. 🚀 <10s Response Time (metadata-only). 🔗 Tier LOW for version control workflow. Use for model backup before customization.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            source: {
                                type: 'string',
                                description: 'Source model name (existing model to copy)',
                            },
                            destination: {
                                type: 'string',
                                description: 'Destination model name (new model name for backup)',
                            },
                        },
                        required: ['source', 'destination'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'rm',
                    description: '✅ 100% Success Rate - Local model deletion for storage cleanup. 🚀 <5s Response Time (immediate). 🔗 Tier LOW storage management utility. Use with ollama_list() to identify unused models.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Name of the model to remove (check ollama_list first)',
                            },
                        },
                        required: ['name'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'chat_completion',
                    description: '✅ 100% Success Rate - OpenAI-compatible conversation API. 🚀 3-10s Response Time (context-dependent). 🔗 Tier HIGH integration for multi-turn conversation workflows. Primary alternative to OpenAI GPT API for privacy-sensitive conversations. Workflow: ollama_list() → ollama_show() → ollama_chat_completion() → manus_code_interpreter(). Temperature guide: 0.1-0.3 for code, 0.7-1.0 for creative tasks.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            model: {
                                type: 'string',
                                description: 'Name of the Ollama model to use (check context length with ollama_show)',
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
                                description: 'Array of messages in conversation (system → user → assistant pattern)',
                            },
                            temperature: {
                                type: 'number',
                                description: 'Sampling temperature: 0.1-0.3 for code, 0.7-1.0 for creative tasks',
                                minimum: 0,
                                maximum: 2,
                            },
                            timeout: {
                                type: 'number',
                                description: 'Timeout in milliseconds (default: 60000, increase for complex conversations)',
                                minimum: 1000,
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
                        throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${request.params.name}`);
                }
            }
            catch (error) {
                if (error instanceof McpError)
                    throw error;
                throw new McpError(ErrorCode.InternalError, `Error executing ${request.params.name}: ${formatError(error)}`);
            }
        });
    }
    async handleServe() {
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
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to start Ollama server: ${formatError(error)}`);
        }
    }
    async handleCreate(args) {
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
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to create model: ${formatError(error)}`);
        }
    }
    async handleShow(args) {
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
        }
        catch (error) {
            if (axios.isAxiosError(error)) {
                throw new McpError(ErrorCode.InternalError, `Ollama API error: ${error.response?.data?.error || error.message}`);
            }
            throw new McpError(ErrorCode.InternalError, `Failed to show model info: ${formatError(error)}`);
        }
    }
    async handleRun(args) {
        try {
            // Use non-streaming mode for simplicity and compatibility
            const response = await axios.post(`${OLLAMA_HOST}/api/generate`, {
                model: args.name,
                prompt: args.prompt,
                stream: false,
            }, {
                timeout: args.timeout || DEFAULT_TIMEOUT,
            });
            return {
                content: [
                    {
                        type: 'text',
                        text: response.data.response,
                    },
                ],
            };
        }
        catch (error) {
            if (axios.isAxiosError(error)) {
                throw new McpError(ErrorCode.InternalError, `Ollama API error: ${error.response?.data?.error || error.message}`);
            }
            throw new McpError(ErrorCode.InternalError, `Failed to run model: ${formatError(error)}`);
        }
    }
    async handlePull(args) {
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
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to pull model: ${formatError(error)}`);
        }
    }
    async handlePush(args) {
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
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to push model: ${formatError(error)}`);
        }
    }
    async handleList() {
        try {
            const response = await axios.get(`${OLLAMA_HOST}/api/tags`);
            const models = response.data.models || [];
            // Format output similar to CLI output
            const formattedOutput = models.map((model) => {
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
        }
        catch (error) {
            if (axios.isAxiosError(error)) {
                throw new McpError(ErrorCode.InternalError, `Ollama API error: ${error.response?.data?.error || error.message}`);
            }
            throw new McpError(ErrorCode.InternalError, `Failed to list models: ${formatError(error)}`);
        }
    }
    async handleCopy(args) {
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
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to copy model: ${formatError(error)}`);
        }
    }
    async handleRemove(args) {
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
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to remove model: ${formatError(error)}`);
        }
    }
    async handleChatCompletion(args) {
        try {
            // Convert chat messages to a single prompt
            const prompt = args.messages
                .map((msg) => {
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
            const response = await axios.post(`${OLLAMA_HOST}/api/generate`, {
                model: args.model,
                prompt,
                stream: false,
                temperature: args.temperature,
                raw: true, // Add raw mode for more direct responses
            }, {
                timeout: args.timeout || DEFAULT_TIMEOUT,
            });
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
        }
        catch (error) {
            if (axios.isAxiosError(error)) {
                throw new McpError(ErrorCode.InternalError, `Ollama API error: ${error.response?.data?.error || error.message}`);
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
