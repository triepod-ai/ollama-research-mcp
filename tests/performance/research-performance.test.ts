/**
 * Performance Tests for Research Tool
 * Tests timeout management, resource usage, caching effectiveness, and fallback performance
 */

import { jest } from '@jest/globals';
import { ResearchTool } from '../../src/research-tool.js';
import { axiosMock } from '../mocks/axios-mock.js';
import { testConfig } from '../setup.js';
import type { ResearchRequest, ComplexityLevel } from '../../src/research-types.js';

// Performance test utilities
const measurePerformance = async <T>(fn: () => Promise<T>): Promise<{ result: T; time: number; memory: NodeJS.MemoryUsage }> => {
  const memoryBefore = process.memoryUsage();
  const startTime = Date.now();

  const result = await fn();

  const endTime = Date.now();
  const memoryAfter = process.memoryUsage();

  return {
    result,
    time: endTime - startTime,
    memory: {
      rss: memoryAfter.rss - memoryBefore.rss,
      heapTotal: memoryAfter.heapTotal - memoryBefore.heapTotal,
      heapUsed: memoryAfter.heapUsed - memoryBefore.heapUsed,
      external: memoryAfter.external - memoryBefore.external,
      arrayBuffers: memoryAfter.arrayBuffers - memoryBefore.arrayBuffers
    }
  };
};

describe('Research Tool Performance', () => {
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

  describe('timeout management', () => {
    it('should calculate complexity-based timeouts correctly', async () => {
      const complexities: ComplexityLevel[] = ['simple', 'medium', 'complex'];
      const timeouts: number[] = [];

      // Set up delayed responses to measure actual timeout behavior
      axiosMock.setResponseDelay('/api/generate', 1000);
      axiosMock.setupMocks();

      for (const complexity of complexities) {
        const request: ResearchRequest = {
          question: `Timeout test for ${complexity}`,
          complexity,
          models: ['llama3.2:1b'] // Use single model for consistent testing
        };

        const { time } = await measurePerformance(async () => {
          return await researchTool.executeResearch(request);
        });

        timeouts.push(time);
      }

      // Simple should be fastest, complex should allow more time
      expect(timeouts[0]).toBeLessThan(timeouts[2]); // simple < complex

      // All should complete within reasonable bounds
      expect(timeouts.every(t => t < 30000)).toBe(true); // < 30 seconds with mocks
    });

    it('should handle timeout escalation for different model tiers', async () => {
      const models = [
        ['llama3.2:1b'],      // Fast tier
        ['qwen2.5-coder:7b-instruct'], // Balanced tier
        ['smallthinker:latest']  // Quality tier (simulated)
      ];

      // Set moderate delay to test timeout behavior
      axiosMock.setResponseDelay('/api/generate', 2000);
      axiosMock.setupMocks();

      const results = [];

      for (const modelList of models) {
        const request: ResearchRequest = {
          question: 'Model tier timeout test',
          complexity: 'medium',
          models: modelList
        };

        const { time, result } = await measurePerformance(async () => {
          return await researchTool.executeResearch(request);
        });

        results.push({ time, success: !result.responses[0].error });
      }

      // All should succeed with appropriate timeouts
      expect(results.every(r => r.success)).toBe(true);

      // Execution times should vary based on model capabilities
      expect(results.some(r => r.time > 1000)).toBe(true);
    });

    it('should respect custom timeout parameters', async () => {
      const customTimeout = 5000; // 5 seconds

      const request: ResearchRequest = {
        question: 'Custom timeout test',
        timeout: customTimeout,
        models: ['llama3.2:1b']
      };

      // Set delay that would exceed default timeout but not custom
      axiosMock.setResponseDelay('/api/generate', 3000);
      axiosMock.setupMocks();

      const { result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(request);
      });

      // Should succeed with custom timeout
      expect(result.responses[0].error).toBeUndefined();
    });

    it('should fail appropriately when timeout exceeded', async () => {
      // Set very short timeout
      const request: ResearchRequest = {
        question: 'Timeout failure test',
        timeout: 100, // 100ms - very short
        models: ['llama3.2:1b']
      };

      // Set delay longer than timeout
      axiosMock.setResponseDelay('/api/generate', 500);
      axiosMock.setupMocks();

      const { result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(request);
      });

      // Should have timeout errors
      expect(result.responses[0].error).toContain('Timeout');
    });
  });

  describe('resource usage optimization', () => {
    it('should maintain reasonable memory usage during execution', async () => {
      const request: ResearchRequest = {
        question: 'Memory usage test - analyze the impact of AI on software development patterns',
        complexity: 'complex'
      };

      const { memory, result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(request);
      });

      expect(result).toHaveResearchResult();

      // Memory usage should be reasonable (less than 50MB increase)
      expect(memory.heapUsed).toBeLessThan(50 * 1024 * 1024);

      // RSS increase should be controlled
      expect(memory.rss).toBeLessThan(100 * 1024 * 1024);
    });

    it('should handle memory efficiently with large responses', async () => {
      // Mock large response data
      axiosMock.reset();
      const mockedAxios = require('axios');
      mockedAxios.get.mockResolvedValue({
        data: {
          models: [
            { name: 'large-model', size: 5000000000, digest: 'abc123' }
          ]
        }
      });
      mockedAxios.post.mockResolvedValue({
        data: {
          response: 'Large response content. '.repeat(1000), // ~25KB response
          done: true
        }
      });

      const request: ResearchRequest = {
        question: 'Large response memory test',
        complexity: 'complex'
      };

      const { memory, result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(request);
      });

      expect(result).toHaveResearchResult();

      // Memory should still be reasonable even with large responses
      expect(memory.heapUsed).toBeLessThan(100 * 1024 * 1024);
    });

    it('should manage CPU usage effectively in parallel execution', async () => {
      const request: ResearchRequest = {
        question: 'CPU usage test in parallel mode',
        complexity: 'medium',
        parallel: true
      };

      const startCPU = process.cpuUsage();
      const { time, result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(request);
      });
      const cpuUsage = process.cpuUsage(startCPU);

      expect(result).toHaveResearchResult();

      // Parallel execution should complete faster
      expect(time).toBeLessThan(10000); // Should be fast with mocks

      // CPU usage should be reasonable (this is approximate)
      const totalCPU = cpuUsage.user + cpuUsage.system;
      expect(totalCPU).toBeGreaterThan(0); // Should use some CPU
      expect(totalCPU).toBeLessThan(5000000); // But not excessive (5 seconds of CPU time)
    });

    it('should handle concurrent requests without resource exhaustion', async () => {
      const concurrentRequests = Array.from({ length: 5 }, (_, i) => ({
        question: `Concurrent request ${i + 1}`,
        complexity: 'simple' as ComplexityLevel
      }));

      const { memory, time, result } = await measurePerformance(async () => {
        const promises = concurrentRequests.map(req => researchTool.executeResearch(req));
        return await Promise.all(promises);
      });

      expect(result).toHaveLength(5);
      result.forEach(res => expect(res).toHaveResearchResult());

      // Memory usage should scale reasonably with concurrent requests
      expect(memory.heapUsed).toBeLessThan(150 * 1024 * 1024); // 150MB limit

      // Should complete in reasonable time
      expect(time).toBeLessThan(15000);
    });
  });

  describe('caching and optimization', () => {
    it('should benefit from model capability caching', async () => {
      const requests = Array.from({ length: 3 }, (_, i) => ({
        question: `Caching test ${i + 1}`,
        complexity: 'simple' as ComplexityLevel
      }));

      // First request - should build cache
      const { time: firstTime } = await measurePerformance(async () => {
        return await researchTool.executeResearch(requests[0]);
      });

      // Subsequent requests - should benefit from cache
      const { time: secondTime } = await measurePerformance(async () => {
        return await researchTool.executeResearch(requests[1]);
      });

      const { time: thirdTime } = await measurePerformance(async () => {
        return await researchTool.executeResearch(requests[2]);
      });

      // Later requests should be faster due to cached model capabilities
      expect(secondTime).toBeLessThanOrEqual(firstTime * 1.2); // Allow 20% variance
      expect(thirdTime).toBeLessThanOrEqual(firstTime * 1.2);
    });

    it('should optimize model selection based on performance history', async () => {
      // Execute several requests to build performance history
      const trainingRequests = Array.from({ length: 3 }, (_, i) => ({
        question: `Training request ${i + 1}`,
        complexity: 'simple' as ComplexityLevel
      }));

      // Build performance history
      for (const request of trainingRequests) {
        await researchTool.executeResearch(request);
      }

      // Test optimized selection
      const optimizedRequest: ResearchRequest = {
        question: 'Optimized selection test',
        complexity: 'simple'
      };

      const { time, result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(optimizedRequest);
      });

      expect(result).toHaveResearchResult();
      expect(time).toBeLessThan(8000); // Should be optimized
    });

    it('should handle cache invalidation appropriately', async () => {
      // Mock changing model availability
      let modelCount = 3;

      axiosMock.reset();
      const mockedAxios = require('axios');
      mockedAxios.get.mockImplementation(async () => {
        // Simulate changing model list
        const models = Array.from({ length: modelCount }, (_, i) => ({
          name: `model-${i}:latest`,
          size: 2000000000,
          digest: `sha256:${i}`.repeat(8)
        }));

        return { data: { models } };
      });
      mockedAxios.post.mockResolvedValue({
        data: { response: 'Test response', done: true }
      });

      const request: ResearchRequest = {
        question: 'Cache invalidation test',
        complexity: 'simple'
      };

      // First execution
      const result1 = await researchTool.executeResearch(request);
      expect(result1.responses).toHaveLength(3);

      // Change available models
      modelCount = 2;

      // Second execution should adapt to new model availability
      const result2 = await researchTool.executeResearch(request);
      expect(result2.responses).toHaveLength(2);
    });
  });

  describe('fallback performance', () => {
    it('should handle model failures with minimal performance impact', async () => {
      // Set up mixed success/failure scenario
      axiosMock.setBehavior('mixed');
      axiosMock.setupMocks();

      const request: ResearchRequest = {
        question: 'Fallback performance test',
        complexity: 'medium'
      };

      const { time, result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(request);
      });

      expect(result).toHaveResearchResult();

      // Should still complete quickly despite some failures
      expect(time).toBeLessThan(12000);

      // Should have both successful and failed responses
      const successes = result.responses.filter(r => !r.error);
      const failures = result.responses.filter(r => r.error);

      expect(successes.length).toBeGreaterThan(0);
      expect(failures.length).toBeGreaterThan(0);
    });

    it('should degrade gracefully under network issues', async () => {
      // Simulate intermittent network issues
      let requestCount = 0;
      axiosMock.reset();
      const mockedAxios = require('axios');

      mockedAxios.get.mockResolvedValue({
        data: {
          models: [{ name: 'test-model', size: 1000000000, digest: 'abc123' }]
        }
      });

      mockedAxios.post.mockImplementation(async () => {
        requestCount++;
        if (requestCount % 2 === 0) {
          throw new Error('Network timeout');
        }
        return {
          data: { response: 'Success response', done: true }
        };
      });

      const request: ResearchRequest = {
        question: 'Network degradation test',
        models: ['test-model']
      };

      const { time, result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(request);
      });

      expect(result).toHaveResearchResult();

      // Should handle partial failures without excessive delay
      expect(time).toBeLessThan(15000);
    });

    it('should maintain performance with sequential fallback', async () => {
      const request: ResearchRequest = {
        question: 'Sequential fallback test',
        complexity: 'medium',
        parallel: false // Force sequential execution
      };

      // Set up some response delays
      axiosMock.setResponseDelay('/api/generate', 1000);
      axiosMock.setupMocks();

      const { time, result } = await measurePerformance(async () => {
        return await researchTool.executeResearch(request);
      });

      expect(result).toHaveResearchResult();

      // Sequential execution should still complete in reasonable time
      expect(time).toBeLessThan(20000); // Allow more time for sequential
      expect(result.responses.length).toBe(3);
    });
  });

  describe('performance benchmarks', () => {
    const performanceTargets = {
      simple: { maxTime: 5000, maxMemory: 20 * 1024 * 1024 },  // 5s, 20MB
      medium: { maxTime: 8000, maxMemory: 30 * 1024 * 1024 },  // 8s, 30MB
      complex: { maxTime: 12000, maxMemory: 50 * 1024 * 1024 } // 12s, 50MB
    };

    Object.entries(performanceTargets).forEach(([complexity, targets]) => {
      it(`should meet performance targets for ${complexity} complexity`, async () => {
        const request: ResearchRequest = {
          question: `Performance benchmark test for ${complexity} complexity`,
          complexity: complexity as ComplexityLevel
        };

        const { time, memory, result } = await measurePerformance(async () => {
          return await researchTool.executeResearch(request);
        });

        expect(result).toHaveResearchResult();

        // Time benchmark
        expect(time).toBeLessThan(targets.maxTime);

        // Memory benchmark
        expect(memory.heapUsed).toBeLessThan(targets.maxMemory);

        // Quality benchmarks
        expect(result.confidence).toBeGreaterThan(0.3);
        expect(result.synthesis.length).toBeGreaterThan(50);
      });
    });

    it('should demonstrate performance scaling with parallel vs sequential', async () => {
      const baseRequest: ResearchRequest = {
        question: 'Scaling comparison test',
        complexity: 'medium'
      };

      // Test sequential execution
      const { time: sequentialTime } = await measurePerformance(async () => {
        return await researchTool.executeResearch({
          ...baseRequest,
          parallel: false
        });
      });

      // Test parallel execution
      const { time: parallelTime } = await measurePerformance(async () => {
        return await researchTool.executeResearch({
          ...baseRequest,
          parallel: true
        });
      });

      // Parallel should be faster (or at least not significantly slower)
      expect(parallelTime).toBeLessThanOrEqual(sequentialTime * 1.5);
    });

    it('should handle load testing with multiple concurrent operations', async () => {
      const concurrency = 10;
      const requests = Array.from({ length: concurrency }, (_, i) => ({
        question: `Load test request ${i + 1}`,
        complexity: 'simple' as ComplexityLevel
      }));

      const { time, memory, result } = await measurePerformance(async () => {
        const promises = requests.map(req => researchTool.executeResearch(req));
        return await Promise.allSettled(promises);
      });

      const successfulResults = result.filter(r => r.status === 'fulfilled');

      // Should handle concurrent load successfully
      expect(successfulResults.length).toBeGreaterThan(concurrency * 0.8); // 80% success rate

      // Performance should scale reasonably
      expect(time).toBeLessThan(15000); // 15 seconds max
      expect(memory.heapUsed).toBeLessThan(200 * 1024 * 1024); // 200MB max
    });
  });

  describe('health check performance', () => {
    it('should perform health checks quickly', async () => {
      const { time, result } = await measurePerformance(async () => {
        return await researchTool.healthCheck();
      });

      expect(result.status).toBe('healthy');
      expect(time).toBeLessThan(2000); // Should complete in under 2 seconds
    });

    it('should handle health check failures efficiently', async () => {
      axiosMock.setBehavior('error');
      axiosMock.setupMocks();

      const { time, result } = await measurePerformance(async () => {
        return await researchTool.healthCheck();
      });

      expect(result.status).toBe('unhealthy');
      expect(time).toBeLessThan(3000); // Should fail quickly
    });
  });
});

// Performance utility tests
describe('Performance Utilities', () => {
  it('should measure performance accurately', async () => {
    const testDelay = 100;

    const { time } = await measurePerformance(async () => {
      await new Promise(resolve => setTimeout(resolve, testDelay));
      return 'test';
    });

    // Should measure time accurately (with some tolerance for execution overhead)
    expect(time).toBeGreaterThanOrEqual(testDelay);
    expect(time).toBeLessThan(testDelay + 50); // Allow 50ms tolerance
  });

  it('should track memory usage changes', async () => {
    const { memory } = await measurePerformance(async () => {
      // Allocate some memory
      const largeArray = new Array(100000).fill('test');
      return largeArray.length;
    });

    // Should detect memory usage increase
    expect(memory.heapUsed).toBeGreaterThan(0);
  });
});