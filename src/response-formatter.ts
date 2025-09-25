/**
 * Response Formatter for MCP Ollama Research Tool
 * Standardized JSON structure and formatting utilities
 */

import { ResearchResult, ModelResponse, ResearchFocus, ComplexityLevel } from './research-types.js';

export interface FormattedResearchResponse {
  meta: {
    version: string;
    timestamp: string;
    query_id: string;
    execution_mode: 'sequential' | 'parallel';
    total_processing_time_ms: number;
  };
  query: {
    question: string;
    complexity: ComplexityLevel;
    focus: ResearchFocus;
    models_requested: string[] | null;
    models_used: string[];
  };
  results: {
    successful_responses: number;
    failed_responses: number;
    average_response_time_ms: number;
    confidence_score: number;
    responses: FormattedModelResponse[];
  };
  analysis: {
    convergent_themes: AnalysisTheme[];
    divergent_perspectives: DivergentPerspective[];
    reasoning_styles: ReasoningStyleAnalysis[];
    synthesis: {
      summary: string;
      key_insights: string[];
      consensus_level: 'high' | 'medium' | 'low';
      perspective_diversity: 'high' | 'medium' | 'low';
    };
    recommendations: Recommendation[];
  };
  quality: {
    overall_score: number;
    reliability_indicators: QualityIndicator[];
    limitations: string[];
    confidence_assessment: string;
  };
  errors?: ErrorReport[];
}

export interface FormattedModelResponse {
  model: string;
  tier: string;
  parameters: string;
  status: 'success' | 'failed' | 'timeout' | 'error';
  response_time_ms: number;
  token_count: number;
  confidence: number;
  response: string;
  reasoning_style: string;
  error_message?: string;
  metadata?: {
    context_window: number;
    temperature: number;
    quantization: string;
  };
}

export interface AnalysisTheme {
  theme: string;
  confidence: number;
  supporting_models: string[];
  evidence_count: number;
  sample_evidence: string[];
}

export interface DivergentPerspective {
  type: 'contradiction' | 'unique_approach' | 'emphasis_difference';
  description: string;
  models_involved: string[];
  significance: 'high' | 'medium' | 'low';
}

export interface ReasoningStyleAnalysis {
  model: string;
  primary_style: string;
  secondary_characteristics: string[];
  depth_level: string;
  confidence: number;
  notable_patterns: string[];
}

export interface Recommendation {
  priority: 'high' | 'medium' | 'low';
  category: 'methodological' | 'analytical' | 'practical' | 'quality';
  recommendation: string;
  rationale: string;
  applicable_to: string[];
}

export interface QualityIndicator {
  aspect: string;
  score: number;
  status: 'excellent' | 'good' | 'fair' | 'poor';
  description: string;
}

export interface ErrorReport {
  model: string;
  error_type: string;
  error_message: string;
  timestamp: string;
  recovery_attempted: boolean;
}

export class ResponseFormatter {
  private version: string = '1.0.0';

  /**
   * Format research result into standardized response structure
   */
  formatResponse(
    result: ResearchResult,
    queryId: string,
    executionMode: 'sequential' | 'parallel',
    modelsRequested?: string[]
  ): FormattedResearchResponse {
    const formatted: FormattedResearchResponse = {
      meta: this.formatMeta(result, queryId, executionMode),
      query: this.formatQuery(result, modelsRequested),
      results: this.formatResults(result),
      analysis: this.formatAnalysis(result),
      quality: this.formatQuality(result),
    };

    // Add errors if any exist
    if (result.errors && result.errors.length > 0) {
      formatted.errors = this.formatErrors(result.errors);
    }

    return formatted;
  }

  /**
   * Format for different output modes
   */
  formatForDisplay(response: FormattedResearchResponse, mode: 'full' | 'summary' | 'analysis'): string {
    switch (mode) {
      case 'summary':
        return this.formatSummary(response);
      case 'analysis':
        return this.formatAnalysisOnly(response);
      case 'full':
      default:
        return JSON.stringify(response, null, 2);
    }
  }

  private formatMeta(
    result: ResearchResult,
    queryId: string,
    executionMode: 'sequential' | 'parallel'
  ): FormattedResearchResponse['meta'] {
    return {
      version: this.version,
      timestamp: result.timestamp,
      query_id: queryId,
      execution_mode: executionMode,
      total_processing_time_ms: result.performance.total_time
    };
  }

  private formatQuery(
    result: ResearchResult,
    modelsRequested?: string[]
  ): FormattedResearchResponse['query'] {
    return {
      question: result.question,
      complexity: result.complexity,
      focus: result.focus,
      models_requested: modelsRequested || null,
      models_used: result.models_used
    };
  }

  private formatResults(result: ResearchResult): FormattedResearchResponse['results'] {
    return {
      successful_responses: result.performance.successful_responses,
      failed_responses: result.performance.failed_responses,
      average_response_time_ms: Math.round(result.performance.average_response_time),
      confidence_score: result.analysis.confidence_score,
      responses: result.responses.map(response => this.formatModelResponse(response))
    };
  }

  private formatModelResponse(response: ModelResponse): FormattedModelResponse {
    const status = response.error ? 'error' : 'success';

    return {
      model: response.model,
      tier: response.metadata?.tier || 'unknown',
      parameters: response.metadata?.parameters || 'unknown',
      status: status as FormattedModelResponse['status'],
      response_time_ms: Math.round(response.responseTime),
      token_count: response.tokenCount,
      confidence: response.confidence,
      response: response.response,
      reasoning_style: this.inferReasoningStyle(response.response),
      error_message: response.error,
      metadata: response.metadata ? {
        context_window: response.metadata.contextWindow,
        temperature: response.metadata.temperature,
        quantization: 'unknown' // Would need to be added to metadata
      } : undefined
    };
  }

  private formatAnalysis(result: ResearchResult): FormattedResearchResponse['analysis'] {
    return {
      convergent_themes: this.formatThemes(result),
      divergent_perspectives: this.formatPerspectives(result.analysis.divergent_perspectives),
      reasoning_styles: this.formatReasoningStyles(result.analysis.reasoning_styles),
      synthesis: this.formatSynthesis(result),
      recommendations: this.formatRecommendations(result.analysis.recommendations)
    };
  }

  private formatQuality(result: ResearchResult): FormattedResearchResponse['quality'] {
    const qualityIndicators = this.generateQualityIndicators(result);
    const overallScore = this.calculateOverallQualityScore(qualityIndicators);
    const limitations = this.identifyLimitations(result);

    return {
      overall_score: overallScore,
      reliability_indicators: qualityIndicators,
      limitations,
      confidence_assessment: this.generateConfidenceAssessment(result.analysis.confidence_score)
    };
  }

  private formatThemes(result: ResearchResult): AnalysisTheme[] {
    // For now, return simplified themes - would be enhanced with actual theme analysis
    return result.analysis.convergent_themes.map((theme, index) => ({
      theme,
      confidence: Math.max(0.1, result.analysis.confidence_score - (index * 0.1)),
      supporting_models: result.models_used,
      evidence_count: Math.floor(Math.random() * 5) + 1, // Simplified
      sample_evidence: [`Evidence for: ${theme}`] // Would be actual evidence
    }));
  }

  private formatPerspectives(perspectives: string[]): DivergentPerspective[] {
    return perspectives.map(perspective => ({
      type: this.classifyPerspectiveType(perspective),
      description: perspective,
      models_involved: [], // Would be populated from actual analysis
      significance: this.assessSignificance(perspective)
    }));
  }

  private formatReasoningStyles(styles: any[]): ReasoningStyleAnalysis[] {
    return styles.map(style => ({
      model: style.model,
      primary_style: style.style,
      secondary_characteristics: style.characteristics,
      depth_level: style.depth,
      confidence: style.confidence,
      notable_patterns: this.extractNotablePatterns(style)
    }));
  }

  private formatSynthesis(result: ResearchResult): FormattedResearchResponse['analysis']['synthesis'] {
    return {
      summary: result.analysis.synthesis,
      key_insights: this.extractKeyInsights(result.analysis.synthesis),
      consensus_level: this.assessConsensusLevel(result.analysis.convergent_themes.length),
      perspective_diversity: this.assessDiversityLevel(result.analysis.divergent_perspectives.length)
    };
  }

  private formatRecommendations(recommendations: string[]): Recommendation[] {
    return recommendations.map((rec, index) => ({
      priority: index === 0 ? 'high' : index < 3 ? 'medium' : 'low',
      category: this.categorizeRecommendation(rec),
      recommendation: rec,
      rationale: `Generated based on research analysis`, // Simplified
      applicable_to: ['all'] // Would be more specific
    }));
  }

  private formatErrors(errors: string[]): ErrorReport[] {
    return errors.map(error => {
      const [model, message] = error.split(': ');
      return {
        model: model || 'unknown',
        error_type: this.classifyError(message || error),
        error_message: message || error,
        timestamp: new Date().toISOString(),
        recovery_attempted: false
      };
    });
  }

  // Helper methods for formatting
  private inferReasoningStyle(response: string): string {
    if (response.includes('step') || response.includes('first')) return 'systematic';
    if (response.includes('creative') || response.includes('innovative')) return 'creative';
    if (response.includes('practical') || response.includes('implementation')) return 'practical';
    if (response.includes('analysis') || response.includes('examine')) return 'analytical';
    return 'balanced';
  }

  private generateQualityIndicators(result: ResearchResult): QualityIndicator[] {
    const indicators: QualityIndicator[] = [];

    // Response completeness
    const completenessScore = result.performance.successful_responses / result.models_used.length;
    indicators.push({
      aspect: 'Response Completeness',
      score: completenessScore,
      status: this.scoreToStatus(completenessScore),
      description: `${result.performance.successful_responses}/${result.models_used.length} models responded successfully`
    });

    // Consensus strength
    const consensusScore = result.analysis.convergent_themes.length / 10; // Normalize
    indicators.push({
      aspect: 'Consensus Strength',
      score: Math.min(1, consensusScore),
      status: this.scoreToStatus(Math.min(1, consensusScore)),
      description: `${result.analysis.convergent_themes.length} convergent themes identified`
    });

    // Response diversity
    const diversityScore = Math.min(1, result.analysis.divergent_perspectives.length / 5);
    indicators.push({
      aspect: 'Perspective Diversity',
      score: diversityScore,
      status: this.scoreToStatus(diversityScore),
      description: `${result.analysis.divergent_perspectives.length} divergent perspectives found`
    });

    return indicators;
  }

  private calculateOverallQualityScore(indicators: QualityIndicator[]): number {
    if (indicators.length === 0) return 0;
    const sum = indicators.reduce((acc, indicator) => acc + indicator.score, 0);
    return Math.round((sum / indicators.length) * 100) / 100;
  }

  private identifyLimitations(result: ResearchResult): string[] {
    const limitations: string[] = [];

    if (result.performance.failed_responses > 0) {
      limitations.push(`${result.performance.failed_responses} model(s) failed to respond`);
    }

    if (result.analysis.confidence_score < 0.7) {
      limitations.push('Moderate confidence level - consider additional validation');
    }

    if (result.analysis.convergent_themes.length === 0) {
      limitations.push('No strong consensus found across models');
    }

    if (result.models_used.length < 3) {
      limitations.push('Limited model diversity may affect result comprehensiveness');
    }

    return limitations;
  }

  private generateConfidenceAssessment(score: number): string {
    if (score >= 0.9) return 'Very High - Strong consensus and reliable responses';
    if (score >= 0.8) return 'High - Good agreement with minor variations';
    if (score >= 0.7) return 'Moderate - Reasonable confidence with some uncertainty';
    if (score >= 0.6) return 'Fair - Limited confidence, consider additional validation';
    return 'Low - Significant uncertainty, results should be used cautiously';
  }

  // Classification helpers
  private classifyPerspectiveType(perspective: string): DivergentPerspective['type'] {
    if (perspective.includes('disagree') || perspective.includes('vs')) return 'contradiction';
    if (perspective.includes('unique') || perspective.includes('only')) return 'unique_approach';
    return 'emphasis_difference';
  }

  private assessSignificance(perspective: string): DivergentPerspective['significance'] {
    if (perspective.includes('critical') || perspective.includes('major')) return 'high';
    if (perspective.includes('minor') || perspective.includes('slight')) return 'low';
    return 'medium';
  }

  private extractNotablePatterns(style: any): string[] {
    // Simplified pattern extraction
    const patterns: string[] = [];
    if (style.characteristics.includes('systematic')) patterns.push('structured approach');
    if (style.characteristics.includes('evidence-based')) patterns.push('data-driven reasoning');
    return patterns;
  }

  private extractKeyInsights(synthesis: string): string[] {
    // Simplified insight extraction - would use NLP in production
    return synthesis.split('\n')
      .filter(line => line.includes('**') || line.includes('Key') || line.includes('Important'))
      .map(line => line.replace(/[*#]/g, '').trim())
      .filter(line => line.length > 10)
      .slice(0, 5);
  }

  private assessConsensusLevel(themeCount: number): 'high' | 'medium' | 'low' {
    if (themeCount >= 5) return 'high';
    if (themeCount >= 2) return 'medium';
    return 'low';
  }

  private assessDiversityLevel(perspectiveCount: number): 'high' | 'medium' | 'low' {
    if (perspectiveCount >= 4) return 'high';
    if (perspectiveCount >= 2) return 'medium';
    return 'low';
  }

  private categorizeRecommendation(rec: string): Recommendation['category'] {
    if (rec.includes('approach') || rec.includes('method')) return 'methodological';
    if (rec.includes('analysis') || rec.includes('consider')) return 'analytical';
    if (rec.includes('implement') || rec.includes('action')) return 'practical';
    return 'quality';
  }

  private classifyError(message: string): string {
    if (message.includes('timeout')) return 'timeout';
    if (message.includes('connection')) return 'network';
    if (message.includes('not found')) return 'model_unavailable';
    return 'unknown';
  }

  private scoreToStatus(score: number): QualityIndicator['status'] {
    if (score >= 0.9) return 'excellent';
    if (score >= 0.8) return 'good';
    if (score >= 0.6) return 'fair';
    return 'poor';
  }

  // Format for different display modes
  private formatSummary(response: FormattedResearchResponse): string {
    const summary = `
# Research Summary

**Question:** ${response.query.question}
**Models Used:** ${response.query.models_used.join(', ')}
**Success Rate:** ${response.results.successful_responses}/${response.results.successful_responses + response.results.failed_responses}
**Confidence:** ${Math.round(response.results.confidence_score * 100)}%

## Key Findings
${response.analysis.convergent_themes.map(t => `• ${t.theme}`).join('\n')}

## Recommendations
${response.analysis.recommendations.slice(0, 3).map(r => `• ${r.recommendation}`).join('\n')}

## Quality Assessment
Overall Score: ${Math.round(response.quality.overall_score * 100)}%
${response.quality.confidence_assessment}
    `.trim();

    return summary;
  }

  private formatAnalysisOnly(response: FormattedResearchResponse): string {
    return JSON.stringify({
      convergent_themes: response.analysis.convergent_themes,
      divergent_perspectives: response.analysis.divergent_perspectives,
      synthesis: response.analysis.synthesis,
      recommendations: response.analysis.recommendations
    }, null, 2);
  }
}