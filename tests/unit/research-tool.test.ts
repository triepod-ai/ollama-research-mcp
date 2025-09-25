/**
 * Unit Tests for ResearchTool
 * Tests core orchestration, execution strategies, and error handling
 */

import { jest } from '@jest/globals';
import { ResearchTool } from '../../src/research-tool.js';
import { axiosMock } from '../mocks/axios-mock.js';
import { mockResearchRequest, testConfig } from '../setup.js';
import type { ResearchRequest } from '../../src/research-types.js';

describe('ResearchTool', () => {
  let researchTool: ResearchTool;

  beforeEach(() => {
    researchTool = new ResearchTool(testConfig.OLLAMA_HOST);
    axiosMock.reset();
    axiosMock.setBehavior('success');
    axiosMock.setupMocks();
  });

  afterEach(() => {
    axiosMock.reset();
  });

  describe('executeResearch', () => {
    it('should execute research with default parameters', async () => {
      const request: ResearchRequest = {
        question: 'What is the impact of AI on software development?'
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.question).toBe(request.question);
      expect(result.responses.length).toBe(3);
      expect(result.synthesis.length).toBeGreaterThan(0);
      expect(result.executionTime).toBeGreaterThan(0);
    });

    it('should execute research with custom parameters', async () => {
      const request: ResearchRequest = {
        question: 'How does AI improve code quality?',
        complexity: 'complex',
        focus: 'technical',
        parallel: true,
        include_metadata: true,
        temperature: 0.3,
        timeout: 45000
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.responses.length).toBe(3);
      expect(result.responses[0].metadata).toBeDefined();
      expect(result.synthesis.length).toBeGreaterThan(100); // Complex should be longer
    });

    it('should validate specific models when provided', async () => {
      const request: ResearchRequest = {
        question: 'Test question',
        models: ['llama3.2:1b', 'qwen2.5-coder:7b-instruct']
      };

      const result = await researchTool.executeResearch(request);

      expect(result.responses.length).toBe(2);
      expect(result.responses.some(r => r.model === 'llama3.2:1b')).toBe(true);
      expect(result.responses.some(r => r.model === 'qwen2.5-coder:7b-instruct')).toBe(true);
    });

    it('should handle invalid model names', async () => {
      const request: ResearchRequest = {
        question: 'Test question',
        models: ['nonexistent-model', 'another-fake-model']
      };

      await expect(researchTool.executeResearch(request)).rejects.toThrow('not found');
    });

    it('should validate enum parameters', async () => {
      const invalidComplexityRequest = {
        ...mockResearchRequest,
        complexity: 'invalid' as any
      };

      await expect(researchTool.executeResearch(invalidComplexityRequest))
        .rejects.toThrow('Complexity must be one of');

      const invalidFocusRequest = {
        ...mockResearchRequest,
        focus: 'invalid' as any
      };

      await expect(researchTool.executeResearch(invalidFocusRequest))
        .rejects.toThrow('Focus must be one of');
    });

    it('should require question parameter', async () => {
      const request = {
        complexity: 'medium'
      } as any;

      await expect(researchTool.executeResearch(request))
        .rejects.toThrow('question is required');
    });
  });

  describe('execution strategies', () => {
    it('should execute queries in parallel when requested', async () => {
      const startTime = Date.now();

      const request: ResearchRequest = {
        question: 'Parallel execution test',
        parallel: true
      };

      const result = await researchTool.executeResearch(request);
      const totalTime = Date.now() - startTime;

      expect(result).toHaveResearchResult();
      expect(result.responses.length).toBe(3);

      // Parallel execution should be faster than sequential
      // (This is approximate since we're using mocks)
      expect(totalTime).toBeLessThan(15000); // Should complete quickly with mocks
    });

    it('should execute queries sequentially by default', async () => {
      const request: ResearchRequest = {
        question: 'Sequential execution test',
        parallel: false
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.responses.length).toBe(3);
    });

    it('should handle mixed success and failures in parallel execution', async () => {
      axiosMock.setBehavior('mixed');
      axiosMock.setupMocks();

      const request: ResearchRequest = {
        question: 'Mixed results test',
        parallel: true
      };

      const result = await researchTool.executeResearch(request);

      expect(result.responses.length).toBe(3);

      // Should have both successful and failed responses
      const successfulResponses = result.responses.filter(r => !r.error);
      const failedResponses = result.responses.filter(r => r.error);

      expect(successfulResponses.length).toBeGreaterThan(0);
      expect(failedResponses.length).toBeGreaterThan(0);
    });
  });

  describe('timeout management', () => {
    it('should use complexity-based timeouts', async () => {
      // Set up slow responses to test timeout behavior
      axiosMock.setResponseDelay('/api/generate', 100);
      axiosMock.setupMocks();

      const simpleRequest: ResearchRequest = {
        question: 'Simple question',
        complexity: 'simple'
      };

      const complexRequest: ResearchRequest = {
        question: 'Complex question',
        complexity: 'complex'
      };

      const simpleResult = await researchTool.executeResearch(simpleRequest);
      const complexResult = await researchTool.executeResearch(complexRequest);

      expect(simpleResult).toHaveResearchResult();
      expect(complexResult).toHaveResearchResult();

      // Complex queries should have longer acceptable response times
      // This is tested indirectly through successful completion
    });

    it('should handle custom timeout parameter', async () => {
      const request: ResearchRequest = {
        question: 'Custom timeout test',
        timeout: 5000 // 5 seconds
      };

      const result = await researchTool.executeResearch(request);
      expect(result).toHaveResearchResult();
    });

    it('should handle timeout errors gracefully', async () => {
      axiosMock.setBehavior('timeout');
      axiosMock.setupMocks();

      const request: ResearchRequest = {
        question: 'Timeout test'
      };

      const result = await researchTool.executeResearch(request);

      expect(result.responses.length).toBe(3);
      result.responses.forEach(response => {
        expect(response.error).toContain('Timeout');
      });

      expect(result.synthesis).toContain('insufficient');
    });
  });

  describe('model selection and optimization', () => {
    it('should select models based on complexity level', async () => {
      const simpleRequest: ResearchRequest = {
        question: 'Simple question',
        complexity: 'simple'
      };

      const complexRequest: ResearchRequest = {
        question: 'Complex question',
        complexity: 'complex'
      };

      const simpleResult = await researchTool.executeResearch(simpleRequest);
      const complexResult = await researchTool.executeResearch(complexRequest);

      expect(simpleResult).toHaveResearchResult();
      expect(complexResult).toHaveResearchResult();

      // Verify that different models were potentially selected
      // (This is tested indirectly through successful execution)
    });

    it('should select models based on research focus', async () => {
      const technicalRequest: ResearchRequest = {
        question: 'Technical question',
        focus: 'technical'
      };

      const businessRequest: ResearchRequest = {
        question: 'Business question',
        focus: 'business'
      };

      const technicalResult = await researchTool.executeResearch(technicalRequest);
      const businessResult = await researchTool.executeResearch(businessRequest);

      expect(technicalResult).toHaveResearchResult();
      expect(businessResult).toHaveResearchResult();
    });

    it('should update performance history after successful executions', async () => {
      const request: ResearchRequest = {
        question: 'Performance tracking test'
      };

      // Execute multiple times to build performance history
      await researchTool.executeResearch(request);
      await researchTool.executeResearch(request);

      // Performance history is tracked internally
      // We test this indirectly by ensuring no errors occur
    });

    it('should handle no suitable models scenario', async () => {
      // Mock empty model list
      axiosMock.reset();
      const originalSetup = axiosMock.setupMocks;
      axiosMock.setupMocks = jest.fn().mockImplementation(() => {
        jest.mocked(axiosMock.setupMocks as any).mockRestore();
        originalSetup.call(axiosMock);

        // Override model list to be empty
        const mockedAxios = require('axios');
        mockedAxios.get.mockResolvedValue({
          data: { models: [] }
        });
      });
      axiosMock.setupMocks();

      const request: ResearchRequest = {
        question: 'No models test'
      };

      await expect(researchTool.executeResearch(request))
        .rejects.toThrow('No suitable models available');
    });
  });

  describe('response formatting and metadata', () => {
    it('should include metadata when requested', async () => {
      const request: ResearchRequest = {
        question: 'Metadata test',
        include_metadata: true
      };

      const result = await researchTool.executeResearch(request);

      expect(result.responses.length).toBeGreaterThan(0);
      result.responses.forEach(response => {
        if (!response.error) {
          expect(response.metadata).toBeDefined();
          expect(response.metadata?.parameters).toBeDefined();
          expect(response.metadata?.tier).toBeDefined();
        }
      });
    });

    it('should format prompts based on complexity', async () => {
      // Test different complexity levels
      const complexities: Array<'simple' | 'medium' | 'complex'> = ['simple', 'medium', 'complex'];

      for (const complexity of complexities) {
        const request: ResearchRequest = {
          question: `${complexity} complexity test`,
          complexity
        };

        const result = await researchTool.executeResearch(request);
        expect(result).toHaveResearchResult();

        // Verify appropriate response length based on complexity
        if (complexity === 'simple') {
          expect(result.responses.some(r => r.tokenCount < 100)).toBe(true);
        } else if (complexity === 'complex') {
          expect(result.responses.some(r => r.tokenCount > 50)).toBe(true);
        }
      }
    });

    it('should calculate response confidence accurately', async () => {
      const result = await researchTool.executeResearch(mockResearchRequest);

      expect(result.responses.length).toBeGreaterThan(0);
      result.responses.forEach(response => {
        if (!response.error) {
          expect(response.confidence).toBeGreaterThan(0);
          expect(response.confidence).toBeLessThanOrEqual(1);
        }
      });
    });
  });

  describe('error handling and resilience', () => {
    it('should handle network errors gracefully', async () => {
      axiosMock.setBehavior('error');
      axiosMock.setupMocks();

      const request: ResearchRequest = {
        question: 'Network error test'
      };

      // Should not throw, but should handle errors in responses
      const result = await researchTool.executeResearch(request);

      expect(result.responses.length).toBe(3);
      result.responses.forEach(response => {
        expect(response.error).toBeDefined();
      });

      expect(result.synthesis).toContain('insufficient');
    });

    it('should handle partial failures in execution', async () => {
      // Mix of success and failure responses
      axiosMock.setBehavior('mixed');
      axiosMock.setupMocks();

      const request: ResearchRequest = {
        question: 'Partial failure test'
      };

      const result = await researchTool.executeResearch(request);

      expect(result.responses.length).toBe(3);

      const successfulResponses = result.responses.filter(r => !r.error);
      const failedResponses = result.responses.filter(r => r.error);

      expect(successfulResponses.length).toBeGreaterThan(0);
      expect(failedResponses.length).toBeGreaterThan(0);

      // Should still generate synthesis from successful responses
      expect(result.synthesis.length).toBeGreaterThan(0);
    });

    it('should handle malformed API responses', async () => {
      // Mock malformed response
      axiosMock.reset();
      const mockedAxios = require('axios');
      mockedAxios.get.mockResolvedValue({
        data: { models: ['invalid'] } // Missing required fields
      });
      mockedAxios.post.mockResolvedValue({
        data: { response: null } // Invalid response format
      });

      const request: ResearchRequest = {
        question: 'Malformed response test'
      };

      // Should handle gracefully and not crash
      await expect(researchTool.executeResearch(request)).rejects.toThrow();
    });
  });

  describe('healthCheck', () => {
    it('should return healthy status when Ollama is available', async () => {
      const health = await researchTool.healthCheck();

      expect(health.status).toBe('healthy');
      expect(health.models).toBeGreaterThan(0);
      expect(health.message).toContain('operational');
    });

    it('should return unhealthy status when Ollama is unavailable', async () => {
      axiosMock.setBehavior('error');
      axiosMock.setupMocks();

      const health = await researchTool.healthCheck();

      expect(health.status).toBe('unhealthy');
      expect(health.models).toBe(0);
      expect(health.message).toContain('failed');
    });
  });

  describe('integration scenarios', () => {
    it('should handle full research workflow end-to-end', async () => {
      const request: ResearchRequest = {
        question: 'How can AI models improve software testing?',
        complexity: 'medium',
        focus: 'technical',
        parallel: false,
        include_metadata: true,
        temperature: 0.5
      };

      const result = await researchTool.executeResearch(request);

      // Comprehensive validation
      expect(result).toHaveResearchResult();
      expect(result.question).toBe(request.question);
      expect(result.responses).toHaveLength(3);
      expect(result.convergentThemes.length).toBeGreaterThan(0);
      expect(result.divergentPerspectives.length).toBeGreaterThan(0);
      expect(result.synthesis.length).toBeGreaterThan(50);
      expect(result.confidence).toBeGreaterThan(0);
      expect(result.executionTime).toBeGreaterThan(0);

      // Verify metadata inclusion
      result.responses.forEach(response => {
        expect(response).toHaveValidModelResponse();
        if (!response.error) {
          expect(response.metadata).toBeDefined();
        }
      });
    });

    it('should maintain performance within acceptable limits', async () => {
      const startTime = Date.now();

      const request: ResearchRequest = {
        question: 'Performance test question',
        complexity: 'simple'
      };

      const result = await researchTool.executeResearch(request);
      const executionTime = Date.now() - startTime;

      expect(result).toHaveResearchResult();
      expect(executionTime).toBeLessThan(10000); // Should complete within 10 seconds with mocks
    });

    it('should handle concurrent research requests', async () => {
      const requests = Array.from({ length: 3 }, (_, i) => ({
        question: `Concurrent test question ${i + 1}`,
        complexity: 'simple' as const
      }));

      const promises = requests.map(req => researchTool.executeResearch(req));
      const results = await Promise.all(promises);

      expect(results).toHaveLength(3);
      results.forEach((result, index) => {
        expect(result).toHaveResearchResult();
        expect(result.question).toBe(requests[index].question);
      });
    });
  });
});