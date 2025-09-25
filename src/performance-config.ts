/**
 * Performance Configuration for MCP Ollama Research Tool
 * Optimized timeout strategies, caching, and resource management
 */

import { ComplexityLevel, ModelCapabilities } from './research-types.js';

export interface PerformanceConfig {
  timeouts: {
    base: number;
    max: number;
    multiplierByTier: Record<string, number>;
  };
  concurrency: {
    maxParallelQueries: number;
    queueLimit: number;
    backpressureThreshold: number;
  };
  caching: {
    enabled: boolean;
    ttl: number;
    maxEntries: number;
  };
  retries: {
    maxAttempts: number;
    backoffMultiplier: number;
    retryableErrors: string[];
  };
  resources: {
    memoryWarningThreshold: number;
    cpuWarningThreshold: number;
    diskSpaceWarningThreshold: number;
  };
}

export const PERFORMANCE_CONFIGS: Record<ComplexityLevel, PerformanceConfig> = {
  simple: {
    timeouts: {
      base: 30000,  // 30 seconds
      max: 90000,   // 1.5 minutes
      multiplierByTier: {
        fast: 1.0,
        large: 1.5,
        cloud: 2.0
      }
    },
    concurrency: {
      maxParallelQueries: 5,
      queueLimit: 10,
      backpressureThreshold: 8
    },
    caching: {
      enabled: true,
      ttl: 300000,  // 5 minutes
      maxEntries: 100
    },
    retries: {
      maxAttempts: 2,
      backoffMultiplier: 1.5,
      retryableErrors: ['ECONNABORTED', 'ENOTFOUND', 'timeout']
    },
    resources: {
      memoryWarningThreshold: 0.8,
      cpuWarningThreshold: 0.7,
      diskSpaceWarningThreshold: 0.9
    }
  },

  medium: {
    timeouts: {
      base: 60000,   // 1 minute
      max: 180000,   // 3 minutes
      multiplierByTier: {
        fast: 1.0,
        large: 1.8,
        cloud: 2.5
      }
    },
    concurrency: {
      maxParallelQueries: 3,
      queueLimit: 8,
      backpressureThreshold: 6
    },
    caching: {
      enabled: true,
      ttl: 600000,  // 10 minutes
      maxEntries: 50
    },
    retries: {
      maxAttempts: 3,
      backoffMultiplier: 2.0,
      retryableErrors: ['ECONNABORTED', 'ENOTFOUND', 'timeout', 'ECONNRESET']
    },
    resources: {
      memoryWarningThreshold: 0.85,
      cpuWarningThreshold: 0.75,
      diskSpaceWarningThreshold: 0.95
    }
  },

  complex: {
    timeouts: {
      base: 120000,  // 2 minutes
      max: 600000,   // 10 minutes
      multiplierByTier: {
        fast: 1.2,
        large: 2.0,
        cloud: 3.0
      }
    },
    concurrency: {
      maxParallelQueries: 2,
      queueLimit: 5,
      backpressureThreshold: 4
    },
    caching: {
      enabled: true,
      ttl: 1200000, // 20 minutes
      maxEntries: 25
    },
    retries: {
      maxAttempts: 4,
      backoffMultiplier: 2.5,
      retryableErrors: ['ECONNABORTED', 'ENOTFOUND', 'timeout', 'ECONNRESET', 'ETIMEDOUT']
    },
    resources: {
      memoryWarningThreshold: 0.9,
      cpuWarningThreshold: 0.8,
      diskSpaceWarningThreshold: 0.98
    }
  }
};

export class PerformanceManager {
  private queryQueue: Array<{ id: string; priority: number; timestamp: number }> = [];
  private activeQueries = new Map<string, { startTime: number; complexity: ComplexityLevel }>();
  private cache = new Map<string, { data: any; timestamp: number; ttl: number }>();

  /**
   * Get timeout for model based on complexity and tier
   */
  getTimeout(model: ModelCapabilities, complexity: ComplexityLevel, customTimeout?: number): number {
    if (customTimeout) return customTimeout;

    const config = PERFORMANCE_CONFIGS[complexity];
    const multiplier = config.timeouts.multiplierByTier[model.tier.name] || 1.0;
    const calculatedTimeout = config.timeouts.base * multiplier;

    return Math.min(calculatedTimeout, config.timeouts.max);
  }

  /**
   * Check if query can be executed based on current load
   */
  canExecuteQuery(complexity: ComplexityLevel): { allowed: boolean; reason?: string } {
    const config = PERFORMANCE_CONFIGS[complexity];
    const currentLoad = this.activeQueries.size;

    if (currentLoad >= config.concurrency.maxParallelQueries) {
      return {
        allowed: false,
        reason: `Maximum concurrent queries reached (${currentLoad}/${config.concurrency.maxParallelQueries})`
      };
    }

    if (this.queryQueue.length >= config.concurrency.queueLimit) {
      return {
        allowed: false,
        reason: `Query queue full (${this.queryQueue.length}/${config.concurrency.queueLimit})`
      };
    }

    return { allowed: true };
  }

  /**
   * Register query start for tracking
   */
  registerQueryStart(queryId: string, complexity: ComplexityLevel): void {
    this.activeQueries.set(queryId, {
      startTime: Date.now(),
      complexity
    });
  }

  /**
   * Register query completion and update metrics
   */
  registerQueryCompletion(queryId: string, responseTime: number): void {
    this.activeQueries.delete(queryId);
  }

  /**
   * Cache result with TTL based on complexity
   */
  cacheResult(key: string, data: any, complexity: ComplexityLevel): void {
    const config = PERFORMANCE_CONFIGS[complexity];
    if (!config.caching.enabled) return;

    // Clean old entries if cache is full
    if (this.cache.size >= config.caching.maxEntries) {
      this.cleanExpiredCache();
    }

    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: config.caching.ttl
    });
  }

  /**
   * Retrieve cached result if valid
   */
  getCachedResult(key: string): any | null {
    const cached = this.cache.get(key);
    if (!cached) return null;

    const age = Date.now() - cached.timestamp;
    if (age > cached.ttl) {
      this.cache.delete(key);
      return null;
    }

    return cached.data;
  }

  /**
   * Generate cache key for research query
   */
  generateCacheKey(question: string, models: string[], complexity: ComplexityLevel, focus: string): string {
    const normalizedQuestion = question.toLowerCase().replace(/\s+/g, ' ').trim();
    const sortedModels = models.sort().join(',');
    return `research:${normalizedQuestion}:${sortedModels}:${complexity}:${focus}`;
  }

  /**
   * Clean expired cache entries
   */
  private cleanExpiredCache(): void {
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > entry.ttl) {
        this.cache.delete(key);
      }
    }
  }

  /**
   * Get current performance metrics
   */
  getMetrics(): {
    activeQueries: number;
    queueLength: number;
    cacheSize: number;
    cacheHitRate: number;
  } {
    return {
      activeQueries: this.activeQueries.size,
      queueLength: this.queryQueue.length,
      cacheSize: this.cache.size,
      cacheHitRate: 0 // TODO: Implement hit rate tracking
    };
  }

  /**
   * Check system resource status
   */
  async checkResourceStatus(complexity: ComplexityLevel): Promise<{
    status: 'healthy' | 'warning' | 'critical';
    warnings: string[];
  }> {
    const warnings: string[] = [];
    let status: 'healthy' | 'warning' | 'critical' = 'healthy';

    const config = PERFORMANCE_CONFIGS[complexity];

    // Check memory usage (simplified - would use actual system metrics in production)
    const memoryUsage = process.memoryUsage().heapUsed / process.memoryUsage().heapTotal;
    if (memoryUsage > config.resources.memoryWarningThreshold) {
      warnings.push(`High memory usage: ${Math.round(memoryUsage * 100)}%`);
      status = 'warning';
    }

    // Check active query load
    const queryLoad = this.activeQueries.size / PERFORMANCE_CONFIGS[complexity].concurrency.maxParallelQueries;
    if (queryLoad > 0.8) {
      warnings.push(`High query load: ${Math.round(queryLoad * 100)}%`);
      if (status === 'healthy') status = 'warning';
    }

    return { status, warnings };
  }
}

export class RetryManager {
  private retryHistory = new Map<string, { attempts: number; lastAttempt: number }>();

  /**
   * Execute function with retry logic based on complexity
   */
  async executeWithRetry<T>(
    operation: () => Promise<T>,
    operationId: string,
    complexity: ComplexityLevel
  ): Promise<T> {
    const config = PERFORMANCE_CONFIGS[complexity].retries;
    let lastError: Error;

    const history = this.retryHistory.get(operationId) || { attempts: 0, lastAttempt: 0 };

    for (let attempt = 1; attempt <= config.maxAttempts; attempt++) {
      try {
        const result = await operation();
        this.retryHistory.delete(operationId); // Clear history on success
        return result;

      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        history.attempts = attempt;
        history.lastAttempt = Date.now();
        this.retryHistory.set(operationId, history);

        // Don't retry if it's not a retryable error
        if (!this.isRetryableError(lastError, config.retryableErrors)) {
          throw lastError;
        }

        // Don't retry on last attempt
        if (attempt >= config.maxAttempts) {
          throw lastError;
        }

        // Calculate backoff delay
        const delay = this.calculateBackoffDelay(attempt, config.backoffMultiplier);
        await this.sleep(delay);
      }
    }

    throw lastError!;
  }

  private isRetryableError(error: Error, retryableErrors: string[]): boolean {
    return retryableErrors.some(pattern =>
      error.message.includes(pattern) || error.name.includes(pattern)
    );
  }

  private calculateBackoffDelay(attempt: number, multiplier: number): number {
    const baseDelay = 1000; // 1 second
    return baseDelay * Math.pow(multiplier, attempt - 1);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export default { PERFORMANCE_CONFIGS, PerformanceManager, RetryManager };