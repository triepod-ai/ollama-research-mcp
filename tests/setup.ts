/**
 * Global Test Setup Configuration
 * Initializes testing environment, mocks, and utilities
 */

import { jest } from '@jest/globals';

// Extend Jest matchers
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeValidTimeout(): R;
      toHaveValidModelResponse(): R;
      toBeComplexityLevel(): R;
      toHaveResearchResult(): R;
    }
  }
}

// Global test timeout
jest.setTimeout(30000);

// Mock console methods to reduce noise in tests
const originalConsoleWarn = console.warn;
const originalConsoleLog = console.log;

beforeAll(() => {
  console.warn = jest.fn();
  console.log = jest.fn();
});

afterAll(() => {
  console.warn = originalConsoleWarn;
  console.log = originalConsoleLog;
});

// Custom matchers for research tool testing
expect.extend({
  toBeValidTimeout(received: number) {
    const pass = received >= 1000 && received <= 600000;
    return {
      message: () =>
        `expected ${received} to be a valid timeout (1000-600000ms)`,
      pass,
    };
  },

  toHaveValidModelResponse(received: any) {
    const hasRequiredFields =
      typeof received.model === 'string' &&
      typeof received.response === 'string' &&
      typeof received.responseTime === 'number' &&
      typeof received.tokenCount === 'number' &&
      typeof received.confidence === 'number';

    const validConfidence = received.confidence >= 0 && received.confidence <= 1;
    const validResponseTime = received.responseTime >= 0;
    const validTokenCount = received.tokenCount >= 0;

    const pass = hasRequiredFields && validConfidence && validResponseTime && validTokenCount;

    return {
      message: () =>
        `expected ${JSON.stringify(received)} to be a valid model response`,
      pass,
    };
  },

  toBeComplexityLevel(received: string) {
    const validLevels = ['simple', 'medium', 'complex'];
    const pass = validLevels.includes(received);

    return {
      message: () =>
        `expected ${received} to be a valid complexity level (${validLevels.join(', ')})`,
      pass,
    };
  },

  toHaveResearchResult(received: any) {
    const hasRequiredFields =
      typeof received.question === 'string' &&
      Array.isArray(received.responses) &&
      Array.isArray(received.convergentThemes) &&
      Array.isArray(received.divergentPerspectives) &&
      typeof received.synthesis === 'string' &&
      typeof received.confidence === 'number' &&
      typeof received.executionTime === 'number';

    const pass = hasRequiredFields;

    return {
      message: () =>
        `expected ${JSON.stringify(received)} to be a valid research result`,
      pass,
    };
  }
});

// Global error handler for unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Environment variables for testing
process.env.NODE_ENV = 'test';
process.env.OLLAMA_HOST = process.env.OLLAMA_HOST || 'http://127.0.0.1:11434';

// Export test utilities
export const testConfig = {
  OLLAMA_HOST: process.env.OLLAMA_HOST,
  DEFAULT_TIMEOUT: 30000,
  FAST_TIMEOUT: 5000,
  SLOW_TIMEOUT: 60000
};

export const mockModels = [
  {
    name: 'llama3.2:1b',
    size: 1234567890,
    digest: 'sha256:abcd1234',
    modified_at: new Date().toISOString()
  },
  {
    name: 'qwen2.5-coder:7b-instruct',
    size: 4567890123,
    digest: 'sha256:efgh5678',
    modified_at: new Date().toISOString()
  },
  {
    name: 'smallthinker:latest',
    size: 2345678901,
    digest: 'sha256:ijkl9012',
    modified_at: new Date().toISOString()
  }
];

export const mockModelResponse = {
  model: 'test-model',
  created_at: new Date().toISOString(),
  response: 'Test response content',
  done: true
};

export const mockResearchRequest = {
  question: 'What is the impact of artificial intelligence on software development?',
  complexity: 'medium' as const,
  focus: 'technical' as const,
  parallel: false,
  include_metadata: false,
  temperature: 0.7
};