/**
 * Unit Tests for ModelSelector
 * Tests model tier classification, selection algorithms, and performance tracking
 */

import { jest } from '@jest/globals';
import { ModelSelector } from '../../src/model-selector.js';
import type { ModelCapabilities, ComplexityLevel, ResearchFocus } from '../../src/research-types.js';

describe('ModelSelector', () => {
  let modelSelector: ModelSelector;
  let mockModels: any[];

  beforeEach(() => {
    modelSelector = new ModelSelector();

    mockModels = [
      {
        name: 'llama3.2:1b',
        size: 1.2 * 1024 * 1024 * 1024, // 1.2GB
        digest: 'sha256:abcd1234',
        modified_at: new Date().toISOString()
      },
      {
        name: 'qwen2.5-coder:7b-instruct',
        size: 4.5 * 1024 * 1024 * 1024, // 4.5GB
        digest: 'sha256:efgh5678',
        modified_at: new Date().toISOString()
      },
      {
        name: 'llama3.1:70b',
        size: 40 * 1024 * 1024 * 1024, // 40GB
        digest: 'sha256:ijkl9012',
        modified_at: new Date().toISOString()
      },
      {
        name: 'codellama:34b',
        size: 18 * 1024 * 1024 * 1024, // 18GB
        digest: 'sha256:mnop3456',
        modified_at: new Date().toISOString()
      }
    ];
  });

  describe('parseModelCapabilities', () => {
    it('should correctly parse model capabilities with tier classification', () => {
      const capabilities = modelSelector.parseModelCapabilities(mockModels);

      expect(capabilities).toHaveLength(4);

      // Test small model (1B)
      const smallModel = capabilities.find(m => m.name === 'llama3.2:1b');
      expect(smallModel).toBeDefined();
      expect(smallModel!.tier.name).toBe('fast');
      expect(smallModel!.tier.timeoutMultiplier).toBe(1.0);
      expect(smallModel!.complexity).toContain('simple');
      expect(smallModel!.focus).toContain('general');

      // Test medium model (7B)
      const mediumModel = capabilities.find(m => m.name === 'qwen2.5-coder:7b-instruct');
      expect(mediumModel).toBeDefined();
      expect(mediumModel!.tier.name).toBe('balanced');
      expect(mediumModel!.tier.timeoutMultiplier).toBe(1.5);
      expect(mediumModel!.complexity).toContain('medium');
      expect(mediumModel!.focus).toContain('technical');

      // Test large model (70B)
      const largeModel = capabilities.find(m => m.name === 'llama3.1:70b');
      expect(largeModel).toBeDefined();
      expect(largeModel!.tier.name).toBe('quality');
      expect(largeModel!.tier.timeoutMultiplier).toBe(3.0);
      expect(largeModel!.complexity).toContain('complex');
    });

    it('should handle empty model list', () => {
      const capabilities = modelSelector.parseModelCapabilities([]);
      expect(capabilities).toHaveLength(0);
    });

    it('should handle malformed model data gracefully', () => {
      const malformedModels = [
        { name: 'valid-model:1b', size: 1000000000 },
        { name: '', size: 0 }, // Invalid name
        { size: 5000000000 }, // Missing name
        null,
        undefined
      ];

      const capabilities = modelSelector.parseModelCapabilities(malformedModels);
      expect(capabilities.length).toBeGreaterThanOrEqual(1); // Only valid model should be included
      expect(capabilities[0].name).toBe('valid-model:1b');
    });
  });

  describe('selectModels', () => {
    let availableModels: ModelCapabilities[];

    beforeEach(() => {
      availableModels = modelSelector.parseModelCapabilities(mockModels);
    });

    it('should select optimal models for simple complexity', async () => {
      const criteria = {
        complexity: 'simple' as ComplexityLevel,
        focus: 'general' as ResearchFocus,
        availableModels,
        preferredCount: 3,
        requireDiversity: true,
        maxTimeout: 60000
      };

      const strategy = await modelSelector.selectModels(criteria);

      expect(strategy.primary).toBeDefined();
      expect(strategy.secondary).toBeDefined();
      expect(strategy.tertiary).toBeDefined();

      // Should prefer fast models for simple complexity
      expect(strategy.primary!.tier.name).toBe('fast');
    });

    it('should select optimal models for complex complexity', async () => {
      const criteria = {
        complexity: 'complex' as ComplexityLevel,
        focus: 'technical' as ResearchFocus,
        availableModels,
        preferredCount: 3,
        requireDiversity: true,
        maxTimeout: 300000
      };

      const strategy = await modelSelector.selectModels(criteria);

      expect(strategy.primary).toBeDefined();

      // Should prefer quality models for complex tasks
      const primaryTier = strategy.primary!.tier.name;
      expect(['balanced', 'quality']).toContain(primaryTier);
    });

    it('should handle technical focus by preferring coding models', async () => {
      const criteria = {
        complexity: 'medium' as ComplexityLevel,
        focus: 'technical' as ResearchFocus,
        availableModels,
        preferredCount: 3,
        requireDiversity: true,
        maxTimeout: 120000
      };

      const strategy = await modelSelector.selectModels(criteria);

      // Should prefer models with coding capabilities
      const hasCodingModel = [strategy.primary, strategy.secondary, strategy.tertiary]
        .some(model => model?.name.includes('coder') || model?.name.includes('code'));
      expect(hasCodingModel).toBe(true);
    });

    it('should ensure model diversity when required', async () => {
      const criteria = {
        complexity: 'medium' as ComplexityLevel,
        focus: 'general' as ResearchFocus,
        availableModels,
        preferredCount: 3,
        requireDiversity: true,
        maxTimeout: 120000
      };

      const strategy = await modelSelector.selectModels(criteria);

      const selectedModels = [strategy.primary, strategy.secondary, strategy.tertiary]
        .filter(Boolean);

      // All models should be different
      const modelNames = selectedModels.map(m => m!.name);
      const uniqueNames = new Set(modelNames);
      expect(uniqueNames.size).toBe(modelNames.length);

      // Should have different tiers for diversity
      const tiers = selectedModels.map(m => m!.tier.name);
      const uniqueTiers = new Set(tiers);
      expect(uniqueTiers.size).toBeGreaterThan(1);
    });

    it('should handle insufficient available models', async () => {
      const limitedModels = availableModels.slice(0, 1); // Only one model

      const criteria = {
        complexity: 'medium' as ComplexityLevel,
        focus: 'general' as ResearchFocus,
        availableModels: limitedModels,
        preferredCount: 3,
        requireDiversity: true,
        maxTimeout: 120000
      };

      const strategy = await modelSelector.selectModels(criteria);

      expect(strategy.primary).toBeDefined();
      expect(strategy.secondary).toBeNull();
      expect(strategy.tertiary).toBeNull();
    });

    it('should respect timeout constraints in model selection', async () => {
      const shortTimeout = 30000; // 30 seconds

      const criteria = {
        complexity: 'complex' as ComplexityLevel,
        focus: 'general' as ResearchFocus,
        availableModels,
        preferredCount: 3,
        requireDiversity: true,
        maxTimeout: shortTimeout
      };

      const strategy = await modelSelector.selectModels(criteria);

      // Should prefer faster models when timeout is constrained
      expect(strategy.primary!.tier.timeoutMultiplier).toBeLessThanOrEqual(2.0);
    });
  });

  describe('updatePerformanceHistory', () => {
    it('should track performance history for models', () => {
      const modelName = 'llama3.2:1b';
      const responseTime1 = 2000;
      const responseTime2 = 3000;

      modelSelector.updatePerformanceHistory(modelName, responseTime1);
      modelSelector.updatePerformanceHistory(modelName, responseTime2);

      // Performance history should be tracked internally
      // We can't directly test private methods, but we can test the effect
      // on model selection by providing multiple data points
      const availableModels = modelSelector.parseModelCapabilities(mockModels);

      expect(availableModels.find(m => m.name === modelName)).toBeDefined();
    });

    it('should handle invalid performance data', () => {
      expect(() => {
        modelSelector.updatePerformanceHistory('', 1000);
        modelSelector.updatePerformanceHistory('valid-model', -1000);
        modelSelector.updatePerformanceHistory('valid-model', NaN);
      }).not.toThrow();
    });
  });

  describe('model tier classification', () => {
    it('should classify models by parameter count correctly', () => {
      const capabilities = modelSelector.parseModelCapabilities(mockModels);

      // Test tier assignments
      const fastModels = capabilities.filter(m => m.tier.name === 'fast');
      const balancedModels = capabilities.filter(m => m.tier.name === 'balanced');
      const qualityModels = capabilities.filter(m => m.tier.name === 'quality');

      expect(fastModels.length).toBeGreaterThan(0);
      expect(balancedModels.length).toBeGreaterThan(0);
      expect(qualityModels.length).toBeGreaterThan(0);

      // Verify parameter estimation
      fastModels.forEach(model => {
        expect(model.parameters).toBeLessThanOrEqual(3000000000); // <= 3B
      });

      qualityModels.forEach(model => {
        expect(model.parameters).toBeGreaterThan(15000000000); // > 15B
      });
    });

    it('should assign appropriate complexity levels to models', () => {
      const capabilities = modelSelector.parseModelCapabilities(mockModels);

      capabilities.forEach(model => {
        expect(model.complexity.length).toBeGreaterThan(0);
        model.complexity.forEach(level => {
          expect(level).toBeComplexityLevel();
        });
      });
    });

    it('should assign focus areas based on model names', () => {
      const capabilities = modelSelector.parseModelCapabilities(mockModels);

      const codingModel = capabilities.find(m => m.name.includes('coder'));
      expect(codingModel?.focus).toContain('technical');

      const generalModel = capabilities.find(m => m.name.includes('llama'));
      expect(generalModel?.focus).toContain('general');
    });
  });

  describe('edge cases and error handling', () => {
    it('should handle models with unusual naming patterns', () => {
      const unusualModels = [
        { name: 'custom-model_v2.0', size: 2000000000 },
        { name: 'model.with.dots:latest', size: 5000000000 },
        { name: 'UPPERCASE-MODEL:1B', size: 1000000000 }
      ];

      const capabilities = modelSelector.parseModelCapabilities(unusualModels);
      expect(capabilities).toHaveLength(3);
      capabilities.forEach(model => {
        expect(model.tier).toBeDefined();
        expect(model.complexity.length).toBeGreaterThan(0);
        expect(model.focus.length).toBeGreaterThan(0);
      });
    });

    it('should handle very large model sizes', () => {
      const largeModels = [
        { name: 'huge-model:405b', size: 200 * 1024 * 1024 * 1024 } // 200GB
      ];

      const capabilities = modelSelector.parseModelCapabilities(largeModels);
      expect(capabilities[0].tier.name).toBe('quality');
      expect(capabilities[0].tier.timeoutMultiplier).toBeGreaterThan(2.0);
    });

    it('should provide fallback for unknown model patterns', () => {
      const unknownModels = [
        { name: 'completely-unknown-model', size: 3000000000 }
      ];

      const capabilities = modelSelector.parseModelCapabilities(unknownModels);
      expect(capabilities[0].tier).toBeDefined();
      expect(capabilities[0].complexity).toContain('medium'); // Should default to medium
      expect(capabilities[0].focus).toContain('general'); // Should default to general
    });
  });

  describe('performance optimization', () => {
    it('should prefer models with better historical performance', async () => {
      // Simulate performance history
      modelSelector.updatePerformanceHistory('llama3.2:1b', 1000); // Fast
      modelSelector.updatePerformanceHistory('qwen2.5-coder:7b-instruct', 5000); // Slow

      const availableModels = modelSelector.parseModelCapabilities(mockModels);
      const criteria = {
        complexity: 'simple' as ComplexityLevel,
        focus: 'general' as ResearchFocus,
        availableModels,
        preferredCount: 3,
        requireDiversity: false, // Don't require diversity for this test
        maxTimeout: 60000
      };

      const strategy = await modelSelector.selectModels(criteria);

      // Should prefer the faster model based on historical performance
      expect(strategy.primary!.name).toBe('llama3.2:1b');
    });

    it('should balance performance history with model capabilities', async () => {
      const availableModels = modelSelector.parseModelCapabilities(mockModels);

      // Even with good performance, shouldn't select inappropriate model for complex tasks
      modelSelector.updatePerformanceHistory('llama3.2:1b', 500); // Very fast but small

      const criteria = {
        complexity: 'complex' as ComplexityLevel,
        focus: 'technical' as ResearchFocus,
        availableModels,
        preferredCount: 3,
        requireDiversity: true,
        maxTimeout: 300000
      };

      const strategy = await modelSelector.selectModels(criteria);

      // Should still prefer capable models for complex tasks despite performance history
      expect(['balanced', 'quality']).toContain(strategy.primary!.tier.name);
    });
  });
});