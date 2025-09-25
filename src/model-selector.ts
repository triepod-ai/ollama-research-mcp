/**
 * Intelligent Model Selection Algorithm for MCP Ollama Research Tool
 * Implements dynamic model detection, tier-based selection, and fallback strategies
 */

import {
  ModelCapabilities,
  ModelTier,
  ComplexityLevel,
  ResearchFocus,
  ModelSelectionCriteria,
  SelectionStrategy,
  MODEL_TIERS,
  FOCUS_PREFERENCES,
  COMPLEXITY_TIMEOUTS
} from './research-types.js';

export class ModelSelector {
  private modelCache: Map<string, ModelCapabilities> = new Map();
  private performanceHistory: Map<string, number[]> = new Map();

  /**
   * Parse model information from Ollama API response and classify capabilities
   */
  parseModelCapabilities(rawModels: any[]): ModelCapabilities[] {
    return rawModels.map(model => {
      const sizeGB = model.size / (1024 * 1024 * 1024);
      const parameters = this.estimateParameters(sizeGB);
      const tier = this.classifyModelTier(parameters);

      return {
        name: model.name,
        size: model.size,
        parameters: this.formatParameters(parameters),
        contextWindow: this.estimateContextWindow(model.name, parameters),
        quantization: model.details?.quantization_level || 'unknown',
        modifiedAt: model.modified_at,
        tier,
        complexity: tier.complexitySupport,
        specializations: this.detectSpecializations(model.name),
        averageResponseTime: this.getAverageResponseTime(model.name),
        reliability: this.calculateReliability(model.name)
      };
    });
  }

  /**
   * Select optimal 3 models based on criteria with intelligent fallback
   */
  async selectModels(criteria: ModelSelectionCriteria): Promise<SelectionStrategy> {
    const { complexity, focus, availableModels, preferredCount, requireDiversity, maxTimeout } = criteria;

    // Filter models by complexity support
    const compatibleModels = availableModels.filter(model =>
      model.complexity.includes(complexity) &&
      this.estimateTimeout(model, complexity) <= maxTimeout
    );

    if (compatibleModels.length === 0) {
      throw new Error(`No compatible models found for complexity: ${complexity}`);
    }

    // Apply focus-based scoring
    const scoredModels = this.scoreModelsByFocus(compatibleModels, focus, complexity);

    // Select diverse set of models
    const selectedModels = this.selectDiverseModels(
      scoredModels,
      Math.min(preferredCount, compatibleModels.length),
      requireDiversity
    );

    // Build selection strategy with fallbacks
    const strategy: SelectionStrategy = {
      primary: selectedModels[0],
      secondary: selectedModels[1] || selectedModels[0],
      tertiary: selectedModels[2] || selectedModels[1] || selectedModels[0],
      fallbacks: this.buildFallbackChain(compatibleModels, selectedModels),
      reasoning: this.generateSelectionReasoning(selectedModels, criteria),
      estimatedTime: this.estimateStrategyTime(selectedModels, complexity)
    };

    return strategy;
  }

  private estimateParameters(sizeGB: number): number {
    // Heuristic: typical model size to parameter ratio
    // Accounts for quantization and model architecture
    if (sizeGB < 1) return 0.5;
    if (sizeGB < 2) return 1;
    if (sizeGB < 4) return 3;
    if (sizeGB < 8) return 7;
    if (sizeGB < 15) return 13;
    if (sizeGB < 30) return 30;
    if (sizeGB < 50) return 70;
    if (sizeGB < 100) return 180;
    return 480; // Assume cloud-tier for very large models
  }

  private formatParameters(params: number): string {
    if (params < 1) return `${Math.round(params * 1000)}M`;
    if (params < 1000) return `${params}B`;
    return `${Math.round(params / 1000)}T`;
  }

  private classifyModelTier(parameters: number): ModelTier {
    for (const tier of Object.values(MODEL_TIERS)) {
      if (parameters >= tier.minParams && parameters <= tier.maxParams) {
        return tier;
      }
    }
    return MODEL_TIERS.fast; // Default fallback
  }

  private estimateContextWindow(modelName: string, parameters: number): number {
    // Known model patterns
    if (modelName.includes('llama3.2')) return 128000;
    if (modelName.includes('qwen2.5')) return 32768;
    if (modelName.includes('mistral')) return 32768;
    if (modelName.includes('codellama')) return 16384;
    if (modelName.includes('gemma2')) return 8192;

    // Parameter-based estimation
    if (parameters >= 70) return 32768;
    if (parameters >= 13) return 16384;
    if (parameters >= 7) return 8192;
    return 4096;
  }

  private detectSpecializations(modelName: string): string[] {
    const specializations: string[] = [];
    const name = modelName.toLowerCase();

    if (name.includes('code') || name.includes('coder')) specializations.push('coding');
    if (name.includes('instruct') || name.includes('chat')) specializations.push('instruction-following');
    if (name.includes('math')) specializations.push('mathematics');
    if (name.includes('reason')) specializations.push('reasoning');
    if (name.includes('creative') || name.includes('story')) specializations.push('creative-writing');

    return specializations.length > 0 ? specializations : ['general'];
  }

  private getAverageResponseTime(modelName: string): number {
    const history = this.performanceHistory.get(modelName);
    if (!history || history.length === 0) {
      // Estimate based on typical model performance
      if (modelName.includes('1b') || modelName.includes('0.5b')) return 2000;
      if (modelName.includes('3b') || modelName.includes('7b')) return 5000;
      if (modelName.includes('13b')) return 8000;
      if (modelName.includes('30b') || modelName.includes('70b')) return 15000;
      return 10000; // Default
    }
    return history.reduce((sum, time) => sum + time, 0) / history.length;
  }

  private calculateReliability(modelName: string): number {
    // Based on community feedback and stability metrics
    const reliabilityScores: Record<string, number> = {
      'llama3.2': 0.95,
      'qwen2.5': 0.92,
      'mistral': 0.90,
      'gemma2': 0.88,
      'codellama': 0.85
    };

    for (const [pattern, score] of Object.entries(reliabilityScores)) {
      if (modelName.includes(pattern)) return score;
    }
    return 0.80; // Default reliability
  }

  private scoreModelsByFocus(
    models: ModelCapabilities[],
    focus: ResearchFocus,
    complexity: ComplexityLevel
  ): Array<ModelCapabilities & { score: number }> {
    const focusPreferences = FOCUS_PREFERENCES[focus];

    return models.map(model => {
      let score = 0;

      // Focus alignment score (40%)
      const focusScore = this.calculateFocusScore(model.name, focusPreferences);
      score += focusScore * 0.4;

      // Complexity appropriateness (25%)
      const complexityScore = this.calculateComplexityScore(model, complexity);
      score += complexityScore * 0.25;

      // Performance and reliability (20%)
      const performanceScore = this.calculatePerformanceScore(model);
      score += performanceScore * 0.2;

      // Specialization bonus (15%)
      const specializationScore = this.calculateSpecializationScore(model, focus);
      score += specializationScore * 0.15;

      return { ...model, score };
    }).sort((a, b) => b.score - a.score);
  }

  private calculateFocusScore(modelName: string, preferences: string[]): number {
    const name = modelName.toLowerCase();
    for (let i = 0; i < preferences.length; i++) {
      if (name.includes(preferences[i].toLowerCase())) {
        return 1 - (i * 0.2); // Decreasing score by preference order
      }
    }
    return 0.3; // Base score for unlisted models
  }

  private calculateComplexityScore(model: ModelCapabilities, complexity: ComplexityLevel): number {
    const tierComplexityMap = {
      simple: { cloud: 0.7, large: 0.9, fast: 1.0 },
      medium: { cloud: 0.9, large: 1.0, fast: 0.7 },
      complex: { cloud: 1.0, large: 0.8, fast: 0.3 }
    };
    return tierComplexityMap[complexity][model.tier.name] || 0.5;
  }

  private calculatePerformanceScore(model: ModelCapabilities): number {
    // Normalize response time (lower is better)
    const timeScore = Math.max(0, 1 - (model.averageResponseTime / 30000));
    return (timeScore * 0.6) + (model.reliability * 0.4);
  }

  private calculateSpecializationScore(model: ModelCapabilities, focus: ResearchFocus): number {
    const focusSpecializationMap = {
      technical: ['coding'],
      business: ['general', 'instruction-following'],
      ethical: ['reasoning', 'instruction-following'],
      creative: ['creative-writing', 'general'],
      general: ['general', 'instruction-following']
    };

    const relevantSpecs = focusSpecializationMap[focus];
    const hasRelevantSpec = model.specializations.some(spec =>
      relevantSpecs.includes(spec)
    );
    return hasRelevantSpec ? 1.0 : 0.5;
  }

  private selectDiverseModels(
    scoredModels: Array<ModelCapabilities & { score: number }>,
    count: number,
    requireDiversity: boolean
  ): ModelCapabilities[] {
    if (!requireDiversity || scoredModels.length <= count) {
      return scoredModels.slice(0, count);
    }

    const selected: ModelCapabilities[] = [];
    const used_tiers = new Set<string>();
    const used_specializations = new Set<string>();

    // First pass: select highest scoring models from different tiers
    for (const model of scoredModels) {
      if (selected.length >= count) break;

      if (!used_tiers.has(model.tier.name)) {
        selected.push(model);
        used_tiers.add(model.tier.name);
        model.specializations.forEach(spec => used_specializations.add(spec));
      }
    }

    // Second pass: fill remaining slots with diverse specializations
    for (const model of scoredModels) {
      if (selected.length >= count) break;
      if (selected.includes(model)) continue;

      const hasNewSpecialization = model.specializations.some(spec =>
        !used_specializations.has(spec)
      );

      if (hasNewSpecialization) {
        selected.push(model);
        model.specializations.forEach(spec => used_specializations.add(spec));
      }
    }

    // Fill any remaining slots with highest scoring models
    while (selected.length < count && selected.length < scoredModels.length) {
      for (const model of scoredModels) {
        if (!selected.includes(model)) {
          selected.push(model);
          break;
        }
      }
    }

    return selected;
  }

  private buildFallbackChain(
    availableModels: ModelCapabilities[],
    selectedModels: ModelCapabilities[]
  ): ModelCapabilities[] {
    return availableModels
      .filter(model => !selectedModels.includes(model))
      .sort((a, b) => b.reliability - a.reliability)
      .slice(0, 3); // Keep top 3 as fallbacks
  }

  private estimateTimeout(model: ModelCapabilities, complexity: ComplexityLevel): number {
    const baseTimeout = COMPLEXITY_TIMEOUTS[complexity].base;
    const multiplier = model.tier.timeoutMultiplier;
    return Math.min(
      baseTimeout * multiplier,
      COMPLEXITY_TIMEOUTS[complexity].max
    );
  }

  private estimateStrategyTime(models: ModelCapabilities[], complexity: ComplexityLevel): number {
    // Estimate for sequential execution (parallel would be max of all)
    return models.reduce((total, model) => {
      return total + this.estimateTimeout(model, complexity);
    }, 0);
  }

  private generateSelectionReasoning(
    models: ModelCapabilities[],
    criteria: ModelSelectionCriteria
  ): string {
    const { complexity, focus } = criteria;
    const tierDistribution = models.reduce((acc, model) => {
      acc[model.tier.name] = (acc[model.tier.name] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return `Selected ${models.length} models for ${complexity} complexity ${focus} research: ` +
      `${models.map(m => `${m.name} (${m.parameters})`).join(', ')}. ` +
      `Tier distribution: ${Object.entries(tierDistribution)
        .map(([tier, count]) => `${count} ${tier}`)
        .join(', ')}. ` +
      `Estimated completion time: ${Math.round(this.estimateStrategyTime(models, complexity) / 1000)}s.`;
  }

  /**
   * Update performance history for model optimization
   */
  updatePerformanceHistory(modelName: string, responseTime: number): void {
    const history = this.performanceHistory.get(modelName) || [];
    history.push(responseTime);

    // Keep only last 10 measurements
    if (history.length > 10) {
      history.shift();
    }

    this.performanceHistory.set(modelName, history);
  }
}