/**
 * Axios Mock Configuration for Testing
 * Provides comprehensive mocking of Ollama API responses
 */

import axios, { AxiosResponse, AxiosError } from 'axios';
import { jest } from '@jest/globals';
import { mockModels, mockModelResponse } from '../setup.js';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Response templates
export const mockResponses = {
  // Successful model list
  modelList: {
    data: {
      models: mockModels
    },
    status: 200,
    statusText: 'OK'
  } as AxiosResponse,

  // Successful generate response
  generate: {
    data: mockModelResponse,
    status: 200,
    statusText: 'OK'
  } as AxiosResponse,

  // Model show response
  modelShow: {
    data: {
      license: 'MIT',
      modelfile: 'FROM llama3.2:1b\nSYSTEM "You are a helpful assistant."',
      parameters: 'num_predict=2048\ntemperature=0.7',
      template: '{{ if .System }}<|start_header_id|>system<|end_header_id|>\n\n{{ .System }}<|eot_id|>{{ end }}{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>\n\n{{ .Prompt }}<|eot_id|>{{ end }}<|start_header_id|>assistant<|end_header_id|>\n\n',
      details: {
        format: 'gguf',
        family: 'llama',
        families: ['llama'],
        parameter_size: '1B',
        quantization_level: 'Q4_0'
      }
    },
    status: 200,
    statusText: 'OK'
  } as AxiosResponse,

  // Different model responses for research testing
  research: {
    simple: {
      data: {
        model: 'llama3.2:1b',
        response: 'AI improves software development through automation and code assistance.',
        done: true
      }
    },
    medium: {
      data: {
        model: 'qwen2.5-coder:7b-instruct',
        response: 'Artificial intelligence significantly impacts software development by automating routine tasks, providing intelligent code completion, detecting bugs early, and enabling better testing strategies. However, it also raises concerns about job displacement and code quality dependencies.',
        done: true
      }
    },
    complex: {
      data: {
        model: 'smallthinker:latest',
        response: 'The impact of artificial intelligence on software development is multifaceted and transformative. On the positive side, AI tools like GitHub Copilot and CodeT5 have revolutionized code generation, reducing development time by 25-40% according to recent studies. Machine learning algorithms enhance testing through predictive bug detection and automated test case generation. Furthermore, AI-driven analytics provide insights into code quality, performance bottlenecks, and maintenance requirements. However, this technological shift also presents challenges: over-reliance on AI tools may diminish fundamental programming skills, introduce subtle bugs that are harder to detect, and create security vulnerabilities through automatically generated code. The long-term implications suggest a paradigm shift toward AI-assisted development rather than AI replacement of developers, emphasizing the need for continuous learning and adaptation in the software engineering profession.',
        done: true
      }
    }
  }
};

// Error responses
export const mockErrors = {
  networkError: new AxiosError('Network Error', 'ECONNREFUSED'),
  timeoutError: new AxiosError('Timeout', 'ECONNABORTED'),
  modelNotFound: {
    response: {
      data: { error: 'model not found' },
      status: 404
    }
  } as AxiosError,
  internalServerError: {
    response: {
      data: { error: 'internal server error' },
      status: 500
    }
  } as AxiosError
};

// Mock implementation factory
export class AxiosMockFactory {
  private static instance: AxiosMockFactory;
  private mockBehavior: 'success' | 'error' | 'timeout' | 'mixed' = 'success';
  private responseDelays: Map<string, number> = new Map();

  static getInstance(): AxiosMockFactory {
    if (!AxiosMockFactory.instance) {
      AxiosMockFactory.instance = new AxiosMockFactory();
    }
    return AxiosMockFactory.instance;
  }

  setBehavior(behavior: 'success' | 'error' | 'timeout' | 'mixed'): void {
    this.mockBehavior = behavior;
  }

  setResponseDelay(endpoint: string, delay: number): void {
    this.responseDelays.set(endpoint, delay);
  }

  setupMocks(): void {
    // Mock axios.get for /api/tags
    mockedAxios.get.mockImplementation(async (url: string) => {
      const delay = this.responseDelays.get(url) || 0;
      if (delay > 0) {
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      if (url.includes('/api/tags')) {
        switch (this.mockBehavior) {
          case 'error':
            throw mockErrors.networkError;
          case 'timeout':
            throw mockErrors.timeoutError;
          default:
            return mockResponses.modelList;
        }
      }

      throw new Error(`Unmocked GET request: ${url}`);
    });

    // Mock axios.post for /api/generate and /api/show
    mockedAxios.post.mockImplementation(async (url: string, data?: any) => {
      const delay = this.responseDelays.get(url) || 0;
      if (delay > 0) {
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      if (url.includes('/api/generate')) {
        switch (this.mockBehavior) {
          case 'error':
            throw mockErrors.internalServerError;
          case 'timeout':
            throw mockErrors.timeoutError;
          case 'mixed':
            // Return different responses based on model
            if (data?.model?.includes('1b')) {
              return { data: mockResponses.research.simple.data };
            } else if (data?.model?.includes('7b')) {
              return { data: mockResponses.research.medium.data };
            } else {
              return { data: mockResponses.research.complex.data };
            }
          default:
            // Return response based on model complexity
            if (data?.model?.includes('1b')) {
              return { data: mockResponses.research.simple.data };
            } else if (data?.model?.includes('7b')) {
              return { data: mockResponses.research.medium.data };
            }
            return { data: mockResponses.research.complex.data };
        }
      }

      if (url.includes('/api/show')) {
        switch (this.mockBehavior) {
          case 'error':
            throw mockErrors.modelNotFound;
          case 'timeout':
            throw mockErrors.timeoutError;
          default:
            return mockResponses.modelShow;
        }
      }

      throw new Error(`Unmocked POST request: ${url}`);
    });
  }

  reset(): void {
    this.mockBehavior = 'success';
    this.responseDelays.clear();
    mockedAxios.get.mockReset();
    mockedAxios.post.mockReset();
  }
}

// Export singleton instance
export const axiosMock = AxiosMockFactory.getInstance();