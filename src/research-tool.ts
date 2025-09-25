/**
 * Research Tool Implementation for MCP Ollama Server
 * Orchestrates model selection, parallel execution, and response analysis
 */

import axios from 'axios';
import {
  ResearchRequest,
  ModelResponse,
  ResearchResult,
  ModelCapabilities,
  ComplexityLevel,
  ResearchFocus,
  COMPLEXITY_TIMEOUTS
} from './research-types.js';
import { ModelSelector } from './model-selector.js';
import { ResponseAnalyzer } from './response-analyzer.js';

export class ResearchTool {
  private modelSelector: ModelSelector;
  private responseAnalyzer: ResponseAnalyzer;
  private ollamaHost: string;
  private lastSelectionReasoning?: string;
  private modelQueryIndex?: number;

  constructor(ollamaHost: string = 'http://127.0.0.1:11434') {
    this.modelSelector = new ModelSelector();
    this.responseAnalyzer = new ResponseAnalyzer();
    this.ollamaHost = ollamaHost;
  }

  /**
   * Execute research query with intelligent model selection and analysis
   */
  async executeResearch(request: ResearchRequest): Promise<ResearchResult> {
    const {
      question,
      complexity = 'medium',
      models,
      focus = 'general',
      parallel = false,
      include_metadata = false,
      timeout,
      temperature = 0.7
    } = request;

    try {
      // Get available models from Ollama
      const availableModels = await this.getAvailableModels();

      // Select optimal models if not specified
      const selectedModels = models && models.length > 0
        ? await this.validateSpecificModels(models, availableModels, complexity)
        : await this.selectOptimalModels(availableModels, complexity, focus);

      if (selectedModels.length === 0) {
        // If user specified models but none were valid, try auto-selection as fallback
        if (models && models.length > 0) {
          console.warn('All specified models invalid, attempting auto-selection fallback');
          const fallbackModels = await this.selectOptimalModels(availableModels, complexity, focus);
          if (fallbackModels.length === 0) {
            throw new Error('No suitable models available for the requested complexity level');
          }
          selectedModels.push(...fallbackModels);
        } else {
          throw new Error('No suitable models available for the requested complexity level');
        }
      }

      // Execute queries
      const responses = parallel
        ? await this.executeParallelQueries(selectedModels, question, complexity, temperature, timeout)
        : await this.executeSequentialQueries(selectedModels, question, complexity, temperature, timeout);

      // Check if we have any successful responses
      const successfulResponses = responses.filter(r => !r.error);
      if (successfulResponses.length === 0) {
        const errors = responses.map(r => `${r.model}: ${r.error}`).join('; ');
        throw new Error(`All models failed to respond. Errors: ${errors}`);
      }

      // Log partial failures if any
      const failedResponses = responses.filter(r => r.error);
      if (failedResponses.length > 0) {
        console.warn(`${failedResponses.length}/${responses.length} models failed:`,
          failedResponses.map(r => `${r.model}: ${r.error}`).join('; '));
      }

      // Add metadata if requested
      if (include_metadata) {
        this.addMetadataToResponses(responses, availableModels);
      }

      // Analyze responses and generate result (analyzer handles failed responses gracefully)
      const result = await this.responseAnalyzer.analyzeResponses(
        question,
        responses,
        focus,
        complexity
      );

      // Update performance history for optimization
      responses.forEach(response => {
        if (!response.error) {
          this.modelSelector.updatePerformanceHistory(response.model, response.responseTime);
        }
      });

      // Add model selection reasoning to result
      if (this.lastSelectionReasoning) {
        result.analysis.model_selection_reasoning = this.lastSelectionReasoning;
      }

      return result;

    } catch (error) {
      console.error('Research execution error:', error);
      throw new Error(`Research execution failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get available models from Ollama with capability analysis
   */
  private async getAvailableModels(): Promise<ModelCapabilities[]> {
    try {
      const response = await axios.get(`${this.ollamaHost}/api/tags`);
      const rawModels = response.data.models || [];
      return this.modelSelector.parseModelCapabilities(rawModels);
    } catch (error) {
      throw new Error(`Failed to fetch available models: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Validate user-specified models against complexity requirements
   */
  private async validateSpecificModels(
    modelNames: string[],
    availableModels: ModelCapabilities[],
    complexity: ComplexityLevel
  ): Promise<ModelCapabilities[]> {
    const validModels: ModelCapabilities[] = [];
    const invalidModels: string[] = [];

    for (const modelName of modelNames) {
      const model = availableModels.find(m => m.name === modelName);
      if (!model) {
        invalidModels.push(modelName);
        console.warn(`Warning: Model '${modelName}' not found, skipping`);
        continue;
      }

      if (!model.complexity.includes(complexity)) {
        console.warn(`Warning: Model '${modelName}' may not be optimal for '${complexity}' complexity`);
      }

      validModels.push(model);
    }

    // Log summary of validation results
    if (invalidModels.length > 0) {
      console.warn(`Skipped ${invalidModels.length} invalid models: ${invalidModels.join(', ')}`);
      console.warn(`Available models: ${availableModels.map(m => m.name).join(', ')}`);
    }

    return validModels;
  }

  /**
   * Select optimal models using intelligent selection algorithm
   */
  private async selectOptimalModels(
    availableModels: ModelCapabilities[],
    complexity: ComplexityLevel,
    focus: ResearchFocus
  ): Promise<ModelCapabilities[]> {
    const maxTimeout = COMPLEXITY_TIMEOUTS[complexity].max;

    const selectionCriteria = {
      complexity,
      focus,
      availableModels,
      preferredCount: 3,
      requireDiversity: true,
      maxTimeout
    };

    const strategy = await this.modelSelector.selectModels(selectionCriteria);
    // Store selection reasoning for user feedback
    this.lastSelectionReasoning = strategy.reasoning;
    return [strategy.primary, strategy.secondary, strategy.tertiary].filter(Boolean);
  }

  /**
   * Execute queries in parallel for faster results
   */
  private async executeParallelQueries(
    models: ModelCapabilities[],
    question: string,
    complexity: ComplexityLevel,
    temperature: number,
    customTimeout?: number
  ): Promise<ModelResponse[]> {
    const promises = models.map(model =>
      this.executeModelQuery(model, question, complexity, temperature, customTimeout)
    );

    const responses = await Promise.allSettled(promises);

    return responses.map((result, index) => {
      if (result.status === 'fulfilled') {
        return result.value;
      } else {
        return {
          model: models[index].name,
          response: '',
          responseTime: 0,
          tokenCount: 0,
          confidence: 0,
          error: result.reason instanceof Error ? result.reason.message : 'Query failed'
        };
      }
    });
  }

  /**
   * Execute queries sequentially for better resource management
   */
  private async executeSequentialQueries(
    models: ModelCapabilities[],
    question: string,
    complexity: ComplexityLevel,
    temperature: number,
    customTimeout?: number
  ): Promise<ModelResponse[]> {
    const responses: ModelResponse[] = [];

    for (const model of models) {
      try {
        const response = await this.executeModelQuery(model, question, complexity, temperature, customTimeout);
        responses.push(response);
      } catch (error) {
        responses.push({
          model: model.name,
          response: '',
          responseTime: 0,
          tokenCount: 0,
          confidence: 0,
          error: error instanceof Error ? error.message : 'Query failed'
        });
      }
    }

    return responses;
  }

  /**
   * Execute query on a single model with comprehensive error handling
   */
  private async executeModelQuery(
    model: ModelCapabilities,
    question: string,
    complexity: ComplexityLevel,
    temperature: number,
    customTimeout?: number
  ): Promise<ModelResponse> {
    const startTime = Date.now();

    // Calculate timeout based on model tier and complexity
    const baseTimeout = COMPLEXITY_TIMEOUTS[complexity].base;
    const timeout = customTimeout || Math.min(
      baseTimeout * model.tier.timeoutMultiplier,
      COMPLEXITY_TIMEOUTS[complexity].max
    );

    // Determine if model is small (< 8B parameters) and adjust approach
    const isSmallModel = model.size < 8_000_000_000;
    const modelIndex = this.modelQueryIndex || 0;
    this.modelQueryIndex = (this.modelQueryIndex || 0) + 1;

    try {
      const response = await axios.post(
        `${this.ollamaHost}/api/generate`,
        {
          model: model.name,
          prompt: this.formatResearchPrompt(question, complexity, isSmallModel, modelIndex),
          stream: false,
          options: {
            temperature: isSmallModel ? Math.min(1.2, temperature * 1.3) : temperature, // Higher temp for small models
            num_predict: this.getMaxTokensForComplexity(complexity),
            seed: isSmallModel ? modelIndex * 42 : undefined // Different seeds for diversity
          }
        },
        { timeout }
      );

      const responseTime = Date.now() - startTime;
      const responseText = response.data.response || '';

      return {
        model: model.name,
        response: responseText,
        responseTime,
        tokenCount: this.estimateTokenCount(responseText),
        confidence: this.calculateResponseConfidence(responseText, question, complexity, model)
      };

    } catch (error) {
      const responseTime = Date.now() - startTime;

      let errorMessage = 'Unknown error';
      if (axios.isAxiosError(error)) {
        if (error.code === 'ECONNABORTED') {
          errorMessage = `Timeout after ${timeout}ms`;
        } else {
          errorMessage = error.response?.data?.error || error.message;
        }
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }

      return {
        model: model.name,
        response: '',
        responseTime,
        tokenCount: 0,
        confidence: 0,
        error: errorMessage
      };
    }
  }

  /**
   * Format research prompt based on complexity level and model characteristics
   */
  private formatResearchPrompt(
    question: string,
    complexity: ComplexityLevel,
    isSmallModel: boolean = false,
    modelIndex: number = 0
  ): string {
    // For small models, add perspective variation to encourage divergence
    if (isSmallModel) {
      const perspectives = [
        'from a skeptical perspective, identify potential issues and risks',
        'playing devil\'s advocate, argue an alternative viewpoint',
        'from an innovative angle, suggest unconventional approaches',
        'focusing on practical limitations and real-world constraints'
      ];
      const perspective = perspectives[modelIndex % perspectives.length];

      return `Please analyze the following question ${perspective}:\n\n${question}\n\nProvide a unique perspective that challenges common assumptions.`;
    }

    // Standard prompts for larger models
    const prompts = {
      simple: `Please provide a clear and concise answer to the following question:\n\n${question}\n\nKeep your response focused and direct.`,

      medium: `Please analyze and answer the following research question comprehensively:\n\n${question}\n\nProvide reasoning, examples, and consider multiple perspectives. Aim for a balanced and well-structured response.`,

      complex: `Please conduct a thorough analysis of the following complex research question:\n\n${question}\n\nYour response should include:\n- Detailed analysis of the topic\n- Multiple perspectives and considerations\n- Evidence and reasoning\n- Potential implications and conclusions\n- Any limitations or uncertainties\n\nProvide a comprehensive and nuanced response.`
    };

    return prompts[complexity];
  }

  /**
   * Get maximum token count based on complexity
   */
  private getMaxTokensForComplexity(complexity: ComplexityLevel): number {
    const tokenLimits = {
      simple: 500,
      medium: 1500,
      complex: 3000
    };
    return tokenLimits[complexity];
  }

  /**
   * Estimate token count from response text
   */
  private estimateTokenCount(text: string): number {
    // Rough estimation: ~1.3 tokens per word
    const words = text.split(/\s+/).length;
    return Math.round(words * 1.3);
  }

  /**
   * Calculate response confidence based on various factors including model size
   */
  private calculateResponseConfidence(
    response: string,
    question: string,
    complexity: ComplexityLevel,
    model?: ModelCapabilities
  ): number {
    let confidence = 0.5; // Base confidence

    // Adjust base confidence based on model size
    if (model) {
      if (model.size < 3_000_000_000) { // < 3B
        confidence = 0.4; // Lower base for very small models
      } else if (model.size < 8_000_000_000) { // 3B-8B
        confidence = 0.45; // Slightly lower base for small models
      } else if (model.size > 30_000_000_000) { // > 30B
        confidence = 0.6; // Higher base for large models
      }
    }

    // Length appropriateness
    const expectedLengths = { simple: [50, 300], medium: [200, 800], complex: [500, 2000] };
    const [minLen, maxLen] = expectedLengths[complexity];
    const length = response.length;

    if (length >= minLen && length <= maxLen) {
      confidence += 0.15; // Reduced from 0.2
    } else if (length < minLen * 0.5 || length > maxLen * 2) {
      confidence -= 0.15; // Reduced penalty
    }

    // Content quality indicators
    const qualityIndicators = [
      'because', 'therefore', 'however', 'although', 'furthermore',
      'example', 'evidence', 'analysis', 'conclusion', 'consider'
    ];
    const indicatorCount = qualityIndicators.filter(indicator =>
      response.toLowerCase().includes(indicator)
    ).length;
    confidence += Math.min(0.15, indicatorCount * 0.03); // Reduced impact

    // Question relevance (simple keyword matching)
    const questionWords = question.toLowerCase().split(/\s+/).filter(word =>
      word.length > 3 && !['what', 'how', 'why', 'when', 'where', 'which'].includes(word)
    );
    const relevantWords = questionWords.filter(word =>
      response.toLowerCase().includes(word)
    );
    if (questionWords.length > 0) {
      confidence += Math.min(0.15, (relevantWords.length / questionWords.length) * 0.15);
    }

    // Model tier adjustment
    if (model) {
      const tierMultipliers = { cloud: 1.1, large: 1.0, fast: 0.9 };
      confidence *= tierMultipliers[model.tier.name] || 1.0;
    }

    // Avoid obviously incomplete responses
    if (response.length < 20 || response.includes('...') || response.endsWith('incomplete')) {
      confidence *= 0.5;
    }

    return Math.max(0.1, Math.min(0.95, confidence)); // Keep within realistic bounds
  }

  /**
   * Add model metadata to responses for detailed analysis
   */
  private addMetadataToResponses(responses: ModelResponse[], availableModels: ModelCapabilities[]): void {
    responses.forEach(response => {
      const model = availableModels.find(m => m.name === response.model);
      if (model) {
        response.metadata = {
          parameters: model.parameters,
          contextWindow: model.contextWindow,
          tier: model.tier.name,
          temperature: 0.7 // Default temperature used
        };
      }
    });
  }

  /**
   * Health check for the research tool
   */
  async healthCheck(): Promise<{ status: string; models: number; message: string }> {
    try {
      const models = await this.getAvailableModels();
      return {
        status: 'healthy',
        models: models.length,
        message: `Research tool operational with ${models.length} available models`
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        models: 0,
        message: `Health check failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      };
    }
  }
}