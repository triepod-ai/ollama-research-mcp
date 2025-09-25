/**
 * End-to-End Integration Tests with Real Ollama API
 * Tests actual API responses, model availability, and real-world scenarios
 *
 * Note: These tests require a running Ollama instance with models installed
 * Run with: npm test -- --testPathPattern=e2e --testTimeout=120000
 */

import { jest } from '@jest/globals';
import { ResearchTool } from '../../src/research-tool.js';
import axios from 'axios';
import type { ResearchRequest } from '../../src/research-types.js';

// Configuration for real Ollama testing
const REAL_OLLAMA_HOST = process.env.OLLAMA_HOST || 'http://127.0.0.1:11434';
const E2E_TIMEOUT = 120000; // 2 minutes for real API calls

// Helper to check if Ollama is available
const isOllamaAvailable = async (): Promise<boolean> => {
  try {
    const response = await axios.get(`${REAL_OLLAMA_HOST}/api/tags`, { timeout: 5000 });
    return response.status === 200 && Array.isArray(response.data.models);
  } catch {
    return false;
  }
};

// Helper to get available models
const getAvailableModels = async (): Promise<string[]> => {
  try {
    const response = await axios.get(`${REAL_OLLAMA_HOST}/api/tags`);
    return response.data.models.map((model: any) => model.name);
  } catch {
    return [];
  }
};

describe('Ollama Integration E2E Tests', () => {
  let researchTool: ResearchTool;
  let availableModels: string[];
  let isOllamaOnline: boolean;

  beforeAll(async () => {
    isOllamaOnline = await isOllamaAvailable();

    if (!isOllamaOnline) {
      console.warn('Ollama is not available. E2E tests will be skipped.');
      console.warn(`Attempted connection to: ${REAL_OLLAMA_HOST}`);
      console.warn('To run E2E tests:');
      console.warn('1. Install and start Ollama');
      console.warn('2. Pull at least one model (e.g., ollama pull llama3.2:1b)');
      console.warn('3. Set OLLAMA_HOST environment variable if needed');
      return;
    }

    availableModels = await getAvailableModels();
    console.log(`Found ${availableModels.length} models:`, availableModels);

    researchTool = new ResearchTool(REAL_OLLAMA_HOST);
  }, E2E_TIMEOUT);

  // Skip all tests if Ollama is not available
  const describeIf = isOllamaOnline ? describe : describe.skip;
  const itIf = isOllamaOnline ? it : it.skip;

  describeIf('Real Ollama API Integration', () => {
    itIf('should connect to Ollama and list models', async () => {
      expect(availableModels.length).toBeGreaterThan(0);

      // Verify model structure
      availableModels.forEach(modelName => {
        expect(typeof modelName).toBe('string');
        expect(modelName.length).toBeGreaterThan(0);
      });
    }, E2E_TIMEOUT);

    itIf('should perform health check successfully', async () => {
      const health = await researchTool.healthCheck();

      expect(health.status).toBe('healthy');
      expect(health.models).toBe(availableModels.length);
      expect(health.message).toContain('operational');
    }, E2E_TIMEOUT);

    itIf('should execute simple research query', async () => {
      // Use the first available model or a common one
      const testModel = availableModels.find(m =>
        m.includes('llama') || m.includes('qwen') || m.includes('mistral')
      ) || availableModels[0];

      const request: ResearchRequest = {
        question: 'What is artificial intelligence?',
        complexity: 'simple',
        models: [testModel],
        timeout: 30000
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.question).toBe(request.question);
      expect(result.responses).toHaveLength(1);
      expect(result.responses[0].model).toBe(testModel);
      expect(result.responses[0].response.length).toBeGreaterThan(0);
      expect(result.responses[0].error).toBeUndefined();
      expect(result.synthesis.length).toBeGreaterThan(0);
    }, E2E_TIMEOUT);

    itIf('should execute multi-model research', async () => {
      if (availableModels.length < 2) {
        console.warn('Skipping multi-model test: less than 2 models available');
        return;
      }

      const testModels = availableModels.slice(0, Math.min(3, availableModels.length));

      const request: ResearchRequest = {
        question: 'Explain machine learning in simple terms',
        complexity: 'medium',
        models: testModels,
        timeout: 60000
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.responses).toHaveLength(testModels.length);

      // At least one response should succeed
      const successfulResponses = result.responses.filter(r => !r.error);
      expect(successfulResponses.length).toBeGreaterThan(0);

      successfulResponses.forEach(response => {
        expect(response).toHaveValidModelResponse();
        expect(response.response.length).toBeGreaterThan(20);
        expect(testModels).toContain(response.model);
      });

      expect(result.synthesis.length).toBeGreaterThan(50);
    }, E2E_TIMEOUT);

    itIf('should handle automatic model selection', async () => {
      const request: ResearchRequest = {
        question: 'What are the benefits of open source software?',
        complexity: 'medium',
        focus: 'business'
        // No models specified - should auto-select
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.responses.length).toBeGreaterThan(0);
      expect(result.responses.length).toBeLessThanOrEqual(3);

      // Should have selected models from available list
      result.responses.forEach(response => {
        expect(availableModels).toContain(response.model);
      });
    }, E2E_TIMEOUT);

    itIf('should execute research with different complexity levels', async () => {
      const testModel = availableModels[0];
      const complexities: Array<'simple' | 'medium' | 'complex'> = ['simple', 'medium', 'complex'];

      for (const complexity of complexities) {
        const request: ResearchRequest = {
          question: `Tell me about blockchain technology at ${complexity} level`,
          complexity,
          models: [testModel],
          timeout: complexity === 'complex' ? 90000 : 45000
        };

        const result = await researchTool.executeResearch(request);

        expect(result).toHaveResearchResult();
        expect(result.responses).toHaveLength(1);

        if (!result.responses[0].error) {
          // More complex requests should generally produce longer responses
          if (complexity === 'simple') {
            expect(result.responses[0].response.length).toBeGreaterThan(10);
          } else if (complexity === 'complex') {
            expect(result.responses[0].response.length).toBeGreaterThan(50);
          }
        }
      }
    }, E2E_TIMEOUT);

    itIf('should handle parallel vs sequential execution', async () => {
      if (availableModels.length < 2) {
        console.warn('Skipping parallel/sequential test: less than 2 models available');
        return;
      }

      const testModels = availableModels.slice(0, 2);
      const baseRequest: ResearchRequest = {
        question: 'Compare Python and JavaScript for web development',
        complexity: 'medium',
        models: testModels,
        timeout: 45000
      };

      // Test sequential execution
      const sequentialStart = Date.now();
      const sequentialResult = await researchTool.executeResearch({
        ...baseRequest,
        parallel: false
      });
      const sequentialTime = Date.now() - sequentialStart;

      // Test parallel execution
      const parallelStart = Date.now();
      const parallelResult = await researchTool.executeResearch({
        ...baseRequest,
        parallel: true
      });
      const parallelTime = Date.now() - parallelStart;

      // Both should succeed
      expect(sequentialResult).toHaveResearchResult();
      expect(parallelResult).toHaveResearchResult();

      // Parallel should be faster (allowing some variance)
      expect(parallelTime).toBeLessThanOrEqual(sequentialTime * 1.2);

      console.log(`Sequential: ${sequentialTime}ms, Parallel: ${parallelTime}ms`);
    }, E2E_TIMEOUT);

    itIf('should include metadata when requested', async () => {
      const testModel = availableModels[0];

      const request: ResearchRequest = {
        question: 'What is the future of artificial intelligence?',
        complexity: 'medium',
        models: [testModel],
        include_metadata: true,
        timeout: 45000
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.responses).toHaveLength(1);

      if (!result.responses[0].error) {
        expect(result.responses[0].metadata).toBeDefined();
        expect(result.responses[0].metadata?.parameters).toBeDefined();
        expect(result.responses[0].metadata?.tier).toBeDefined();
      }
    }, E2E_TIMEOUT);

    itIf('should handle temperature parameter', async () => {
      const testModel = availableModels[0];

      const lowTempRequest: ResearchRequest = {
        question: 'List three programming languages',
        complexity: 'simple',
        models: [testModel],
        temperature: 0.1, // Very deterministic
        timeout: 30000
      };

      const highTempRequest: ResearchRequest = {
        question: 'List three programming languages',
        complexity: 'simple',
        models: [testModel],
        temperature: 1.5, // More creative
        timeout: 30000
      };

      const lowTempResult = await researchTool.executeResearch(lowTempRequest);
      const highTempResult = await researchTool.executeResearch(highTempRequest);

      expect(lowTempResult).toHaveResearchResult();
      expect(highTempResult).toHaveResearchResult();

      // Both should succeed but may produce different responses
      if (!lowTempResult.responses[0].error && !highTempResult.responses[0].error) {
        expect(lowTempResult.responses[0].response.length).toBeGreaterThan(0);
        expect(highTempResult.responses[0].response.length).toBeGreaterThan(0);
      }
    }, E2E_TIMEOUT);

    itIf('should handle research focus areas', async () => {
      const testModel = availableModels[0];
      const focuses: Array<'technical' | 'business' | 'ethical' | 'creative' | 'general'> =
        ['technical', 'business', 'ethical', 'creative', 'general'];

      for (const focus of focuses) {
        const request: ResearchRequest = {
          question: 'What is the impact of AI on society?',
          complexity: 'medium',
          models: [testModel],
          focus,
          timeout: 45000
        };

        const result = await researchTool.executeResearch(request);

        expect(result).toHaveResearchResult();
        expect(result.responses).toHaveLength(1);

        if (!result.responses[0].error) {
          expect(result.responses[0].response.length).toBeGreaterThan(10);
          expect(result.synthesis).toContain('AI'); // Should address the topic
        }
      }
    }, E2E_TIMEOUT);
  });

  describeIf('Error Handling with Real API', () => {
    itIf('should handle non-existent model gracefully', async () => {
      const request: ResearchRequest = {
        question: 'Test question',
        models: ['non-existent-model:latest'],
        timeout: 15000
      };

      await expect(researchTool.executeResearch(request))
        .rejects.toThrow('not found');
    }, E2E_TIMEOUT);

    itIf('should handle network timeout', async () => {
      const request: ResearchRequest = {
        question: 'This is a test question that should timeout',
        complexity: 'simple',
        models: [availableModels[0]],
        timeout: 1000 // Very short timeout
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.responses).toHaveLength(1);

      // Should timeout and have error
      if (result.responses[0].error) {
        expect(result.responses[0].error).toContain('timeout');
      }
    }, E2E_TIMEOUT);

    itIf('should handle empty question', async () => {
      const request: ResearchRequest = {
        question: '',
        models: [availableModels[0]]
      };

      // Should handle empty question gracefully
      const result = await researchTool.executeResearch(request);
      expect(result).toHaveResearchResult();
    }, E2E_TIMEOUT);

    itIf('should handle very long questions', async () => {
      const longQuestion = 'What is artificial intelligence? '.repeat(100);

      const request: ResearchRequest = {
        question: longQuestion,
        complexity: 'simple',
        models: [availableModels[0]],
        timeout: 60000
      };

      const result = await researchTool.executeResearch(request);

      expect(result).toHaveResearchResult();
      expect(result.responses).toHaveLength(1);

      // Should handle long questions appropriately
      if (!result.responses[0].error) {
        expect(result.responses[0].response.length).toBeGreaterThan(0);
      }
    }, E2E_TIMEOUT);
  });

  describeIf('Performance with Real API', () => {
    itIf('should complete simple queries within reasonable time', async () => {
      const request: ResearchRequest = {
        question: 'What is 2+2?',
        complexity: 'simple',
        models: [availableModels[0]],
        timeout: 30000
      };

      const startTime = Date.now();
      const result = await researchTool.executeResearch(request);
      const executionTime = Date.now() - startTime;

      expect(result).toHaveResearchResult();
      expect(executionTime).toBeLessThan(30000); // Should complete within timeout

      if (!result.responses[0].error) {
        expect(result.responses[0].responseTime).toBeGreaterThan(0);
        expect(result.responses[0].responseTime).toBeLessThan(30000);
      }
    }, E2E_TIMEOUT);

    itIf('should handle multiple concurrent requests', async () => {
      const requests = Array.from({ length: 3 }, (_, i) => ({
        question: `What is the number ${i + 1}?`,
        complexity: 'simple' as const,
        models: [availableModels[0]],
        timeout: 30000
      }));

      const startTime = Date.now();
      const promises = requests.map(req => researchTool.executeResearch(req));
      const results = await Promise.allSettled(promises);
      const totalTime = Date.now() - startTime;

      expect(results).toHaveLength(3);
      expect(totalTime).toBeLessThan(60000); // Should complete within reasonable time

      const successfulResults = results
        .filter(r => r.status === 'fulfilled')
        .map(r => (r as PromiseFulfilled<any>).value);

      expect(successfulResults.length).toBeGreaterThan(0);
      successfulResults.forEach(result => {
        expect(result).toHaveResearchResult();
      });
    }, E2E_TIMEOUT);
  });

  describeIf('Model-Specific Testing', () => {
    // Test specific models if available
    const commonModels = {
      'llama3.2:1b': { tier: 'fast', good_for: ['simple', 'medium'] },
      'qwen2.5-coder:7b-instruct': { tier: 'balanced', good_for: ['technical'] },
      'mistral:7b': { tier: 'balanced', good_for: ['general'] }
    };

    Object.entries(commonModels).forEach(([modelName, specs]) => {
      itIf(`should work with ${modelName} if available`, async () => {
        if (!availableModels.includes(modelName)) {
          console.warn(`${modelName} not available, skipping model-specific test`);
          return;
        }

        const request: ResearchRequest = {
          question: `Test question for ${modelName}`,
          complexity: 'medium',
          models: [modelName],
          timeout: 45000
        };

        const result = await researchTool.executeResearch(request);

        expect(result).toHaveResearchResult();
        expect(result.responses).toHaveLength(1);
        expect(result.responses[0].model).toBe(modelName);

        if (!result.responses[0].error) {
          expect(result.responses[0]).toHaveValidModelResponse();
          expect(result.responses[0].response.length).toBeGreaterThan(0);
        }
      }, E2E_TIMEOUT);
    });
  });

  // Cleanup and reporting
  afterAll(async () => {
    if (isOllamaOnline) {
      console.log('E2E test summary:');
      console.log(`- Ollama host: ${REAL_OLLAMA_HOST}`);
      console.log(`- Available models: ${availableModels.length}`);
      console.log(`- Models tested: ${availableModels.slice(0, 3).join(', ')}`);
    } else {
      console.log('E2E tests were skipped due to Ollama not being available');
    }
  });
});