#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "requests>=2.32.3",
# ]
# ///

"""
PreCompact Hook - Agent-Based Intelligent Conversation Summarization

This hook runs before Claude compacts context, using the codex-session-analyzer agent
for structured analysis with comprehensive fallback support:

Primary Method:
- Uses codex-session-analyzer agent via Claude Code Task tool
- JSON input/output format for structured data
- Generates analysis, executive, actions, and insights summaries

Fallback Methods:
- Legacy codex-summarize.sh system (secondary)
- Minimal git-based analysis (tertiary)

Features:
- Context-aware TTS notifications based on analysis content
- Enhanced observability with structured data
- Zero-token local processing via Codex CLI or agent system
- Robust three-tier error handling

Updated: 2025-07-28 - Agent integration complete
"""

import json
import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path
import tempfile
import re

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(os.path.expanduser('~/.claude/logs/pre_compact.log')),
        logging.StreamHandler()
    ]
)

def get_git_context():
    """Get git context for the session analysis"""
    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        
        # Get recent commits
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            capture_output=True,
            text=True,
            timeout=5
        )
        recent_commits = log_result.stdout.strip().split('\n') if log_result.returncode == 0 else []
        
        # Get status
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )
        changes = status_result.stdout.strip().split('\n') if status_result.returncode == 0 and status_result.stdout.strip() else []
        
        return {
            "current_branch": current_branch,
            "recent_commits": recent_commits,
            "pending_changes": changes
        }
    except Exception as e:
        logging.error(f"Error getting git context: {e}")
        return {
            "current_branch": "unknown",
            "recent_commits": [],
            "pending_changes": []
        }

def export_conversation():
    """Export current conversation to a temporary file"""
    try:
        # Create temporary file for conversation export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            temp_file = f.name
            
            # Get conversation from stdin or environment
            conversation_data = sys.stdin.read() if not sys.stdin.isatty() else ""
            
            # If no stdin, try to get from environment or hook data
            if not conversation_data:
                # Check for conversation in environment variables
                hook_data = os.environ.get('CLAUDE_HOOK_DATA', '{}')
                try:
                    data = json.loads(hook_data)
                    conversation_data = data.get('conversation', '')
                except:
                    conversation_data = ""
            
            if conversation_data:
                f.write(conversation_data)
                logging.info(f"Exported conversation to {temp_file} ({len(conversation_data)} bytes)")
                return temp_file
            else:
                logging.warning("No conversation data available")
                return None
                
    except Exception as e:
        logging.error(f"Error exporting conversation: {e}")
        return None

def should_generate_actions(conversation_file):
    """Check if conversation contains action items"""
    try:
        with open(conversation_file, 'r') as f:
            content = f.read().lower()
        
        action_keywords = ['todo', 'task', 'need to', 'should', 'must', 'will do', 'action item']
        action_count = sum(content.count(keyword) for keyword in action_keywords)
        
        return action_count >= 3  # Simple threshold
    except:
        return False

def should_generate_lessons(conversation_file):
    """Check if conversation contains lessons learned"""
    try:
        with open(conversation_file, 'r') as f:
            content = f.read().lower()
        
        lesson_keywords = ['learned', 'insight', 'realize', 'discovered', 'found that']
        lesson_count = sum(content.count(keyword) for keyword in lesson_keywords)
        
        return lesson_count >= 2  # Simple threshold
    except:
        return False

def invoke_session_analyzer(conversation_content, working_dir):
    """Invoke codex-session-analyzer agent using Task tool with fallback"""
    try:
        # Prepare input data for the agent
        agent_input = {
            "session_summary": conversation_content,
            "working_dir": working_dir,
            "git_context": get_git_context()
        }
        
        logging.info("Attempting to invoke codex-session-analyzer agent")
        
        # Invoke the codex-session-analyzer agent using direct execution
        try:
            logging.info("Invoking codex-session-analyzer agent via direct execution")
            
            # Use the claude_agent_runner.py script for direct agent execution
            script_dir = os.path.dirname(os.path.abspath(__file__))
            agent_runner_path = os.path.join(script_dir, "utils", "claude_agent_runner.py")
            
            # Prepare JSON input for the agent
            agent_input_json = json.dumps(agent_input)
            
            # Execute the agent runner with subprocess
            result = subprocess.run(
                ["python3", agent_runner_path, "codex-session-analyzer"],
                input=agent_input_json,
                capture_output=True,
                text=True,
                timeout=60  # Allow up to 60 seconds for agent execution
            )
            
            if result.returncode != 0:
                logging.warning(f"Agent runner failed with exit code {result.returncode}")
                logging.debug(f"Agent runner stderr: {result.stderr}")
                return None
            
            # Parse the JSON response from the agent runner
            try:
                agent_response = json.loads(result.stdout)
                
                # Check for error in response
                if "error" in agent_response:
                    logging.warning(f"Agent returned error: {agent_response['error']}")
                    return None
                
                # Validate the expected response structure
                expected_keys = ["achievements", "next_steps", "blockers", "insights"]
                if not any(key in agent_response for key in expected_keys):
                    logging.warning("Agent response missing expected keys, treating as invalid")
                    return None
                
                logging.info("Session analysis completed successfully via codex-session-analyzer agent")
                return agent_response
                
            except json.JSONDecodeError as parse_error:
                logging.warning(f"Failed to parse agent JSON response: {parse_error}")
                logging.debug(f"Raw agent response: {result.stdout}")
                return None
            
        except subprocess.TimeoutExpired:
            logging.warning("Agent execution timed out after 60 seconds")
            return None
        except FileNotFoundError:
            logging.warning("Agent runner script not found - check installation")
            return None
        except Exception as agent_error:
            logging.warning(f"Agent invocation failed: {agent_error}")
            return None
                
    except Exception as e:
        logging.error(f"Error preparing agent invocation: {e}")
        return None

def fallback_to_legacy_analysis(conversation_file, working_dir):
    """Fallback to legacy codex-summarize.sh analysis if agent fails"""
    try:
        logging.info("Attempting fallback to legacy codex-summarize.sh")
        
        # Find codex-summarize.sh
        legacy_paths = [
            "/home/bryan/setup-mcp-server.sh.APP/tests/export-codex/codex-summarize.sh",
        ]
        
        codex_path = None
        for path in legacy_paths:
            if os.path.exists(path):
                codex_path = path
                break
        
        if not codex_path:
            logging.warning("Legacy codex-summarize.sh not found, generating minimal analysis")
            return generate_minimal_analysis(working_dir)
        
        logging.info(f"Using legacy codex-summarize.sh at: {codex_path}")
        
        # Generate basic technical summary
        cmd = [codex_path, "-t", "technical", conversation_file]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            summary_content = result.stdout.strip()
            
            # Convert legacy format to agent format
            analysis_result = {
                "achievements": ["Technical analysis completed via legacy system"],
                "next_steps": ["Review generated summary", "Continue development"],
                "blockers": [],
                "insights": ["Legacy analysis system used as fallback"],
                "session_metrics": {
                    "duration": "unknown",
                    "complexity": "medium",
                    "analysis_method": "legacy"
                },
                "legacy_content": summary_content
            }
            
            logging.info("Fallback analysis completed successfully")
            return analysis_result
        else:
            logging.error(f"Legacy analysis failed: {result.stderr}")
            return generate_minimal_analysis(working_dir)
            
    except Exception as e:
        logging.error(f"Fallback analysis failed: {e}")
        return generate_minimal_analysis(working_dir)

def generate_minimal_analysis(working_dir):
    """Generate minimal analysis when all other methods fail"""
    try:
        git_context = get_git_context()
        files_modified = len(git_context["pending_changes"])
        
        return {
            "achievements": ["Session context captured", "Minimal analysis completed"],
            "next_steps": ["Continue development", "Consider using full analysis tools"],
            "blockers": ["Analysis tools unavailable"],
            "insights": ["Basic session information preserved"],
            "session_metrics": {
                "duration": "unknown",
                "complexity": "unknown",
                "files_modified": files_modified,
                "analysis_method": "minimal"
            }
        }
    except Exception as e:
        logging.error(f"Even minimal analysis failed: {e}")
        return {
            "achievements": ["PreCompact hook executed"],
            "next_steps": ["Check system configuration"],
            "blockers": ["Analysis system unavailable"],
            "insights": ["System requires troubleshooting"],
            "session_metrics": {
                "analysis_method": "emergency"
            }
        }

def format_analysis_content(analysis_result):
    """Format the full analysis result into markdown content"""
    content = []
    content.append("# Session Analysis Report")
    content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    
    if analysis_result.get('achievements'):
        content.append("## Achievements")
        for achievement in analysis_result['achievements']:
            content.append(f"- {achievement}")
        content.append("")
    
    if analysis_result.get('next_steps'):
        content.append("## Next Steps")
        for i, step in enumerate(analysis_result['next_steps'], 1):
            content.append(f"{i}. {step}")
        content.append("")
    
    if analysis_result.get('blockers'):
        content.append("## Blockers")
        for blocker in analysis_result['blockers']:
            content.append(f"- {blocker}")
        content.append("")
    
    if analysis_result.get('insights'):
        content.append("## Insights")
        for insight in analysis_result['insights']:
            content.append(f"- {insight}")
        content.append("")
    
    if analysis_result.get('session_metrics'):
        content.append("## Session Metrics")
        metrics = analysis_result['session_metrics']
        for key, value in metrics.items():
            content.append(f"- {key.replace('_', ' ').title()}: {value}")
        content.append("")
    
    # Include legacy content if available (from fallback analysis)
    if analysis_result.get('legacy_content'):
        content.append("## Legacy Analysis Content")
        content.append("")
        content.append(analysis_result['legacy_content'])
        content.append("")
    
    return "\n".join(content)

def format_executive_summary(analysis_result):
    """Format executive summary from analysis results"""
    content = []
    content.append("# Executive Summary")
    content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    
    achievements = analysis_result.get('achievements', [])
    if achievements:
        content.append("## Key Accomplishments")
        for achievement in achievements[:3]:  # Top 3 achievements
            content.append(f"- {achievement}")
        content.append("")
    
    next_steps = analysis_result.get('next_steps', [])
    if next_steps:
        content.append("## Immediate Next Steps")
        for i, step in enumerate(next_steps[:5], 1):  # Top 5 next steps
            content.append(f"{i}. {step}")
        content.append("")
    
    blockers = analysis_result.get('blockers', [])
    if blockers:
        content.append("## Current Blockers")
        for blocker in blockers:
            content.append(f"- {blocker}")
        content.append("")
    
    return "\n".join(content)

def format_action_items(analysis_result):
    """Format action items from analysis results"""
    content = []
    content.append("# Action Items")
    content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    
    next_steps = analysis_result.get('next_steps', [])
    if next_steps:
        content.append("## Pending Tasks")
        for i, step in enumerate(next_steps, 1):
            content.append(f"**Task {i}**: {step}")
            content.append("- Priority: Medium")
            content.append("- Status: Pending")
            content.append("")
    
    blockers = analysis_result.get('blockers', [])
    if blockers:
        content.append("## Blockers to Resolve")
        for i, blocker in enumerate(blockers, 1):
            content.append(f"**Blocker {i}**: {blocker}")
            content.append("- Priority: High")
            content.append("- Status: Active")
            content.append("")
    
    return "\n".join(content)

def format_insights(analysis_result):
    """Format insights and lessons learned from analysis results"""
    content = []
    content.append("# Insights and Lessons Learned")
    content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    
    insights = analysis_result.get('insights', [])
    if insights:
        content.append("## Key Insights")
        for insight in insights:
            content.append(f"- {insight}")
        content.append("")
    
    if analysis_result.get('session_metrics'):
        content.append("## Session Analysis")
        metrics = analysis_result['session_metrics']
        content.append(f"- Complexity Level: {metrics.get('complexity', 'Unknown')}")
        content.append(f"- Files Modified: {metrics.get('files_modified', 0)}")
        content.append("")
    
    return "\n".join(content)

def extract_tts_brief_from_analysis(analysis_result):
    """Extract a brief TTS-friendly message from analysis results"""
    achievements = analysis_result.get('achievements', [])
    next_steps = analysis_result.get('next_steps', [])
    blockers = analysis_result.get('blockers', [])
    
    if blockers:
        return f"{len(achievements)} items completed, {len(blockers)} blockers identified"
    elif achievements and next_steps:
        return f"{len(achievements)} achievements documented, {len(next_steps)} next steps identified"
    elif achievements:
        return f"{len(achievements)} achievements captured"
    elif next_steps:
        return f"{len(next_steps)} action items identified"
    else:
        return "Session analysis completed"

def extract_tts_brief(summary_type, content):
    """Extract a brief TTS-friendly message from summary content"""
    if not content:
        return ""
    
    if summary_type == 'executive':
        # Parse executive summary with improved format handling
        lines = content.split('\n')
        objective = ""
        outcome = ""
        in_objective = False
        in_outcome = False
        
        for line in lines:
            clean_line = line.replace('**', '').replace('*', '').strip()
            
            # Check section headers
            if 'objective' in clean_line.lower():
                in_objective = True
                in_outcome = False
                continue
            elif 'outcome' in clean_line.lower():
                in_outcome = True
                in_objective = False
                continue
            elif '---' in clean_line or 'key decision' in clean_line.lower():
                in_objective = False
                in_outcome = False
            
            # Capture content
            if in_objective and clean_line and not clean_line.startswith('['):
                if not objective:
                    objective = clean_line
            elif in_outcome and clean_line and not clean_line.startswith('['):
                # Handle bullet points
                if clean_line.startswith('-') or clean_line.startswith('•'):
                    clean_line = clean_line[1:].strip()
                if not outcome and clean_line:
                    outcome = clean_line
        
        # Build message
        parts = []
        if objective:
            # Extract key part after "to" if present
            obj_clean = objective.lower()
            if ' to ' in obj_clean:
                key_part = obj_clean.split(' to ', 1)[1]
                parts.append(f"Goal was to {key_part[:35]}")
            else:
                parts.append(f"Goal was {obj_clean[:40]}")
        if outcome:
            parts.append(f"Achieved {outcome.lower()[:35]}")
        
        return '. '.join(parts) if parts else "Session saved"
    
    elif summary_type == 'action':
        # Count action items more accurately
        lines = content.split('\n')
        action_count = 0
        
        # Look for actual task/action lines (skip metadata)
        in_task_section = False
        for line in lines:
            # Skip metadata sections
            if line.startswith('[') or '---' in line or 'thinking' in line:
                continue
            # Look for priority headers or task markers
            if '**Priority**:' in line or '**High**' in line or '**Medium**' in line or '**Low**' in line:
                in_task_section = True
            elif in_task_section and line.strip() and any(marker in line[:5] for marker in ['•', '-', '*', '1.', '2.', '3.']):
                action_count += 1
        
        if action_count == 1:
            return "One action item captured"
        elif action_count > 1:
            return f"{action_count} action items captured"
        else:
            return "Action items captured"
    
    elif summary_type == 'lessons':
        # Simple lessons indicator
        if 'lesson' in content.lower() or 'learned' in content.lower():
            return "Lessons learned captured"
    
    return ""

def generate_summaries(conversation_file):
    """Generate all relevant summaries using codex-session-analyzer agent"""
    summaries = {}
    
    # Get project name and timestamp for file naming
    project_name = os.path.basename(os.getcwd())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    working_dir = os.getcwd()
    
    # Create summaries directory if it doesn't exist
    summaries_dir = os.path.expanduser("~/.claude/summaries")
    os.makedirs(summaries_dir, exist_ok=True)
    
    # Read conversation content
    try:
        with open(conversation_file, 'r') as f:
            conversation_content = f.read()
    except Exception as e:
        logging.error(f"Error reading conversation file: {e}")
        return summaries
    
    # Invoke session analyzer agent
    analysis_result = invoke_session_analyzer(conversation_content, working_dir)
    
    # Fallback if agent fails
    if not analysis_result:
        logging.warning("Agent analysis failed, attempting fallback to legacy system")
        analysis_result = fallback_to_legacy_analysis(conversation_file, working_dir)
        
        if not analysis_result:
            logging.error("All analysis methods failed")
            return summaries
    
    # Generate comprehensive analysis file
    analysis_file = os.path.join(summaries_dir, f"{project_name}_analysis_{timestamp}.md")
    analysis_content = format_analysis_content(analysis_result)
    
    try:
        with open(analysis_file, 'w') as f:
            f.write(analysis_content)
        summaries['analysis_file'] = analysis_file
        summaries['analysis_result'] = analysis_result
        logging.info(f"Session analysis saved to {analysis_file}")
    except Exception as e:
        logging.error(f"Error saving analysis file: {e}")
    
    # Generate executive summary from achievements
    if analysis_result.get('achievements'):
        exec_content = format_executive_summary(analysis_result)
        exec_file = os.path.join(summaries_dir, f"{project_name}_executive_{timestamp}.md")
        try:
            with open(exec_file, 'w') as f:
                f.write(exec_content)
            summaries['executive_file'] = exec_file
            summaries['executive_brief'] = extract_tts_brief_from_analysis(analysis_result)
            logging.info(f"Executive summary saved to {exec_file}")
        except Exception as e:
            logging.error(f"Error saving executive summary: {e}")
    
    # Generate action items if available
    if analysis_result.get('next_steps'):
        action_content = format_action_items(analysis_result)
        action_file = os.path.join(summaries_dir, f"{project_name}_actions_{timestamp}.md")
        try:
            with open(action_file, 'w') as f:
                f.write(action_content)
            summaries['action_file'] = action_file
            summaries['action_brief'] = f"{len(analysis_result['next_steps'])} action items captured"
            logging.info(f"Action items saved to {action_file}")
        except Exception as e:
            logging.error(f"Error saving action items: {e}")
    
    # Generate insights/lessons if available
    if analysis_result.get('insights'):
        insights_content = format_insights(analysis_result)
        insights_file = os.path.join(summaries_dir, f"{project_name}_insights_{timestamp}.md")
        try:
            with open(insights_file, 'w') as f:
                f.write(insights_content)
            summaries['insights_file'] = insights_file
            logging.info(f"Insights saved to {insights_file}")
        except Exception as e:
            logging.error(f"Error saving insights: {e}")
    
    return summaries

def create_tts_message(summaries):
    """Create a context-aware TTS message from available summaries"""
    # Check if we have analysis results from the agent
    analysis_result = summaries.get('analysis_result')
    if analysis_result:
        return create_tts_message_from_analysis(analysis_result, summaries)
    
    # Fallback to old format for backward compatibility
    has_actions = 'action_brief' in summaries and summaries['action_brief']
    has_executive = 'executive_brief' in summaries and summaries['executive_brief']
    has_lessons = 'lessons_file' in summaries
    
    # Build contextual message
    if has_actions and has_executive:
        # Both action items and executive summary
        action_msg = summaries['action_brief']
        exec_msg = summaries['executive_brief']
        
        # Combine intelligently
        if "goal was" in exec_msg.lower():
            return f"{exec_msg}. Also {action_msg.lower()}"
        else:
            return action_msg  # Action items are more urgent
    
    elif has_actions:
        return summaries['action_brief']
    
    elif has_executive:
        # Add context if we also have lessons
        msg = summaries['executive_brief']
        if has_lessons:
            return f"{msg}. Lessons learned documented"
        return msg
    
    else:
        # Generic but informative
        count = len([k for k in summaries if k.endswith('_file')])
        types = []
        if 'technical_file' in summaries:
            types.append("technical")
        if has_lessons:
            types.append("lessons")
        
        if types:
            return f"Saved {', '.join(types)} summaries"
        return f"Saved {count} summaries"

def create_tts_message_from_analysis(analysis_result, summaries):
    """Create TTS message from agent analysis results"""
    achievements = analysis_result.get('achievements', [])
    next_steps = analysis_result.get('next_steps', [])
    blockers = analysis_result.get('blockers', [])
    insights = analysis_result.get('insights', [])
    
    # Prioritize based on content
    if blockers:
        if achievements:
            return f"Session complete: {len(achievements)} achievements, but {len(blockers)} blockers need attention"
        else:
            return f"Session analyzed: {len(blockers)} blockers identified requiring immediate action"
    
    elif achievements and next_steps:
        return f"Session complete: {len(achievements)} achievements documented, {len(next_steps)} next steps identified"
    
    elif achievements:
        if insights:
            return f"Session complete: {len(achievements)} achievements captured with insights documented"
        else:
            return f"Session complete: {len(achievements)} achievements documented"
    
    elif next_steps:
        return f"Session analyzed: {len(next_steps)} action items identified for continuation"
    
    elif insights:
        return f"Session analyzed: insights and lessons learned captured"
    
    else:
        # Count files generated
        file_count = len([k for k in summaries if k.endswith('_file')])
        return f"Session analysis complete: {file_count} summary files generated"

def send_to_tts(message):
    """Send personalized summary to TTS with context-aware formatting"""
    try:
        engineer_name = os.environ.get('ENGINEER_NAME', 'Developer')
        
        # Context-aware formatting
        if "action item" in message.lower():
            # Urgent tone for action items
            full_message = f"{engineer_name}, attention needed. Context saved with {message}"
        elif "goal was" in message.lower():
            # Completion tone
            full_message = f"{engineer_name}, session complete. {message}"
        elif "lesson" in message.lower():
            # Learning tone
            full_message = f"{engineer_name}, insights captured. {message}"
        elif len(message) > 60:
            # Fallback for long messages
            full_message = f"{engineer_name}, context saved. Multiple summaries generated"
        else:
            # Default
            full_message = f"{engineer_name}, compacting context. {message}"
        
        # Use speak command
        subprocess.Popen(
            ["speak", full_message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logging.info(f"Sent to TTS: {full_message}")
        
    except Exception as e:
        logging.error(f"Failed to send to TTS: {e}")

def notify_observability(summaries):
    """Send enhanced summary event to observability system"""
    try:
        # Count action items if available
        action_count = 0
        if 'action_brief' in summaries:
            # Extract count from the brief message
            match = re.search(r'(\d+)\s+action\s+items?', summaries['action_brief'])
            if match:
                action_count = int(match.group(1))
            elif 'one action item' in summaries['action_brief'].lower():
                action_count = 1
        
        # Enhanced event data
        event_data = {
            "hook_type": "PreCompact",
            "summary_generated": True,
            "summaries_count": len([k for k in summaries if k.endswith('_file')]),
            "summary_types": {
                "technical": 'technical_file' in summaries,
                "executive": 'executive_file' in summaries,
                "actions": 'action_file' in summaries,
                "lessons": 'lessons_file' in summaries
            },
            "action_items_count": action_count,
            "tts_message": summaries.get('tts_message', ''),
            "project": os.path.basename(os.getcwd()),
            "timestamp": datetime.now().isoformat()
        }
        
        # Add file paths for reference
        for key, value in summaries.items():
            if key.endswith('_file'):
                event_data[f"file_{key.replace('_file', '')}"] = value
        
        logging.info(f"PreCompact event: {json.dumps(event_data, indent=2)}")
        
    except Exception as e:
        logging.error(f"Failed to notify observability: {e}")

def main():
    """Main hook execution"""
    logging.info("=== PreCompact Hook Started ===")
    
    # Export conversation
    conversation_file = export_conversation()
    if not conversation_file:
        logging.warning("No conversation to summarize")
        send_to_tts("Context compaction started, no conversation to summarize")
        return
    
    try:
        # Generate summaries using codex-session-analyzer agent
        summaries = generate_summaries(conversation_file)
        
        if not summaries:
            logging.error("Failed to generate summaries - agent may be unavailable")
            send_to_tts("Context compaction started, analysis unavailable")
            return
        
        # Send TTS notification
        tts_message = create_tts_message(summaries)
        summaries['tts_message'] = tts_message  # Store for observability
        send_to_tts(tts_message)
        
        # Notify observability with enhanced data
        notify_observability(summaries)
        
        # Log summary locations
        for key, value in summaries.items():
            if key.endswith('_file'):
                logging.info(f"{key}: {value}")
            
    finally:
        # Clean up temporary file
        if conversation_file and os.path.exists(conversation_file):
            try:
                os.unlink(conversation_file)
                logging.debug(f"Cleaned up temporary file: {conversation_file}")
            except:
                pass
    
    logging.info("=== PreCompact Hook Completed ===")

if __name__ == "__main__":
    main()