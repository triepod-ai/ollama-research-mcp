/**
 * Integration Tests for MCP Server
 * Tests tool registration, handler validation, and end-to-end MCP integration
 */

import { jest } from '@jest/globals';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  McpError,
  ErrorCode
} from '@modelcontextprotocol/sdk/types.js';
import { axiosMock } from '../mocks/axios-mock.js';
import { mockResearchRequest, testConfig } from '../setup.js';

// Import the server class (we'll need to refactor it to be testable)
// For now, we'll create a test version
class TestableOllamaServer {
  private server: Server;
  private researchTool: any;

  constructor() {
    this.server = new Server(
      {
        name: 'ollama-test',
        version: '0.2.0-test',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    // Import and initialize research tool
    const { ResearchTool } = require('../../src/research-tool.js');
    this.researchTool = new ResearchTool(testConfig.OLLAMA_HOST);

    this.setupToolHandlers();
  }

  private setupToolHandlers() {
    // List tools handler
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'research',
          description: 'Intelligent multi-model research tool',
          inputSchema: {
            type: 'object',
            properties: {
              question: {
                type: 'string',
                description: 'Research question to investigate'
              },
              complexity: {
                type: 'string',
                enum: ['simple', 'medium', 'complex']
              }
            },
            required: ['question'],
            additionalProperties: false
          }
        },
        {
          name: 'list',
          description: 'List available models',
          inputSchema: {
            type: 'object',
            properties: {},
            additionalProperties: false
          }
        }
      ]
    }));

    // Call tool handler
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      switch (request.params.name) {
        case 'research':
          return await this.handleResearch(request.params.arguments);
        case 'list':
          return await this.handleList();
        default:
          throw new McpError(
            ErrorCode.MethodNotFound,
            `Unknown tool: ${request.params.name}`
          );
      }
    });
  }

  private async handleResearch(args: any) {
    try {
      const result = await this.researchTool.executeResearch(args);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }
        ]
      };
    } catch (error) {
      throw new McpError(
        ErrorCode.InternalError,
        `Research execution failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  private async handleList() {
    try {
      const axios = require('axios');
      const response = await axios.get(`${testConfig.OLLAMA_HOST}/api/tags`);
      const models = response.data.models || [];

      const formattedOutput = models.map((model: any) => {
        const sizeGB = (model.size / (1024 * 1024 * 1024)).toFixed(1);
        return `${model.name}\t${sizeGB}GB`;
      }).join('\n');

      return {
        content: [
          {
            type: 'text',
            text: formattedOutput || 'No models found'
          }
        ]
      };
    } catch (error) {
      throw new McpError(ErrorCode.InternalError, 'Failed to list models');
    }
  }

  getServer() {
    return this.server;
  }
}

describe('MCP Server Integration', () => {
  let server: TestableOllamaServer;
  let mcpServer: Server;

  beforeEach(() => {
    server = new TestableOllamaServer();
    mcpServer = server.getServer();
    axiosMock.reset();
    axiosMock.setBehavior('success');
    axiosMock.setupMocks();
  });

  afterEach(() => {
    axiosMock.reset();
  });

  describe('tool registration', () => {
    it('should register all required tools', async () => {
      const request = { method: 'tools/list' };

      // Get the list tools handler
      const handlers = (mcpServer as any)._requestHandlers;
      const listHandler = handlers.get(ListToolsRequestSchema);

      expect(listHandler).toBeDefined();

      const result = await listHandler(request);

      expect(result.tools).toHaveLength(2);
      expect(result.tools.find((t: any) => t.name === 'research')).toBeDefined();
      expect(result.tools.find((t: any) => t.name === 'list')).toBeDefined();
    });

    it('should validate research tool schema', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const listHandler = handlers.get(ListToolsRequestSchema);
      const result = await listHandler({ method: 'tools/list' });

      const researchTool = result.tools.find((t: any) => t.name === 'research');

      expect(researchTool.inputSchema.properties.question).toBeDefined();
      expect(researchTool.inputSchema.properties.complexity.enum).toContain('simple');
      expect(researchTool.inputSchema.properties.complexity.enum).toContain('medium');
      expect(researchTool.inputSchema.properties.complexity.enum).toContain('complex');
      expect(researchTool.inputSchema.required).toContain('question');
    });

    it('should validate list tool schema', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const listHandler = handlers.get(ListToolsRequestSchema);
      const result = await listHandler({ method: 'tools/list' });

      const listTool = result.tools.find((t: any) => t.name === 'list');

      expect(listTool.inputSchema.type).toBe('object');
      expect(listTool.inputSchema.additionalProperties).toBe(false);
    });
  });

  describe('tool execution', () => {
    it('should execute research tool successfully', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'research',
          arguments: {
            question: 'What is AI?',
            complexity: 'simple'
          }
        }
      };

      const result = await callHandler(request);

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      const parsedResult = JSON.parse(result.content[0].text);
      expect(parsedResult).toHaveResearchResult();
    });

    it('should execute list tool successfully', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'list',
          arguments: {}
        }
      };

      const result = await callHandler(request);

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');
      expect(result.content[0].text.length).toBeGreaterThan(0);
    });

    it('should handle unknown tool gracefully', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'unknown-tool',
          arguments: {}
        }
      };

      await expect(callHandler(request)).rejects.toThrow(McpError);
      await expect(callHandler(request)).rejects.toThrow('Unknown tool');
    });

    it('should validate research tool parameters', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      // Missing required question parameter
      const invalidRequest = {
        params: {
          name: 'research',
          arguments: {
            complexity: 'simple'
          }
        }
      };

      await expect(callHandler(invalidRequest)).rejects.toThrow(McpError);
    });

    it('should handle research tool with all parameters', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'research',
          arguments: {
            question: 'How does AI improve software development?',
            complexity: 'complex',
            models: ['llama3.2:1b'],
            focus: 'technical',
            parallel: true,
            include_metadata: true,
            temperature: 0.7,
            timeout: 45000
          }
        }
      };

      const result = await callHandler(request);
      const parsedResult = JSON.parse(result.content[0].text);

      expect(parsedResult).toHaveResearchResult();
      expect(parsedResult.question).toBe(request.params.arguments.question);
    });
  });

  describe('error handling', () => {
    it('should handle Ollama API errors in research tool', async () => {
      axiosMock.setBehavior('error');
      axiosMock.setupMocks();

      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'research',
          arguments: {
            question: 'Test question'
          }
        }
      };

      // Should not throw McpError, but should handle the error gracefully
      const result = await callHandler(request);
      const parsedResult = JSON.parse(result.content[0].text);

      // Should still return a result but with error information
      expect(parsedResult.responses.every((r: any) => r.error)).toBe(true);
    });

    it('should handle Ollama API errors in list tool', async () => {
      axiosMock.setBehavior('error');
      axiosMock.setupMocks();

      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'list',
          arguments: {}
        }
      };

      await expect(callHandler(request)).rejects.toThrow(McpError);
      await expect(callHandler(request)).rejects.toThrow('Failed to list models');
    });

    it('should handle timeout errors', async () => {
      axiosMock.setBehavior('timeout');
      axiosMock.setupMocks();

      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'research',
          arguments: {
            question: 'Timeout test'
          }
        }
      };

      const result = await callHandler(request);
      const parsedResult = JSON.parse(result.content[0].text);

      // Should handle timeouts gracefully in research responses
      expect(parsedResult.responses.every((r: any) => r.error?.includes('Timeout'))).toBe(true);
    });

    it('should provide meaningful error messages', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'research',
          arguments: {
            question: 'Test',
            complexity: 'invalid-complexity'
          }
        }
      };

      try {
        await callHandler(request);
        fail('Should have thrown an error');
      } catch (error) {
        expect(error).toBeInstanceOf(McpError);
        expect((error as McpError).message).toContain('Complexity must be one of');
      }
    });
  });

  describe('response formatting', () => {
    it('should format research responses correctly', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'research',
          arguments: mockResearchRequest
        }
      };

      const result = await callHandler(request);

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      // Should be valid JSON
      expect(() => JSON.parse(result.content[0].text)).not.toThrow();

      const parsedResult = JSON.parse(result.content[0].text);
      expect(parsedResult).toHaveResearchResult();
    });

    it('should format list responses correctly', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'list',
          arguments: {}
        }
      };

      const result = await callHandler(request);

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      // Should contain model information
      const text = result.content[0].text;
      expect(text).toContain('GB'); // Should show model sizes
    });

    it('should handle empty model list', async () => {
      // Override mock to return empty model list
      axiosMock.reset();
      const mockedAxios = require('axios');
      mockedAxios.get.mockResolvedValue({
        data: { models: [] }
      });

      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'list',
          arguments: {}
        }
      };

      const result = await callHandler(request);
      expect(result.content[0].text).toBe('No models found');
    });
  });

  describe('performance and reliability', () => {
    it('should handle concurrent tool calls', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const requests = Array.from({ length: 3 }, (_, i) => ({
        params: {
          name: 'research',
          arguments: {
            question: `Concurrent test question ${i + 1}`,
            complexity: 'simple'
          }
        }
      }));

      const promises = requests.map(req => callHandler(req));
      const results = await Promise.all(promises);

      expect(results).toHaveLength(3);
      results.forEach((result, index) => {
        const parsedResult = JSON.parse(result.content[0].text);
        expect(parsedResult).toHaveResearchResult();
        expect(parsedResult.question).toBe(requests[index].params.arguments.question);
      });
    });

    it('should maintain performance under load', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const startTime = Date.now();

      const request = {
        params: {
          name: 'research',
          arguments: {
            question: 'Performance test',
            complexity: 'simple'
          }
        }
      };

      const result = await callHandler(request);
      const executionTime = Date.now() - startTime;

      expect(result.content[0].text.length).toBeGreaterThan(0);
      expect(executionTime).toBeLessThan(5000); // Should complete quickly with mocks
    });

    it('should handle large research responses', async () => {
      // Mock large response
      axiosMock.reset();
      const mockedAxios = require('axios');
      mockedAxios.get.mockResolvedValue({
        data: {
          models: [
            { name: 'test-model', size: 1000000000, digest: 'abc123' }
          ]
        }
      });
      mockedAxios.post.mockResolvedValue({
        data: {
          response: 'A'.repeat(5000), // Large response
          done: true
        }
      });

      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'research',
          arguments: {
            question: 'Large response test',
            complexity: 'complex'
          }
        }
      };

      const result = await callHandler(request);
      const parsedResult = JSON.parse(result.content[0].text);

      expect(parsedResult).toHaveResearchResult();
      expect(parsedResult.synthesis.length).toBeGreaterThan(0);
    });
  });

  describe('MCP protocol compliance', () => {
    it('should use correct MCP error codes', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'unknown-tool',
          arguments: {}
        }
      };

      try {
        await callHandler(request);
        fail('Should have thrown McpError');
      } catch (error) {
        expect(error).toBeInstanceOf(McpError);
        expect((error as McpError).code).toBe(ErrorCode.MethodNotFound);
      }
    });

    it('should handle malformed requests gracefully', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const malformedRequest = {
        params: {
          // Missing name
          arguments: {}
        }
      };

      await expect(callHandler(malformedRequest as any)).rejects.toThrow();
    });

    it('should validate tool parameters according to schema', async () => {
      const handlers = (mcpServer as any)._requestHandlers;
      const callHandler = handlers.get(CallToolRequestSchema);

      const request = {
        params: {
          name: 'research',
          arguments: {
            question: 123, // Should be string
            complexity: 'simple'
          }
        }
      };

      // The validation might happen at a different layer,
      // but the tool should handle type mismatches gracefully
      await expect(callHandler(request)).rejects.toThrow();
    });
  });
});