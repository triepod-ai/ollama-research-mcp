/**
 * Jest Configuration for MCP Ollama Testing Suite
 * Supports TypeScript ES modules with comprehensive coverage
 */

export default {
  // Use ts-jest preset for TypeScript support
  preset: 'ts-jest',

  // ES modules configuration
  extensionsToTreatAsEsm: ['.ts'],

  // Module resolution
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
    '^@/(.*)$': '<rootDir>/src/$1'
  },

  // Test environment
  testEnvironment: 'node',

  // Test file patterns
  testMatch: [
    '<rootDir>/tests/**/*.test.ts',
    '<rootDir>/tests/**/*.spec.ts'
  ],

  // Setup files
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],

  // Coverage configuration
  collectCoverage: true,
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html', 'json'],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/**/index.ts',
    '!coverage/**'
  ],

  // Coverage thresholds
  coverageThreshold: {
    global: {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90
    },
    './src/research-tool.ts': {
      branches: 95,
      functions: 95,
      lines: 95,
      statements: 95
    },
    './src/model-selector.ts': {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90
    },
    './src/response-analyzer.ts': {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90
    }
  },

  // Test timeouts
  testTimeout: 30000,

  // Transform configuration
  transform: {
    '^.+\\.ts$': ['ts-jest', {
      useESM: true
    }]
  },

  // Module file extensions
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],

  // Ignore patterns
  testPathIgnorePatterns: [
    '<rootDir>/node_modules/',
    '<rootDir>/build/',
    '<rootDir>/coverage/'
  ],

  // Clear mocks between tests
  clearMocks: true,

  // Verbose output for debugging
  verbose: true,

  // Test result processor for better reporting
  reporters: [
    'default',
    ['jest-html-reporters', {
      publicPath: './coverage/html-report',
      filename: 'test-report.html',
      expand: true
    }]
  ],

  // Performance monitoring
  detectLeaks: true,
  forceExit: true,

  // Global test configuration
  globals: {
    'ts-jest': {
      useESM: true,
      isolatedModules: true
    }
  }
};