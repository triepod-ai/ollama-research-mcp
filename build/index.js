#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ErrorCode, ListToolsRequestSchema, McpError, } from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import { exec } from 'child_process';
import { promisify } from 'util';
import { ResearchTool } from './research-tool.js';
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
    researchTool;
    constructor() {
        this.server = new Server({
            name: 'ollama',
            version: '0.2.0',
        }, {
            capabilities: {
                tools: {},
            },
        });
        // Initialize research tool
        this.researchTool = new ResearchTool(OLLAMA_HOST);
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
                    description: 'Start Ollama server (usually auto-starts on Windows). Default port: 11434. Run if getting connection errors. Check with "list" after starting. For WSL/Docker: May need special host configuration.',
                    inputSchema: {
                        type: 'object',
                        properties: {},
                        additionalProperties: false,
                    },
                },
                {
                    name: 'create',
                    description: 'Create custom model from Modelfile. Define system prompts and parameters. Format: FROM base_model\\nSYSTEM "custom instructions"\\nPARAMETER temperature 0.7. Use for: Specialized behaviors, preset configurations, fine-tuned responses.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Name for your custom model (e.g., "my-assistant")',
                            },
                            modelfile: {
                                type: 'string',
                                description: 'Path to Modelfile OR inline content like: FROM llama3.2:1b\\nSYSTEM "You are helpful"\\nPARAMETER temperature 0.7',
                            },
                        },
                        required: ['name', 'modelfile'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'show',
                    description: 'Get detailed specifications for any model including context window size, parameter count, quantization method, and template format. Essential for understanding model capabilities and limitations before use. Check context length for prompt size limits and template format for compatibility.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Model name from list command',
                            },
                        },
                        required: ['name'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'run',
                    description: 'Execute a single prompt and get plain text response. Ideal for one-off queries, code generation, and analysis tasks. For coding tasks, use larger models (20B+ params) for better quality. Returns clean output without JSON wrapping or template artifacts. Faster than chat_completion for single requests.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Model name to use (from list command)',
                            },
                            prompt: {
                                type: 'string',
                                description: 'Your prompt text (single request, not conversation)',
                            },
                            timeout: {
                                type: 'number',
                                description: 'Timeout in milliseconds. Scale with model size: smaller models (30-60s), medium (60-120s), large (120-300s)',
                                minimum: 1000,
                                maximum: 300000,
                            },
                            temperature: {
                                type: 'number',
                                description: 'Controls randomness: 0.1-0.3 for factual/code, 0.5-0.7 for balanced, 1.0+ for creative content',
                                minimum: 0,
                                maximum: 2,
                            },
                            seed: {
                                type: 'number',
                                description: 'Random seed for reproducible outputs (use same seed for identical results)',
                            },
                            system: {
                                type: 'string',
                                description: 'Optional behavior instruction (e.g., "You are a Python expert")',
                            },
                            max_tokens: {
                                type: 'number',
                                description: 'Maximum tokens to generate. Estimate ~1.3 tokens per word. Brief: 50-200, Detailed: 500-1500, Comprehensive: 2000+',
                                minimum: 1,
                                maximum: 100000,
                            },
                            stop: {
                                type: 'array',
                                items: {
                                    type: 'string',
                                },
                                description: 'Stop sequences to end generation (e.g., ["\\n", "END"])',
                            },
                        },
                        required: ['name', 'prompt'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'pull',
                    description: 'Download models from Ollama registry. Model sizes vary from <1GB to 100GB+. Smaller models (1-7B params) are faster, larger models (30B+ params) offer better quality and are recommended for coding tasks. Check available disk space before downloading.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            name: {
                                type: 'string',
                                description: 'Model name to download from registry. Format: modelname:tag',
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
                    description: 'List all locally available models with their specifications. Shows model names, sizes, modification dates, and quantization formats. Use this to discover what models are installed before running queries. Start here to see available options.',
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
                    description: 'Conduct multi-turn conversations with context retention. Maintains conversation history across messages. Returns structured JSON response. Note: Some models may include template tokens in output - verify with "show" command for template compatibility.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            model: {
                                type: 'string',
                                description: 'Model name to use. Check template compatibility with "show" if output contains artifacts.',
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
                                description: 'Conversation history array with role and content for each message.',
                            },
                            temperature: {
                                type: 'number',
                                description: 'Controls randomness: 0.1-0.3 for consistency, 0.5-0.7 for balanced, 1.0+ for creativity',
                                minimum: 0,
                                maximum: 2,
                            },
                            timeout: {
                                type: 'number',
                                description: 'Timeout in milliseconds. Scale with model size and conversation length.',
                                minimum: 1000,
                                maximum: 300000,
                            },
                            max_tokens: {
                                type: 'number',
                                description: 'Maximum response length. Consider cumulative context when setting limits.',
                                minimum: 1,
                                maximum: 100000,
                            },
                            stop: {
                                type: 'array',
                                items: {
                                    type: 'string',
                                },
                                description: 'Stop sequences to end generation (e.g., ["\\n", "User:"])',
                            },
                        },
                        required: ['model', 'messages'],
                        additionalProperties: false,
                    },
                },
                {
                    name: 'research',
                    description: 'Intelligent multi-model research tool that queries 3 different models and provides comparative analysis. Automatically selects optimal models based on complexity (simple/medium/complex) and focus (technical/business/ethical/creative/general). Returns convergent themes, divergent perspectives, and synthesized recommendations. Note: For meaningful divergent perspectives, use larger models (>20B parameters).',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            question: {
                                type: 'string',
                                description: 'Research question or topic to investigate across multiple models',
                            },
                            complexity: {
                                type: 'string',
                                enum: ['simple', 'medium', 'complex'],
                                description: 'Complexity level: simple (fast models, brief responses), medium (balanced), complex (detailed analysis). Default: medium',
                            },
                            models: {
                                type: 'array',
                                items: {
                                    type: 'string',
                                },
                                description: 'Optional: specify exact 3 models to use (e.g., ["llama3.2:1b", "qwen2.5:7b"]). If omitted, optimal models are selected automatically.',
                            },
                            focus: {
                                type: 'string',
                                enum: ['technical', 'business', 'ethical', 'creative', 'general'],
                                description: 'Research focus area for model selection optimization. Default: general',
                            },
                            parallel: {
                                type: 'boolean',
                                description: 'Execute queries in parallel (faster) or sequential (resource-friendly). Default: false',
                            },
                            include_metadata: {
                                type: 'boolean',
                                description: 'Include model specifications in response for analysis. Default: false',
                            },
                            timeout: {
                                type: 'number',
                                description: 'Custom timeout in milliseconds. Auto-calculated based on complexity if not specified.',
                                minimum: 10000,
                                maximum: 600000,
                            },
                            temperature: {
                                type: 'number',
                                description: 'Controls response randomness across all models: 0.1-0.3 for factual, 0.7-1.0 for creative. Default: 0.7',
                                minimum: 0,
                                maximum: 2,
                            },
                        },
                        required: ['question'],
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
                    case 'research':
                        return await this.handleResearch(request.params.arguments);
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
            const requestBody = {
                model: args.name,
                prompt: args.prompt,
                stream: false,
            };
            // Add optional parameters if provided
            if (args.temperature !== undefined)
                requestBody.temperature = args.temperature;
            if (args.seed !== undefined)
                requestBody.seed = args.seed;
            if (args.system !== undefined)
                requestBody.system = args.system;
            if (args.max_tokens !== undefined)
                requestBody.max_tokens = args.max_tokens;
            if (args.stop !== undefined)
                requestBody.stop = args.stop;
            const response = await axios.post(`${OLLAMA_HOST}/api/generate`, requestBody, {
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
            // Build request options with all supported parameters
            const requestOptions = {
                model: args.model,
                prompt,
                stream: false,
                raw: true, // Add raw mode for more direct responses
            };
            // Add optional parameters if provided
            if (args.temperature !== undefined) {
                requestOptions.temperature = args.temperature;
            }
            if (args.max_tokens !== undefined) {
                requestOptions.num_predict = args.max_tokens; // Ollama uses num_predict for max tokens
            }
            if (args.stop !== undefined) {
                requestOptions.stop = Array.isArray(args.stop) ? args.stop : [args.stop];
            }
            // Make request to Ollama API with configurable timeout and raw mode
            const response = await axios.post(`${OLLAMA_HOST}/api/generate`, requestOptions, {
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
    async handleResearch(args) {
        try {
            // Validate required parameters
            if (!args.question || typeof args.question !== 'string') {
                throw new McpError(ErrorCode.InvalidParams, 'Research question is required');
            }
            // Build research request with validation
            const request = {
                question: args.question,
                complexity: args.complexity || 'medium',
                models: args.models,
                focus: args.focus || 'general',
                parallel: args.parallel || false,
                include_metadata: args.include_metadata || false,
                timeout: args.timeout,
                temperature: args.temperature || 0.7
            };
            // Validate enum values
            if (!['simple', 'medium', 'complex'].includes(request.complexity)) {
                throw new McpError(ErrorCode.InvalidParams, 'Complexity must be one of: simple, medium, complex');
            }
            if (!['technical', 'business', 'ethical', 'creative', 'general'].includes(request.focus)) {
                throw new McpError(ErrorCode.InvalidParams, 'Focus must be one of: technical, business, ethical, creative, general');
            }
            // Execute research
            const result = await this.researchTool.executeResearch(request);
            return {
                content: [
                    {
                        type: 'text',
                        text: JSON.stringify(result, null, 2),
                    },
                ],
            };
        }
        catch (error) {
            if (error instanceof McpError)
                throw error;
            throw new McpError(ErrorCode.InternalError, `Research execution failed: ${formatError(error)}`);
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
