/**
 * Unit Tests for ResponseAnalyzer
 * Tests convergent/divergent analysis, theme detection, and synthesis generation
 */

import { jest } from '@jest/globals';
import { ResponseAnalyzer } from '../../src/response-analyzer.js';
import type { ModelResponse, ResearchFocus, ComplexityLevel } from '../../src/research-types.js';

describe('ResponseAnalyzer', () => {
  let analyzer: ResponseAnalyzer;
  let mockResponses: ModelResponse[];

  beforeEach(() => {
    analyzer = new ResponseAnalyzer();

    mockResponses = [
      {
        model: 'llama3.2:1b',
        response: 'AI significantly impacts software development through automation and intelligent code assistance. It helps developers write code faster and catch bugs early. However, there are concerns about over-reliance and potential job displacement.',
        responseTime: 2000,
        tokenCount: 45,
        confidence: 0.8
      },
      {
        model: 'qwen2.5-coder:7b-instruct',
        response: 'Artificial intelligence transforms software development by providing intelligent code completion, automated testing, and bug detection. Tools like GitHub Copilot increase productivity by 25-40%. The main challenges include maintaining code quality and ensuring developers retain fundamental skills.',
        responseTime: 4000,
        tokenCount: 62,
        confidence: 0.9
      },
      {
        model: 'smallthinker:latest',
        response: 'The impact of AI on software development is revolutionary. Beyond code generation, AI enables predictive analytics for project management, intelligent refactoring, and automated documentation. However, it raises ethical concerns about code ownership, introduces new security vulnerabilities, and may create over-dependence on AI tools.',
        responseTime: 6000,
        tokenCount: 78,
        confidence: 0.85
      }
    ];
  });

  describe('analyzeResponses', () => {
    it('should analyze responses and return comprehensive research result', async () => {
      const question = 'What is the impact of AI on software development?';
      const result = await analyzer.analyzeResponses(
        question,
        mockResponses,
        'technical',
        'medium'
      );

      expect(result).toHaveResearchResult();
      expect(result.question).toBe(question);
      expect(result.responses).toHaveLength(3);
      expect(result.convergentThemes.length).toBeGreaterThan(0);
      expect(result.divergentPerspectives.length).toBeGreaterThan(0);
      expect(result.synthesis.length).toBeGreaterThan(50);
      expect(result.confidence).toBeGreaterThan(0);
      expect(result.executionTime).toBeGreaterThan(0);
    });

    it('should handle responses with errors', async () => {
      const responsesWithError: ModelResponse[] = [
        ...mockResponses.slice(0, 2),
        {
          model: 'failed-model',
          response: '',
          responseTime: 1000,
          tokenCount: 0,
          confidence: 0,
          error: 'Model timeout'
        }
      ];

      const result = await analyzer.analyzeResponses(
        'Test question',
        responsesWithError,
        'general',
        'simple'
      );

      expect(result.responses).toHaveLength(3);
      expect(result.responses[2].error).toBe('Model timeout');
      expect(result.convergentThemes.length).toBeGreaterThan(0); // Should still find themes from successful responses
    });

    it('should adapt analysis depth based on complexity level', async () => {
      const simpleResult = await analyzer.analyzeResponses(
        'Simple question?',
        mockResponses,
        'general',
        'simple'
      );

      const complexResult = await analyzer.analyzeResponses(
        'Complex question?',
        mockResponses,
        'technical',
        'complex'
      );

      // Complex analysis should provide more detailed insights
      expect(complexResult.synthesis.length).toBeGreaterThan(simpleResult.synthesis.length);
      expect(complexResult.convergentThemes.length).toBeGreaterThanOrEqual(simpleResult.convergentThemes.length);
    });

    it('should consider research focus in analysis', async () => {
      const technicalResult = await analyzer.analyzeResponses(
        'Technical question?',
        mockResponses,
        'technical',
        'medium'
      );

      const businessResult = await analyzer.analyzeResponses(
        'Business question?',
        mockResponses,
        'business',
        'medium'
      );

      // Results should reflect different focus areas
      expect(technicalResult.synthesis).not.toBe(businessResult.synthesis);
    });

    it('should handle empty responses gracefully', async () => {
      const emptyResponses: ModelResponse[] = [];

      const result = await analyzer.analyzeResponses(
        'Test question',
        emptyResponses,
        'general',
        'simple'
      );

      expect(result.responses).toHaveLength(0);
      expect(result.convergentThemes).toHaveLength(0);
      expect(result.divergentPerspectives).toHaveLength(0);
      expect(result.synthesis).toContain('No responses');
      expect(result.confidence).toBe(0);
    });

    it('should handle single response', async () => {
      const singleResponse = [mockResponses[0]];

      const result = await analyzer.analyzeResponses(
        'Single response question',
        singleResponse,
        'general',
        'simple'
      );

      expect(result.responses).toHaveLength(1);
      expect(result.convergentThemes.length).toBeGreaterThanOrEqual(0);
      expect(result.synthesis.length).toBeGreaterThan(0);
      expect(result.confidence).toBeGreaterThan(0);
    });
  });

  describe('theme detection', () => {
    it('should identify convergent themes across responses', async () => {
      const result = await analyzer.analyzeResponses(
        'AI impact on development',
        mockResponses,
        'technical',
        'medium'
      );

      // Should find common themes like automation, productivity, challenges
      expect(result.convergentThemes.some(theme =>
        theme.toLowerCase().includes('automation') ||
        theme.toLowerCase().includes('productivity') ||
        theme.toLowerCase().includes('code')
      )).toBe(true);
    });

    it('should identify divergent perspectives', async () => {
      const diverseResponses: ModelResponse[] = [
        {
          model: 'optimistic-model',
          response: 'AI will revolutionize software development, making it faster and more efficient. Developers will become more productive and focus on higher-level creative tasks.',
          responseTime: 2000,
          tokenCount: 30,
          confidence: 0.8
        },
        {
          model: 'cautious-model',
          response: 'AI tools pose significant risks to software development including job displacement, reduced code quality, and over-dependence. We must proceed carefully.',
          responseTime: 3000,
          tokenCount: 35,
          confidence: 0.7
        },
        {
          model: 'balanced-model',
          response: 'AI brings both opportunities and challenges to software development. The key is finding the right balance between automation and human expertise.',
          responseTime: 2500,
          tokenCount: 32,
          confidence: 0.75
        }
      ];

      const result = await analyzer.analyzeResponses(
        'Future of AI in development',
        diverseResponses,
        'general',
        'medium'
      );

      expect(result.divergentPerspectives.length).toBeGreaterThan(0);
      expect(result.divergentPerspectives.some(perspective =>
        perspective.toLowerCase().includes('risk') ||
        perspective.toLowerCase().includes('caution') ||
        perspective.toLowerCase().includes('opportunit')
      )).toBe(true);
    });

    it('should extract themes from technical responses', async () => {
      const technicalResponses: ModelResponse[] = [
        {
          model: 'tech-model-1',
          response: 'Machine learning algorithms improve code completion accuracy by analyzing patterns in large codebases. Neural networks can predict likely code sequences.',
          responseTime: 3000,
          tokenCount: 40,
          confidence: 0.85
        },
        {
          model: 'tech-model-2',
          response: 'Deep learning models like transformers excel at understanding code context. They can generate syntactically correct code and detect semantic errors.',
          responseTime: 3500,
          tokenCount: 42,
          confidence: 0.9
        }
      ];

      const result = await analyzer.analyzeResponses(
        'How do AI models understand code?',
        technicalResponses,
        'technical',
        'complex'
      );

      // Should identify technical themes
      expect(result.convergentThemes.some(theme =>
        theme.toLowerCase().includes('learning') ||
        theme.toLowerCase().includes('model') ||
        theme.toLowerCase().includes('code')
      )).toBe(true);
    });
  });

  describe('synthesis generation', () => {
    it('should generate comprehensive synthesis from multiple responses', async () => {
      const result = await analyzer.analyzeResponses(
        'Comprehensive AI impact analysis',
        mockResponses,
        'general',
        'complex'
      );

      expect(result.synthesis.length).toBeGreaterThan(100);
      expect(result.synthesis).toContain('AI'); // Should mention the key topic

      // Should reference multiple perspectives
      const synthesisWords = result.synthesis.toLowerCase().split(/\s+/);
      const indicatorWords = ['however', 'although', 'while', 'but', 'also', 'furthermore'];
      const hasTransitions = indicatorWords.some(word => synthesisWords.includes(word));
      expect(hasTransitions).toBe(true);
    });

    it('should adapt synthesis style based on focus area', async () => {
      const technicalResult = await analyzer.analyzeResponses(
        'Technical question',
        mockResponses,
        'technical',
        'medium'
      );

      const businessResult = await analyzer.analyzeResponses(
        'Business question',
        mockResponses,
        'business',
        'medium'
      );

      // Technical synthesis should be more detailed about implementation
      // Business synthesis should focus more on impact and strategy
      expect(technicalResult.synthesis).not.toBe(businessResult.synthesis);
    });

    it('should provide shorter synthesis for simple complexity', async () => {
      const simpleResult = await analyzer.analyzeResponses(
        'Simple question',
        mockResponses,
        'general',
        'simple'
      );

      const complexResult = await analyzer.analyzeResponses(
        'Complex question',
        mockResponses,
        'general',
        'complex'
      );

      expect(simpleResult.synthesis.length).toBeLessThan(complexResult.synthesis.length);
    });
  });

  describe('confidence calculation', () => {
    it('should calculate confidence based on response quality and agreement', async () => {
      const highQualityResponses: ModelResponse[] = [
        {
          model: 'model-1',
          response: 'Detailed response with specific examples and clear reasoning about AI impact on development.',
          responseTime: 2000,
          tokenCount: 50,
          confidence: 0.9
        },
        {
          model: 'model-2',
          response: 'Comprehensive analysis providing similar conclusions with additional evidence and examples.',
          responseTime: 2500,
          tokenCount: 45,
          confidence: 0.85
        }
      ];

      const lowQualityResponses: ModelResponse[] = [
        {
          model: 'model-1',
          response: 'AI good.',
          responseTime: 1000,
          tokenCount: 2,
          confidence: 0.3
        },
        {
          model: 'model-2',
          response: 'Maybe bad maybe good.',
          responseTime: 1200,
          tokenCount: 4,
          confidence: 0.2
        }
      ];

      const highQualityResult = await analyzer.analyzeResponses(
        'Test question',
        highQualityResponses,
        'general',
        'medium'
      );

      const lowQualityResult = await analyzer.analyzeResponses(
        'Test question',
        lowQualityResponses,
        'general',
        'medium'
      );

      expect(highQualityResult.confidence).toBeGreaterThan(lowQualityResult.confidence);
    });

    it('should penalize confidence when responses have errors', async () => {
      const responsesWithErrors: ModelResponse[] = [
        {
          model: 'working-model',
          response: 'Good response about AI development impact.',
          responseTime: 2000,
          tokenCount: 20,
          confidence: 0.8
        },
        {
          model: 'failed-model-1',
          response: '',
          responseTime: 1000,
          tokenCount: 0,
          confidence: 0,
          error: 'Timeout'
        },
        {
          model: 'failed-model-2',
          response: '',
          responseTime: 1500,
          tokenCount: 0,
          confidence: 0,
          error: 'Model not found'
        }
      ];

      const result = await analyzer.analyzeResponses(
        'Test question',
        responsesWithErrors,
        'general',
        'medium'
      );

      // Confidence should be reduced due to failed responses
      expect(result.confidence).toBeLessThan(0.6);
    });

    it('should consider response time in confidence calculation', async () => {
      const fastResponses: ModelResponse[] = mockResponses.map(r => ({
        ...r,
        responseTime: 1000 // Very fast
      }));

      const slowResponses: ModelResponse[] = mockResponses.map(r => ({
        ...r,
        responseTime: 30000 // Very slow, near timeout
      }));

      const fastResult = await analyzer.analyzeResponses(
        'Test question',
        fastResponses,
        'general',
        'medium'
      );

      const slowResult = await analyzer.analyzeResponses(
        'Test question',
        slowResponses,
        'general',
        'medium'
      );

      // Fast responses should generally have higher confidence
      expect(fastResult.confidence).toBeGreaterThanOrEqual(slowResult.confidence);
    });
  });

  describe('edge cases and error handling', () => {
    it('should handle responses with only whitespace', async () => {
      const whitespaceResponses: ModelResponse[] = [
        {
          model: 'empty-model',
          response: '   \n\t  ',
          responseTime: 1000,
          tokenCount: 0,
          confidence: 0.1
        }
      ];

      const result = await analyzer.analyzeResponses(
        'Test question',
        whitespaceResponses,
        'general',
        'simple'
      );

      expect(result.convergentThemes).toHaveLength(0);
      expect(result.synthesis).toContain('insufficient');
    });

    it('should handle very long responses', async () => {
      const longResponse = 'A'.repeat(10000); // Very long response

      const longResponses: ModelResponse[] = [
        {
          model: 'verbose-model',
          response: longResponse,
          responseTime: 5000,
          tokenCount: 7500,
          confidence: 0.7
        }
      ];

      const result = await analyzer.analyzeResponses(
        'Test question',
        longResponses,
        'general',
        'complex'
      );

      expect(result.synthesis.length).toBeLessThan(longResponse.length); // Should be summarized
    });

    it('should handle special characters and encoding', async () => {
      const specialResponses: ModelResponse[] = [
        {
          model: 'unicode-model',
          response: 'AI impacts development: ∞ possibilities, ≈25% productivity ↑, but challenges remain 🤖',
          responseTime: 2000,
          tokenCount: 25,
          confidence: 0.8
        }
      ];

      expect(async () => {
        await analyzer.analyzeResponses(
          'Test question',
          specialResponses,
          'general',
          'simple'
        );
      }).not.toThrow();
    });

    it('should handle duplicate or very similar responses', async () => {
      const duplicateResponses: ModelResponse[] = [
        {
          model: 'model-1',
          response: 'AI improves software development through automation.',
          responseTime: 2000,
          tokenCount: 20,
          confidence: 0.8
        },
        {
          model: 'model-2',
          response: 'AI improves software development through automation.',
          responseTime: 2100,
          tokenCount: 20,
          confidence: 0.8
        },
        {
          model: 'model-3',
          response: 'AI enhances software development via automation.',
          responseTime: 2200,
          tokenCount: 18,
          confidence: 0.75
        }
      ];

      const result = await analyzer.analyzeResponses(
        'Test question',
        duplicateResponses,
        'general',
        'medium'
      );

      // Should still produce meaningful analysis despite similarity
      expect(result.convergentThemes.length).toBeGreaterThan(0);
      expect(result.synthesis.length).toBeGreaterThan(0);

      // Confidence might be lower due to lack of diversity
      expect(result.confidence).toBeGreaterThan(0);
    });
  });
});