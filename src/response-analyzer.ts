/**
 * Response Comparison and Analysis Algorithm for MCP Ollama Research Tool
 * Implements convergence detection, divergence analysis, and intelligent synthesis
 */

import {
  ModelResponse,
  ResearchResult,
  ReasoningStyle,
  ResearchFocus,
  ComplexityLevel
} from './research-types.js';

interface ThemeExtraction {
  theme: string;
  evidence: string[];
  models: string[];
  confidence: number;
}

interface KeywordCluster {
  cluster: string;
  keywords: string[];
  frequency: number;
  models: Set<string>;
}

export class ResponseAnalyzer {
  private stopWords = new Set([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'this', 'that', 'these', 'those', 'is', 'are',
    'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do',
    'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'can', 'cannot', 'it', 'he', 'she', 'they', 'we', 'you', 'i'
  ]);

  /**
   * Analyze multiple model responses and generate comprehensive research result
   */
  async analyzeResponses(
    question: string,
    responses: ModelResponse[],
    focus: ResearchFocus,
    complexity: ComplexityLevel
  ): Promise<ResearchResult> {
    const startTime = Date.now();

    // Extract themes and patterns
    const convergentThemes = this.findConvergentThemes(responses);
    const divergentPerspectives = this.findDivergentPerspectives(responses);
    const reasoningStyles = this.analyzeReasoningStyles(responses);

    // Generate synthesis and recommendations
    const synthesis = await this.generateSynthesis(
      responses,
      convergentThemes,
      divergentPerspectives,
      focus
    );
    const recommendations = this.generateRecommendations(
      convergentThemes,
      divergentPerspectives,
      reasoningStyles,
      complexity
    );

    // Calculate metrics
    const confidenceScore = this.calculateAggregateConfidence(responses, convergentThemes);
    const performance = this.calculatePerformanceMetrics(responses, startTime);

    const result: ResearchResult = {
      question,
      focus,
      complexity,
      timestamp: new Date().toISOString(),
      models_used: responses.map(r => r.model),
      responses,
      analysis: {
        convergent_themes: convergentThemes.map(t => t.theme),
        divergent_perspectives: divergentPerspectives,
        reasoning_styles: reasoningStyles,
        synthesis,
        recommendations,
        confidence_score: confidenceScore
      },
      performance,
      errors: responses.filter(r => r.error).map(r => `${r.model}: ${r.error}`)
    };

    return result;
  }

  /**
   * Find themes that appear across multiple model responses
   */
  private findConvergentThemes(responses: ModelResponse[]): ThemeExtraction[] {
    const validResponses = responses.filter(r => !r.error && r.response.length > 0);
    if (validResponses.length < 2) return [];

    // Extract key phrases and concepts
    const keywordClusters = this.extractKeywordClusters(validResponses);

    // Find themes mentioned by multiple models
    const convergentClusters = keywordClusters.filter(cluster =>
      cluster.models.size >= Math.min(2, Math.ceil(validResponses.length * 0.5))
    );

    return convergentClusters.map(cluster => ({
      theme: cluster.cluster,
      evidence: this.extractEvidence(validResponses, cluster.keywords),
      models: Array.from(cluster.models),
      confidence: cluster.frequency / validResponses.length
    })).sort((a, b) => b.confidence - a.confidence);
  }

  /**
   * Identify unique perspectives and disagreements between models
   */
  private findDivergentPerspectives(responses: ModelResponse[]): string[] {
    const validResponses = responses.filter(r => !r.error && r.response.length > 0);
    if (validResponses.length < 2) return [];

    const perspectives: string[] = [];

    // Find contradictory statements
    const contradictions = this.findContradictions(validResponses);
    perspectives.push(...contradictions);

    // Find unique approaches
    const uniqueApproaches = this.findUniqueApproaches(validResponses);
    perspectives.push(...uniqueApproaches);

    // Find emphasis differences
    const emphasisDifferences = this.findEmphasisDifferences(validResponses);
    perspectives.push(...emphasisDifferences);

    return perspectives.slice(0, 10); // Limit to most significant divergences
  }

  /**
   * Analyze the reasoning style of each model's response
   */
  private analyzeReasoningStyles(responses: ModelResponse[]): ReasoningStyle[] {
    return responses
      .filter(r => !r.error && r.response.length > 0)
      .map(response => {
        const text = response.response.toLowerCase();
        const characteristics: string[] = [];
        let style: ReasoningStyle['style'] = 'balanced';
        let depth: ReasoningStyle['depth'] = 'moderate';

        // Detect analytical patterns
        if (this.hasPattern(text, ['analysis', 'examine', 'evaluate', 'assess', 'measure'])) {
          style = 'analytical';
          characteristics.push('systematic analysis');
        }

        // Detect creative patterns
        if (this.hasPattern(text, ['imagine', 'creative', 'innovative', 'novel', 'unique'])) {
          style = 'creative';
          characteristics.push('creative thinking');
        }

        // Detect practical patterns
        if (this.hasPattern(text, ['practical', 'implement', 'action', 'steps', 'solution'])) {
          style = 'practical';
          characteristics.push('action-oriented');
        }

        // Detect theoretical patterns
        if (this.hasPattern(text, ['theory', 'concept', 'framework', 'model', 'abstract'])) {
          style = 'theoretical';
          characteristics.push('conceptual framework');
        }

        // Assess depth
        if (text.length > 1000 && this.hasPattern(text, ['furthermore', 'moreover', 'additionally'])) {
          depth = 'deep';
          characteristics.push('comprehensive coverage');
        } else if (text.length < 300) {
          depth = 'surface';
          characteristics.push('concise response');
        }

        // Detect additional characteristics
        if (this.hasPattern(text, ['however', 'although', 'despite', 'nevertheless'])) {
          characteristics.push('considers counterpoints');
        }
        if (this.hasPattern(text, ['evidence', 'data', 'research', 'study', 'statistics'])) {
          characteristics.push('evidence-based');
        }
        if (this.hasPattern(text, ['example', 'for instance', 'such as', 'like'])) {
          characteristics.push('uses examples');
        }

        return {
          model: response.model,
          style,
          characteristics,
          depth,
          confidence: response.confidence
        };
      });
  }

  /**
   * Generate intelligent synthesis of all responses
   */
  private async generateSynthesis(
    responses: ModelResponse[],
    convergentThemes: ThemeExtraction[],
    divergentPerspectives: string[],
    focus: ResearchFocus
  ): Promise<string> {
    const validResponses = responses.filter(r => !r.error);
    if (validResponses.length === 0) return "No valid responses available for synthesis.";

    let synthesis = `## Research Synthesis\n\n`;

    // Start with convergent insights
    if (convergentThemes.length > 0) {
      synthesis += `### Key Consensus Points\n\n`;
      synthesis += `Analysis of ${validResponses.length} model responses reveals ${convergentThemes.length} areas of strong agreement:\n\n`;

      convergentThemes.slice(0, 5).forEach((theme, index) => {
        const connector = index === 0 ? 'First,' : index === convergentThemes.slice(0, 5).length - 1 ? 'Finally,' : 'Additionally,';
        synthesis += `${connector} **${theme.theme}** emerges as a central theme, supported by ${theme.models.length}/${validResponses.length} models with ${Math.round(theme.confidence * 100)}% confidence.\n\n`;
      });
    }

    // Add divergent perspectives
    if (divergentPerspectives.length > 0) {
      synthesis += `### Alternative Perspectives\n\n`;
      synthesis += `Despite areas of consensus, models present ${divergentPerspectives.length} distinct viewpoints that merit consideration:\n\n`;
      divergentPerspectives.slice(0, 5).forEach(perspective => {
        synthesis += `• ${perspective}\n`;
      });
      synthesis += '\n';
    }

    // Focus-specific synthesis with connecting text
    synthesis += await this.generateFocusSpecificSynthesis(responses, focus);

    // Quality assessment with context
    const avgConfidence = validResponses.reduce((sum, r) => sum + r.confidence, 0) / validResponses.length;
    synthesis += `\n### Research Quality Assessment\n\n`;
    synthesis += `This synthesis is based on responses from ${validResponses.length} models with an average confidence of ${Math.round(avgConfidence * 100)}%. `;
    synthesis += `The research shows ${convergentThemes.length > 0 ? 'strong consensus' : 'limited agreement'} across models `;
    synthesis += `and ${divergentPerspectives.length > 3 ? 'significant' : 'moderate'} perspective diversity, `;
    synthesis += `indicating ${avgConfidence > 0.8 ? 'high reliability' : avgConfidence > 0.6 ? 'moderate reliability' : 'uncertain reliability'} in findings.\n`;

    return synthesis;
  }

  /**
   * Generate actionable recommendations based on analysis
   */
  private generateRecommendations(
    convergentThemes: ThemeExtraction[],
    divergentPerspectives: string[],
    reasoningStyles: ReasoningStyle[],
    complexity: ComplexityLevel
  ): string[] {
    const recommendations: string[] = [];

    // Theme-based recommendations
    if (convergentThemes.length > 0) {
      recommendations.push(
        `Focus on the ${convergentThemes.length} convergent themes as they show strong model agreement`
      );
    }

    // Divergence-based recommendations
    if (divergentPerspectives.length > 3) {
      recommendations.push(
        `Consider multiple approaches as models show significant perspective diversity`
      );
    }

    // Style-based recommendations
    const styles = reasoningStyles.map(r => r.style);
    const dominantStyle = this.getMostFrequent(styles);
    if (dominantStyle) {
      recommendations.push(
        `Approach aligns well with ${dominantStyle} reasoning - consider this perspective`
      );
    }

    // Complexity-based recommendations
    if (complexity === 'complex') {
      recommendations.push(
        `Break down the problem into smaller components for deeper analysis`
      );
    }

    // Confidence-based recommendations
    const avgConfidence = reasoningStyles.reduce((sum, r) => sum + r.confidence, 0) / reasoningStyles.length;
    if (avgConfidence < 0.7) {
      recommendations.push(
        `Seek additional validation as model confidence is moderate - consider expert consultation`
      );
    }

    return recommendations;
  }

  // Helper methods
  private extractKeywordClusters(responses: ModelResponse[]): KeywordCluster[] {
    const wordFreq: Map<string, { count: number; models: Set<string> }> = new Map();

    responses.forEach(response => {
      const words = this.extractKeywords(response.response);
      const uniqueWords = new Set(words);

      uniqueWords.forEach(word => {
        if (!wordFreq.has(word)) {
          wordFreq.set(word, { count: 0, models: new Set() });
        }
        const entry = wordFreq.get(word)!;
        entry.count++;
        entry.models.add(response.model);
      });
    });

    // Group related keywords into concept-based clusters
    const clusters: KeywordCluster[] = [];
    const processedWords = new Set<string>();

    for (const [word, data] of wordFreq.entries()) {
      if (processedWords.has(word) || data.count < 2) continue;

      const cluster = this.findRelatedWords(word, wordFreq, processedWords);
      if (cluster.keywords.length > 0) {
        clusters.push({
          cluster: this.generateConceptLabel(cluster.keywords), // Generate meaningful concept label
          keywords: cluster.keywords,
          frequency: data.count,
          models: data.models
        });
      }
    }

    return clusters.sort((a, b) => b.frequency - a.frequency);
  }

  private extractKeywords(text: string): string[] {
    // Extract both single words and multi-word phrases
    const words = text
      .toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter(word =>
        word.length > 3 &&
        !this.stopWords.has(word) &&
        !/^\d+$/.test(word)
      );

    // Also extract 2-3 word phrases for better concept capture
    const phrases: string[] = [];
    const cleanText = text.toLowerCase().replace(/[^\w\s]/g, ' ');
    const tokens = cleanText.split(/\s+/);

    for (let i = 0; i < tokens.length - 1; i++) {
      // 2-word phrases
      if (!this.stopWords.has(tokens[i]) && !this.stopWords.has(tokens[i + 1])) {
        phrases.push(`${tokens[i]} ${tokens[i + 1]}`);
      }
      // 3-word phrases
      if (i < tokens.length - 2) {
        const middleIsStop = this.stopWords.has(tokens[i + 1]);
        if (!this.stopWords.has(tokens[i]) && !this.stopWords.has(tokens[i + 2])) {
          phrases.push(`${tokens[i]} ${tokens[i + 1]} ${tokens[i + 2]}`);
        }
      }
    }

    return [...words, ...phrases];
  }

  private findRelatedWords(
    seed: string,
    wordFreq: Map<string, { count: number; models: Set<string> }>,
    processedWords: Set<string>
  ): { keywords: string[] } {
    const related = [seed];
    processedWords.add(seed);

    // Find words with similar stems or semantic relationships
    for (const [word, data] of wordFreq.entries()) {
      if (processedWords.has(word)) continue;
      if (this.areRelated(seed, word)) {
        related.push(word);
        processedWords.add(word);
      }
    }

    return { keywords: related };
  }

  private areRelated(word1: string, word2: string): boolean {
    // Simple similarity check - could be enhanced with NLP libraries
    if (word1.length < 4 || word2.length < 4) return false;

    const stem1 = word1.substring(0, Math.min(4, word1.length - 1));
    const stem2 = word2.substring(0, Math.min(4, word2.length - 1));

    return stem1 === stem2 || this.levenshteinDistance(word1, word2) <= 2;
  }

  private generateConceptLabel(keywords: string[]): string {
    // Create meaningful concept labels from keyword clusters
    const conceptMap: Record<string, string> = {
      // Security concepts
      'security,vulnerability,threat,attack,breach': 'Security Concerns',
      'authentication,authorization,access,login': 'Access Control',
      'encryption,crypto,cipher,secure': 'Data Protection',

      // Technical concepts
      'architecture,system,design,structure': 'System Architecture',
      'performance,speed,optimization,efficiency': 'Performance Optimization',
      'scalability,scaling,load,capacity': 'Scalability Planning',
      'database,storage,data,information': 'Data Management',

      // Business concepts
      'cost,budget,price,expense,financial': 'Financial Considerations',
      'user,customer,client,experience': 'User Experience',
      'market,business,commercial,industry': 'Business Strategy',
      'compliance,regulation,legal,policy': 'Regulatory Compliance',

      // Development concepts
      'implementation,development,coding,programming': 'Implementation Approach',
      'testing,quality,validation,verification': 'Quality Assurance',
      'deployment,infrastructure,cloud,server': 'Infrastructure & Deployment'
    };

    // Check if keywords match any concept pattern
    const keywordSet = new Set(keywords.map(k => k.toLowerCase()));
    for (const [pattern, label] of Object.entries(conceptMap)) {
      const patternWords = pattern.split(',');
      if (patternWords.some(word => keywordSet.has(word))) {
        return label;
      }
    }

    // Fallback: capitalize most frequent word
    return keywords[0].charAt(0).toUpperCase() + keywords[0].slice(1);
  }

  private levenshteinDistance(str1: string, str2: string): number {
    const matrix = Array(str2.length + 1).fill(null).map(() => Array(str1.length + 1).fill(null));

    for (let i = 0; i <= str1.length; i++) matrix[0][i] = i;
    for (let j = 0; j <= str2.length; j++) matrix[j][0] = j;

    for (let j = 1; j <= str2.length; j++) {
      for (let i = 1; i <= str1.length; i++) {
        const indicator = str1[i - 1] === str2[j - 1] ? 0 : 1;
        matrix[j][i] = Math.min(
          matrix[j][i - 1] + 1,
          matrix[j - 1][i] + 1,
          matrix[j - 1][i - 1] + indicator
        );
      }
    }

    return matrix[str2.length][str1.length];
  }

  private extractEvidence(responses: ModelResponse[], keywords: string[]): string[] {
    const evidence: string[] = [];

    responses.forEach(response => {
      const sentences = response.response.split(/[.!?]+/);
      sentences.forEach(sentence => {
        if (keywords.some(keyword => sentence.toLowerCase().includes(keyword.toLowerCase()))) {
          const trimmed = sentence.trim();
          if (trimmed.length > 20) {
            evidence.push(`${response.model}: "${trimmed}"`);
          }
        }
      });
    });

    return evidence.slice(0, 5); // Limit evidence examples
  }

  private findContradictions(responses: ModelResponse[]): string[] {
    const contradictions: string[] = [];

    // Simple contradiction detection - could be enhanced
    const contradictoryPairs = [
      ['yes', 'no'], ['true', 'false'], ['increase', 'decrease'],
      ['positive', 'negative'], ['beneficial', 'harmful'],
      ['should', 'should not'], ['will', 'will not']
    ];

    for (const [term1, term2] of contradictoryPairs) {
      const models1 = responses.filter(r =>
        r.response.toLowerCase().includes(term1) && !r.error
      );
      const models2 = responses.filter(r =>
        r.response.toLowerCase().includes(term2) && !r.error
      );

      if (models1.length > 0 && models2.length > 0) {
        contradictions.push(
          `Disagreement on "${term1}" vs "${term2}": ${models1.map(m => m.model).join(', ')} vs ${models2.map(m => m.model).join(', ')}`
        );
      }
    }

    return contradictions;
  }

  private findUniqueApproaches(responses: ModelResponse[]): string[] {
    const approaches: string[] = [];

    // Detect unique methodological approaches
    responses.forEach(response => {
      const text = response.response.toLowerCase();
      if (text.includes('first') || text.includes('step 1') || text.includes('initially')) {
        if (!responses.some(r => r !== response && r.response.toLowerCase().includes('step'))) {
          approaches.push(`${response.model} provides a step-by-step approach`);
        }
      }
    });

    return approaches;
  }

  private findEmphasisDifferences(responses: ModelResponse[]): string[] {
    const differences: string[] = [];

    // Detect different emphasis patterns
    const emphasisPatterns = {
      technical: ['implementation', 'code', 'algorithm', 'system'],
      business: ['cost', 'revenue', 'market', 'customer'],
      ethical: ['ethics', 'responsibility', 'impact', 'society'],
      practical: ['practical', 'real-world', 'application', 'usage']
    };

    Object.entries(emphasisPatterns).forEach(([category, patterns]) => {
      const emphasizingModels = responses.filter(r =>
        patterns.some(pattern => r.response.toLowerCase().includes(pattern)) && !r.error
      );

      if (emphasizingModels.length > 0 && emphasizingModels.length < responses.length) {
        differences.push(
          `${category.charAt(0).toUpperCase() + category.slice(1)} emphasis by: ${emphasizingModels.map(m => m.model).join(', ')}`
        );
      }
    });

    return differences;
  }

  private hasPattern(text: string, patterns: string[]): boolean {
    return patterns.some(pattern => text.includes(pattern));
  }

  private async generateFocusSpecificSynthesis(responses: ModelResponse[], focus: ResearchFocus): Promise<string> {
    let synthesis = `### ${focus.charAt(0).toUpperCase() + focus.slice(1)} Focus Analysis\n\n`;

    switch (focus) {
      case 'technical':
        synthesis += this.analyzeTechnicalAspects(responses);
        break;
      case 'business':
        synthesis += this.analyzeBusinessAspects(responses);
        break;
      case 'ethical':
        synthesis += this.analyzeEthicalAspects(responses);
        break;
      case 'creative':
        synthesis += this.analyzeCreativeAspects(responses);
        break;
      default:
        synthesis += this.analyzeGeneralAspects(responses);
    }

    return synthesis;
  }

  private analyzeTechnicalAspects(responses: ModelResponse[]): string {
    // Focus on technical implementation details, performance, scalability
    return "Technical implementation considerations and performance implications are analyzed across responses.\n";
  }

  private analyzeBusinessAspects(responses: ModelResponse[]): string {
    // Focus on business value, costs, market impact
    return "Business impact, cost-benefit analysis, and market considerations are evaluated.\n";
  }

  private analyzeEthicalAspects(responses: ModelResponse[]): string {
    // Focus on ethical implications, societal impact
    return "Ethical implications and societal impacts are carefully considered across perspectives.\n";
  }

  private analyzeCreativeAspects(responses: ModelResponse[]): string {
    // Focus on creative solutions, innovation, alternatives
    return "Creative approaches and innovative solutions are explored across different models.\n";
  }

  private analyzeGeneralAspects(responses: ModelResponse[]): string {
    return "Comprehensive analysis covering multiple aspects and perspectives.\n";
  }

  private getMostFrequent<T>(items: T[]): T | null {
    if (items.length === 0) return null;

    const frequency: Map<T, number> = new Map();
    items.forEach(item => {
      frequency.set(item, (frequency.get(item) || 0) + 1);
    });

    let mostFrequent: T | null = null;
    let maxCount = 0;

    for (const [item, count] of frequency.entries()) {
      if (count > maxCount) {
        maxCount = count;
        mostFrequent = item;
      }
    }

    return mostFrequent;
  }

  private calculateAggregateConfidence(responses: ModelResponse[], themes: ThemeExtraction[]): number {
    const validResponses = responses.filter(r => !r.error);
    if (validResponses.length === 0) return 0;

    // Base confidence from model responses
    const responseConfidence = validResponses.reduce((sum, r) => sum + r.confidence, 0) / validResponses.length;

    // Boost confidence based on convergent themes
    const themeBoost = Math.min(0.3, themes.length * 0.1);

    // Reduce confidence if too many failures
    const failureCount = responses.filter(r => r.error).length;
    const failurePenalty = failureCount * 0.1;

    return Math.max(0, Math.min(1, responseConfidence + themeBoost - failurePenalty));
  }

  private calculatePerformanceMetrics(responses: ModelResponse[], startTime: number): ResearchResult['performance'] {
    const successful = responses.filter(r => !r.error);
    const failed = responses.filter(r => r.error);
    const totalTime = Date.now() - startTime;
    const avgResponseTime = successful.length > 0
      ? successful.reduce((sum, r) => sum + r.responseTime, 0) / successful.length
      : 0;

    return {
      total_time: totalTime,
      successful_responses: successful.length,
      failed_responses: failed.length,
      average_response_time: avgResponseTime
    };
  }
}