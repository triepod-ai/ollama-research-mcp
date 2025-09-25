/**
 * Type definitions for the MCP Ollama Research Tool
 * Intelligent model selection and comparative analysis system
 */

export interface ModelCapabilities {
  name: string;
  size: number; // Size in bytes
  parameters: string; // e.g., "7B", "13B", "70B"
  contextWindow: number;
  quantization: string;
  modifiedAt: string;
  tier: ModelTier;
  complexity: ComplexityLevel[];
  specializations: string[];
  averageResponseTime: number; // milliseconds
  reliability: number; // 0-1 score
}

export interface ModelTier {
  name: 'cloud' | 'large' | 'fast';
  minParams: number; // Minimum parameters in billions
  maxParams: number;
  timeoutMultiplier: number;
  complexitySupport: ComplexityLevel[];
}

export type ComplexityLevel = 'simple' | 'medium' | 'complex';
export type ResearchFocus = 'technical' | 'business' | 'ethical' | 'creative' | 'general';

export interface ResearchRequest {
  question: string;
  complexity?: ComplexityLevel;
  models?: string[];
  focus?: ResearchFocus;
  parallel?: boolean;
  include_metadata?: boolean;
  timeout?: number;
  temperature?: number;
}

export interface ModelResponse {
  model: string;
  response: string;
  responseTime: number;
  tokenCount: number;
  confidence: number; // 0-1 based on response coherence
  error?: string;
  metadata?: {
    parameters: string;
    contextWindow: number;
    tier: string;
    temperature: number;
  };
}

export interface ResearchResult {
  question: string;
  focus: ResearchFocus;
  complexity: ComplexityLevel;
  timestamp: string;
  models_used: string[];
  responses: ModelResponse[];
  analysis: {
    convergent_themes: string[];
    divergent_perspectives: string[];
    reasoning_styles: ReasoningStyle[];
    synthesis: string;
    recommendations: string[];
    confidence_score: number; // 0-1 aggregate confidence
    model_selection_reasoning?: string; // Why these models were selected
  };
  performance: {
    total_time: number;
    successful_responses: number;
    failed_responses: number;
    average_response_time: number;
  };
  errors?: string[];
}

export interface ReasoningStyle {
  model: string;
  style: 'analytical' | 'creative' | 'practical' | 'theoretical' | 'balanced';
  characteristics: string[];
  depth: 'surface' | 'moderate' | 'deep';
  confidence: number;
}

export interface ModelSelectionCriteria {
  complexity: ComplexityLevel;
  focus: ResearchFocus;
  availableModels: ModelCapabilities[];
  preferredCount: number;
  requireDiversity: boolean;
  maxTimeout: number;
}

export interface SelectionStrategy {
  primary: ModelCapabilities;
  secondary: ModelCapabilities;
  tertiary: ModelCapabilities;
  fallbacks: ModelCapabilities[];
  reasoning: string;
  estimatedTime: number;
}

// Model tier definitions
export const MODEL_TIERS: Record<string, ModelTier> = {
  cloud: {
    name: 'cloud',
    minParams: 480,
    maxParams: Infinity,
    timeoutMultiplier: 3.0,
    complexitySupport: ['simple', 'medium', 'complex']
  },
  large: {
    name: 'large',
    minParams: 7,
    maxParams: 479,
    timeoutMultiplier: 2.0,
    complexitySupport: ['simple', 'medium', 'complex']
  },
  fast: {
    name: 'fast',
    minParams: 0.1,
    maxParams: 6.9,
    timeoutMultiplier: 1.0,
    complexitySupport: ['simple', 'medium']
  }
};

// Complexity-based timeout configurations
export const COMPLEXITY_TIMEOUTS = {
  simple: {
    base: 30000, // 30 seconds
    max: 90000   // 1.5 minutes
  },
  medium: {
    base: 60000, // 1 minute
    max: 180000  // 3 minutes
  },
  complex: {
    base: 120000, // 2 minutes
    max: 180000   // 3 minutes
  }
};

// Focus-specific model preferences
export const FOCUS_PREFERENCES: Record<ResearchFocus, string[]> = {
  technical: ['codellama', 'deepseek-coder', 'qwen2.5-coder', 'starcoder'],
  business: ['llama3.2', 'qwen2.5', 'mistral', 'gemma2'],
  ethical: ['llama3.2', 'claude-3', 'gpt-4', 'mistral'],
  creative: ['llama3.2', 'mistral-7b', 'qwen2.5', 'gemma2'],
  general: ['llama3.2', 'qwen2.5', 'mistral', 'gemma2']
};