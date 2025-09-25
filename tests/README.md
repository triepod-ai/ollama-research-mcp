# MCP Ollama Testing Suite

Comprehensive testing infrastructure for the MCP Ollama research tool, providing unit, integration, performance, and end-to-end testing capabilities.

## Overview

This testing suite validates all aspects of the MCP Ollama research tool functionality, ensuring reliability, performance, and robustness in production use.

### Test Categories

- **Unit Tests** (`/tests/unit/`) - Individual component testing
- **Integration Tests** (`/tests/integration/`) - Component interaction testing
- **Performance Tests** (`/tests/performance/`) - Performance validation and benchmarking
- **E2E Tests** (`/tests/e2e/`) - Real Ollama API integration testing

## Quick Start

### Prerequisites

```bash
# Install dependencies
npm install

# Build the project
npm run build
```

### Running Tests

```bash
# Run all tests
npm test

# Run specific test categories
npm run test:unit          # Unit tests only
npm run test:integration   # Integration tests only
npm run test:performance   # Performance tests only
npm run test:e2e          # End-to-end tests (requires Ollama)

# Run tests with coverage
npm run test:coverage

# Watch mode for development
npm run test:watch

# CI/CD optimized run
npm run test:ci
```

### Test Coverage Targets

- **Overall Coverage**: ≥90% (branches, functions, lines, statements)
- **Core Components**: ≥95% (research-tool.ts, model-selector.ts, response-analyzer.ts)
- **Integration**: ≥90% (MCP server integration, API integration)

## Test Structure

### Unit Tests (`/tests/unit/`)

#### ModelSelector Tests (`model-selector.test.ts`)
- **Tier Classification**: Tests model parameter estimation and tier assignment
- **Selection Algorithms**: Validates optimal model selection based on complexity/focus
- **Performance Tracking**: Tests performance history integration
- **Edge Cases**: Handles unusual model names, large sizes, unknown patterns

**Key Test Scenarios**:
```typescript
// Model tier classification
describe('parseModelCapabilities', () => {
  it('should correctly classify models by parameter count');
  it('should assign appropriate complexity levels');
});

// Model selection optimization
describe('selectModels', () => {
  it('should select optimal models for different complexity levels');
  it('should ensure model diversity when required');
});
```

#### ResponseAnalyzer Tests (`response-analyzer.test.ts`)
- **Theme Detection**: Tests convergent/divergent analysis algorithms
- **Synthesis Generation**: Validates response synthesis quality
- **Confidence Scoring**: Tests multi-factor confidence calculation
- **Complexity Adaptation**: Ensures analysis depth matches request complexity

**Key Test Scenarios**:
```typescript
// Analysis quality validation
describe('analyzeResponses', () => {
  it('should identify convergent themes across responses');
  it('should generate comprehensive synthesis from multiple responses');
});

// Confidence calculation
describe('confidence calculation', () => {
  it('should calculate confidence based on response quality');
  it('should penalize confidence when responses have errors');
});
```

#### ResearchTool Tests (`research-tool.test.ts`)
- **Core Orchestration**: Tests end-to-end research execution
- **Execution Strategies**: Validates parallel vs sequential execution
- **Error Handling**: Tests resilience and graceful degradation
- **Parameter Validation**: Ensures proper input validation

**Key Test Scenarios**:
```typescript
// Core functionality
describe('executeResearch', () => {
  it('should execute research with default parameters');
  it('should validate specific models when provided');
});

// Execution strategies
describe('execution strategies', () => {
  it('should execute queries in parallel when requested');
  it('should handle mixed success and failures gracefully');
});
```

### Integration Tests (`/tests/integration/`)

#### MCP Server Integration (`mcp-server.test.ts`)
- **Tool Registration**: Validates MCP tool schema and registration
- **Handler Execution**: Tests tool execution and response formatting
- **Error Handling**: Tests MCP error code compliance
- **Protocol Compliance**: Ensures adherence to MCP protocol standards

**Key Test Scenarios**:
```typescript
// MCP protocol validation
describe('tool registration', () => {
  it('should register all required tools');
  it('should validate research tool schema');
});

// Tool execution
describe('tool execution', () => {
  it('should execute research tool successfully');
  it('should handle unknown tools gracefully');
});
```

### Performance Tests (`/tests/performance/`)

#### Research Performance (`research-performance.test.ts`)
- **Timeout Management**: Tests complexity-based timeout calculations
- **Resource Usage**: Validates memory and CPU usage optimization
- **Caching Effectiveness**: Tests model capability caching and optimization
- **Concurrency**: Validates performance under concurrent load

**Performance Benchmarks**:
```typescript
const performanceTargets = {
  simple:  { maxTime: 5000,  maxMemory: 20MB },  // 5s, 20MB
  medium:  { maxTime: 8000,  maxMemory: 30MB },  // 8s, 30MB
  complex: { maxTime: 12000, maxMemory: 50MB }   // 12s, 50MB
};
```

**Key Test Scenarios**:
```typescript
// Performance benchmarks
describe('performance benchmarks', () => {
  it('should meet performance targets for each complexity level');
  it('should demonstrate scaling with parallel vs sequential');
});

// Resource optimization
describe('resource usage', () => {
  it('should maintain reasonable memory usage during execution');
  it('should handle concurrent requests without resource exhaustion');
});
```

### End-to-End Tests (`/tests/e2e/`)

#### Ollama API Integration (`ollama-integration.test.ts`)
- **Real API Testing**: Tests against actual Ollama instance
- **Model Availability**: Validates real model discovery and usage
- **Performance Validation**: Tests real-world response times
- **Error Scenarios**: Tests actual API failure handling

**Requirements**:
- Running Ollama instance
- At least one model installed (e.g., `ollama pull llama3.2:1b`)
- Network connectivity to Ollama API

**Key Test Scenarios**:
```typescript
// Real API integration
describe('Real Ollama API Integration', () => {
  it('should connect to Ollama and list models');
  it('should execute multi-model research');
});

// Performance validation
describe('Performance with Real API', () => {
  it('should complete simple queries within reasonable time');
  it('should handle multiple concurrent requests');
});
```

## Test Configuration

### Jest Configuration (`jest.config.js`)
- **TypeScript Support**: ES modules with ts-jest preset
- **Coverage Reporting**: HTML, LCOV, and text formats
- **Custom Matchers**: Research-specific validation matchers
- **Performance Monitoring**: Memory leak detection and timeout management

### Test Setup (`tests/setup.ts`)
- **Global Configuration**: Test environment and timeouts
- **Custom Matchers**: Domain-specific assertions
- **Mock Data**: Realistic test fixtures
- **Utility Functions**: Common test helpers

### Mock Framework (`tests/mocks/axios-mock.ts`)
- **Axios Mocking**: Comprehensive API response mocking
- **Behavior Control**: Success/error/timeout scenario simulation
- **Response Delays**: Configurable timing simulation
- **Factory Pattern**: Reusable mock configurations

## Running Tests

### Development Workflow

```bash
# Development cycle
npm run test:watch          # Continuous testing during development
npm run test:unit          # Quick unit test validation
npm run lint               # TypeScript type checking
npm run test:coverage      # Coverage analysis

# Before committing
npm run test:all           # Unit, integration, performance
npm run test:ci           # CI/CD validation
```

### CI/CD Integration

```bash
# Automated testing pipeline
npm run test:ci           # Optimized for CI environments
npm run test:coverage     # Generate coverage reports
npm run test:all         # Comprehensive testing
```

### E2E Testing Setup

```bash
# Install and setup Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve

# Pull test models
ollama pull llama3.2:1b    # Fast model for testing
ollama pull qwen2.5-coder:7b-instruct  # Balanced model

# Run E2E tests
npm run test:e2e
```

## Test Data and Fixtures

### Mock Models (`tests/setup.ts`)
```typescript
export const mockModels = [
  {
    name: 'llama3.2:1b',
    size: 1234567890,
    digest: 'sha256:abcd1234'
  },
  // Additional test models...
];
```

### Research Requests (`tests/setup.ts`)
```typescript
export const mockResearchRequest = {
  question: 'What is the impact of AI on software development?',
  complexity: 'medium',
  focus: 'technical',
  parallel: false,
  temperature: 0.7
};
```

### API Responses (`tests/mocks/axios-mock.ts`)
```typescript
export const mockResponses = {
  research: {
    simple: { data: { response: 'Brief AI response...' }},
    medium: { data: { response: 'Detailed AI analysis...' }},
    complex: { data: { response: 'Comprehensive AI study...' }}
  }
};
```

## Debugging Tests

### Debug Mode
```bash
# Run tests in debug mode
npm run test:debug

# Debug specific test file
npx jest --runInBand tests/unit/research-tool.test.ts
```

### Verbose Output
```bash
# Detailed test output
npx jest --verbose

# Watch specific pattern
npx jest --watch --testNamePattern="model selection"
```

### Coverage Analysis
```bash
# Generate coverage report
npm run test:coverage

# View HTML report
open coverage/lcov-report/index.html
```

## Performance Monitoring

### Memory Usage Tracking
```typescript
const measurePerformance = async (fn) => {
  const memoryBefore = process.memoryUsage();
  const result = await fn();
  const memoryAfter = process.memoryUsage();
  return { result, memory: memoryAfter.heapUsed - memoryBefore.heapUsed };
};
```

### Execution Time Monitoring
```typescript
const { time, result } = await measurePerformance(async () => {
  return await researchTool.executeResearch(request);
});
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run test:ci
      - run: npm run test:performance
```

### Coverage Reporting
- **Threshold Enforcement**: Build fails if coverage drops below targets
- **Trend Tracking**: Monitor coverage changes over time
- **Report Generation**: Automated coverage report generation

## Best Practices

### Writing Tests
1. **Descriptive Names**: Use clear, specific test descriptions
2. **Single Responsibility**: Each test should validate one specific behavior
3. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and validation
4. **Independent Tests**: Tests should not depend on each other
5. **Realistic Data**: Use representative test data and scenarios

### Mock Usage
1. **Selective Mocking**: Mock external dependencies, test internal logic
2. **Realistic Responses**: Mock data should reflect actual API behavior
3. **Error Scenarios**: Test both success and failure cases
4. **Performance Simulation**: Include realistic timing and delays

### Performance Testing
1. **Baseline Establishment**: Define clear performance benchmarks
2. **Resource Monitoring**: Track memory, CPU, and execution time
3. **Concurrency Testing**: Validate performance under load
4. **Regression Prevention**: Monitor for performance degradation

## Troubleshooting

### Common Issues

**Jest ES Module Errors**
```bash
# Ensure proper ES module configuration
# Check jest.config.js extensionsToTreatAsEsm setting
```

**Timeout Issues**
```bash
# Increase timeout for slow operations
npx jest --testTimeout=60000
```

**Mock Conflicts**
```bash
# Reset mocks between tests
axiosMock.reset(); // in beforeEach
```

**E2E Test Failures**
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check available models
ollama list
```

### Debugging Failed Tests
1. **Isolate Test**: Run single test to focus debugging
2. **Add Logging**: Use console.log for state inspection
3. **Check Mocks**: Verify mock setup and behavior
4. **Validate Data**: Ensure test data matches expected format

## Contributing

### Adding New Tests
1. **Follow Patterns**: Use existing test structure and conventions
2. **Add Coverage**: Ensure new features have comprehensive test coverage
3. **Update Documentation**: Update this README for new test categories
4. **Performance Impact**: Consider performance implications of new tests

### Test Maintenance
1. **Regular Review**: Periodically review and update test scenarios
2. **Flaky Test Resolution**: Address and fix unreliable tests promptly
3. **Performance Monitoring**: Track test execution time and optimize slow tests
4. **Coverage Maintenance**: Maintain high coverage standards as code evolves