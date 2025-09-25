# Troubleshooting Guide

Comprehensive troubleshooting guide for the MCP Ollama Research Tool, covering common issues, solutions, and debugging techniques.

## 🚨 Quick Diagnostics

### Health Check Command

First, verify that your system is working correctly:

```bash
# Check if Ollama is running
curl http://127.0.0.1:11434/api/tags

# Check if models are available
ollama list

# Test MCP server
node build/index.js

# Test with MCP Inspector
npm run inspector
```

### System Requirements Check

```bash
# Node.js version (should be 18+)
node --version

# NPM version
npm --version

# Ollama version
ollama --version

# Available disk space
df -h

# Available memory
free -m
```

## 🔧 Common Issues & Solutions

### 1. Research Tool Issues

#### Issue: "No suitable models available"

**Symptoms:**
```
Research execution failed: No suitable models available for the requested complexity level
```

**Causes:**
- No models installed in Ollama
- Models don't support requested complexity level
- Ollama server not running

**Solutions:**

**Step 1: Check Ollama Status**
```bash
# Check if Ollama is running
curl http://127.0.0.1:11434/api/tags

# If not running, start it
ollama serve
```

**Step 2: Install Required Models**
```bash
# Install fast models for simple complexity
ollama pull llama3.2:1b

# Install medium models for medium complexity
ollama pull llama3.2:7b
ollama pull qwen2.5:7b
ollama pull mistral:7b

# Install large models for complex complexity
ollama pull llama3.2:13b
```

**Step 3: Test Model Availability**
```bash
# List available models
ollama list

# Test a specific model
ollama run llama3.2:7b "Hello, world!"
```

**Step 4: Use Specific Models**
If automatic selection fails, specify models manually:
```json
{
  "tool": "research",
  "question": "What is TypeScript?",
  "models": ["llama3.2:7b", "mistral:7b"],
  "complexity": "simple"
}
```

#### Issue: Timeout Errors

**Symptoms:**
```
Research request timed out after 180000ms
Model llama3.2:70b failed: Timeout after 60000ms
```

**Causes:**
- Models too large for available resources
- Complex queries requiring more processing time
- System resource constraints

**Solutions:**

**Step 1: Adjust Timeout Values**
```json
{
  "tool": "research",
  "question": "Complex analysis question",
  "complexity": "complex",
  "timeout": 300000  // 5 minutes instead of default
}
```

**Step 2: Use Faster Models**
```json
{
  "tool": "research",
  "question": "Your question",
  "models": ["llama3.2:1b", "llama3.2:3b"],  // Faster models
  "complexity": "simple"
}
```

**Step 3: Enable Sequential Processing**
```json
{
  "tool": "research",
  "question": "Your question",
  "parallel": false,  // Reduce resource usage
  "complexity": "medium"
}
```

**Step 4: Check System Resources**
```bash
# Check CPU usage
top

# Check memory usage
free -m

# Check GPU usage (if using GPU models)
nvidia-smi
```

#### Issue: Low Confidence Scores

**Symptoms:**
- Confidence scores consistently below 0.5
- Analysis shows "Very low confidence" warnings
- Poor quality responses

**Causes:**
- Ambiguous or poorly formatted questions
- Models not suitable for the topic
- High temperature settings causing inconsistent responses

**Solutions:**

**Step 1: Improve Question Quality**
```json
// Bad question
{
  "tool": "research",
  "question": "What's best?"
}

// Good question
{
  "tool": "research",
  "question": "What are the advantages and disadvantages of using Docker containers for web application deployment?",
  "complexity": "medium",
  "focus": "technical"
}
```

**Step 2: Adjust Temperature**
```json
{
  "tool": "research",
  "question": "Technical comparison question",
  "temperature": 0.3,  // Lower temperature for more focused responses
  "focus": "technical"
}
```

**Step 3: Use Appropriate Focus Area**
```json
{
  "tool": "research",
  "question": "Should we implement microservices architecture?",
  "focus": "business",  // Use business focus for strategic decisions
  "complexity": "complex"
}
```

#### Issue: Inconsistent Results

**Symptoms:**
- Same query returns different results each time
- Analysis quality varies significantly
- Convergent themes don't align

**Causes:**
- High temperature settings
- Different model selection between runs
- Non-deterministic model behavior

**Solutions:**

**Step 1: Use Consistent Temperature**
```json
{
  "tool": "research",
  "question": "Your question",
  "temperature": 0.2,  // Low temperature for consistent results
  "models": ["llama3.2:7b", "qwen2.5:7b", "mistral:7b"]  // Fixed models
}
```

**Step 2: Specify Exact Models**
Instead of relying on automatic selection, specify the exact models:
```json
{
  "tool": "research",
  "question": "Your question",
  "models": ["llama3.2:7b", "qwen2.5:7b", "mistral:7b"],
  "complexity": "medium"
}
```

### 2. MCP Server Issues

#### Issue: "Module not found" Errors

**Symptoms:**
```
Error: Cannot find module './research-tool.js'
ModuleNotFoundError: No module named 'research-types'
```

**Causes:**
- TypeScript not compiled to JavaScript
- Missing file extensions in imports
- Incorrect module resolution

**Solutions:**

**Step 1: Rebuild Project**
```bash
npm run clean
npm install
npm run build
```

**Step 2: Check Build Output**
```bash
ls -la build/
# Should see all .js files
```

**Step 3: Verify TypeScript Configuration**
```json
// tsconfig.json should have:
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "node16"
  }
}
```

#### Issue: Claude Desktop Integration Problems

**Symptoms:**
- Tools not appearing in Claude Desktop
- "Server failed to start" errors
- Connection timeout errors

**Causes:**
- Incorrect configuration path
- Missing environment variables
- Permission issues

**Solutions:**

**Step 1: Verify Configuration Path**
Check your Claude Desktop configuration file:
```json
// Windows: %APPDATA%\Claude\claude_desktop_config.json
// macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["C:/full/path/to/mcp-ollama/build/index.js"],  // Use full path
      "env": {
        "OLLAMA_HOST": "http://127.0.0.1:11434"
      }
    }
  }
}
```

**Step 2: Test Server Manually**
```bash
cd /path/to/mcp-ollama
node build/index.js
```

**Step 3: Check Permissions**
```bash
# On Unix-like systems
chmod +x build/index.js

# Check file permissions
ls -la build/index.js
```

**Step 4: Use MCP Inspector for Debugging**
```bash
npm run inspector
```

### 3. Ollama Integration Issues

#### Issue: Connection Refused Errors

**Symptoms:**
```
Failed to fetch available models: connect ECONNREFUSED 127.0.0.1:11434
Research execution failed: Request failed with status code 500
```

**Causes:**
- Ollama server not running
- Incorrect host configuration
- Firewall blocking connections

**Solutions:**

**Step 1: Start Ollama Server**
```bash
# Start Ollama (if not running)
ollama serve

# Or on Windows (if installed as service)
# The service should start automatically
```

**Step 2: Test Ollama Connection**
```bash
# Test basic connectivity
curl http://127.0.0.1:11434/api/tags

# Test with different host (if using Docker/WSL)
curl http://host.docker.internal:11434/api/tags
```

**Step 3: Configure Correct Host**
For WSL or Docker environments:
```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["path/to/build/index.js"],
      "env": {
        "OLLAMA_HOST": "http://host.docker.internal:11434"  // For Docker
        // OR
        // "OLLAMA_HOST": "http://172.x.x.x:11434"  // WSL host IP
      }
    }
  }
}
```

#### Issue: Model Loading Failures

**Symptoms:**
```
Model 'llama3.2:7b' not found. Available models: []
Error loading model: model not found
```

**Causes:**
- Model not downloaded
- Incorrect model name
- Ollama registry issues

**Solutions:**

**Step 1: Check Available Models**
```bash
ollama list
```

**Step 2: Pull Missing Models**
```bash
# Pull specific models
ollama pull llama3.2:7b
ollama pull qwen2.5-coder:7b-instruct
ollama pull mistral:7b

# Verify models are available
ollama list
```

**Step 3: Use Correct Model Names**
```json
// Correct model names (include tags)
{
  "tool": "research",
  "models": ["llama3.2:7b", "qwen2.5:7b", "mistral:7b"]
}

// Incorrect (missing tags)
{
  "tool": "research",
  "models": ["llama3.2", "qwen2.5", "mistral"]  // Will likely fail
}
```

### 4. Performance Issues

#### Issue: Slow Research Execution

**Symptoms:**
- Research takes longer than expected timeouts
- High CPU/memory usage
- System becomes unresponsive

**Causes:**
- Large models running on insufficient hardware
- Too many parallel queries
- Memory leaks or resource exhaustion

**Solutions:**

**Step 1: Use Appropriate Model Sizes**
```json
// For limited resources, use smaller models
{
  "tool": "research",
  "question": "Your question",
  "models": ["llama3.2:1b", "qwen2.5:3b"],  // Smaller, faster models
  "complexity": "simple"
}
```

**Step 2: Reduce Parallelism**
```json
{
  "tool": "research",
  "question": "Your question",
  "parallel": false,  // Sequential execution uses less resources
  "complexity": "medium"
}
```

**Step 3: Monitor Resource Usage**
```bash
# Check system resources
htop

# Monitor during research execution
watch -n 1 'free -m && ps aux | grep ollama'
```

**Step 4: Optimize Ollama Configuration**
```bash
# Set Ollama to use less CPU cores
export OLLAMA_NUM_PARALLEL=2

# Limit memory usage
export OLLAMA_MAX_VRAM=4096  # 4GB limit
```

#### Issue: Memory Leaks

**Symptoms:**
- Memory usage increases over time
- System becomes slow after multiple requests
- Out of memory errors

**Causes:**
- Accumulating model contexts
- Cached responses not being cleared
- Resource cleanup issues

**Solutions:**

**Step 1: Restart Services Regularly**
```bash
# Restart Ollama server
pkill ollama
ollama serve

# Restart MCP server (if running standalone)
```

**Step 2: Monitor Memory Usage**
```bash
# Monitor memory over time
while true; do
  echo "$(date): $(free -m | grep Mem)"
  sleep 60
done
```

**Step 3: Clear Model Context**
```bash
# Clear loaded models from memory
ollama ps  # See loaded models
# Restart ollama to clear all models from memory
```

## 🔍 Debugging Techniques

### 1. Enable Debug Logging

**Environment Variables:**
```bash
export DEBUG=mcp-ollama:*
export MCP_DEBUG=true
export OLLAMA_DEBUG=true
```

**Enhanced Logging:**
```typescript
// Add to your research request for detailed logging
{
  "tool": "research",
  "question": "Debug test question",
  "complexity": "simple",
  "include_metadata": true,  // Enable detailed response metadata
  "debug": true  // If implemented in your version
}
```

### 2. MCP Inspector Usage

**Start Inspector:**
```bash
npm run inspector
```

**Test Research Tool:**
1. Open browser to inspector URL
2. Connect to server
3. Test tool call:
```json
{
  "name": "research",
  "arguments": {
    "question": "Test question for debugging",
    "complexity": "simple",
    "include_metadata": true
  }
}
```

### 3. Manual Testing

**Direct API Testing:**
```bash
# Test Ollama API directly
curl -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:7b",
    "prompt": "What is TypeScript?",
    "stream": false
  }'
```

**Test Model Availability:**
```bash
# List models with details
curl http://127.0.0.1:11434/api/tags | jq '.'

# Show specific model info
curl http://127.0.0.1:11434/api/show \
  -H "Content-Type: application/json" \
  -d '{"name": "llama3.2:7b"}' | jq '.'
```

### 4. Log Analysis

**Common Log Patterns:**

**Successful Request:**
```
[DEBUG] Research Request: { question: "...", complexity: "medium", ... }
[DEBUG] Available models: [llama3.2:7b, mistral:7b, ...]
[DEBUG] Selected models: [llama3.2:7b, qwen2.5:7b, mistral:7b]
[DEBUG] Research Result: { modelsUsed: [...], totalTime: 12547, ... }
```

**Failed Request:**
```
[ERROR] Research execution failed: No suitable models available
[ERROR] Context: { complexity: "complex", availableModels: [] }
[DEBUG] Available models: []
```

**Performance Issues:**
```
[DEBUG] Model query timeout: llama3.2:70b after 60000ms
[WARN] High memory usage detected: 1024MB
[ERROR] Request failed: ECONNABORTED
```

## 🛠️ Recovery Procedures

### 1. Complete System Reset

If you're experiencing persistent issues:

```bash
# 1. Stop all services
pkill ollama
pkill node  # If MCP server is running

# 2. Clear Ollama models
ollama rm $(ollama list | tail -n +2 | awk '{print $1}')

# 3. Reinstall essential models
ollama pull llama3.2:1b
ollama pull llama3.2:7b
ollama pull mistral:7b

# 4. Rebuild MCP server
cd /path/to/mcp-ollama
npm run clean
npm install
npm run build

# 5. Test basic functionality
npm test

# 6. Restart services
ollama serve &
node build/index.js
```

### 2. Configuration Reset

Reset Claude Desktop configuration:

```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["path/to/mcp-ollama/build/index.js"],
      "env": {
        "OLLAMA_HOST": "http://127.0.0.1:11434"
      }
    }
  }
}
```

### 3. Model Cleanup

If models are corrupted or causing issues:

```bash
# Remove specific problematic model
ollama rm problematic-model:tag

# Re-download clean copy
ollama pull problematic-model:tag

# Verify model works
ollama run problematic-model:tag "Test message"
```

## 🆘 Getting Help

### 1. Gather Diagnostic Information

Before seeking help, collect this information:

```bash
# System info
uname -a
node --version
npm --version
ollama --version

# Service status
curl -s http://127.0.0.1:11434/api/tags | jq '.models | length'
ollama list

# Build status
cd /path/to/mcp-ollama
npm run build 2>&1 | tail -10

# Test run
node build/index.js --version
```

### 2. Create Minimal Reproduction

Create a minimal test case that reproduces the issue:

```json
{
  "tool": "research",
  "question": "Simple test question that fails",
  "complexity": "simple",
  "models": ["llama3.2:7b"],
  "include_metadata": true
}
```

### 3. Error Reporting Template

When reporting issues, include:

1. **Environment Details:**
   - Operating System
   - Node.js version
   - Ollama version
   - MCP server version

2. **Configuration:**
   - Claude Desktop configuration
   - Environment variables
   - Ollama host settings

3. **Error Details:**
   - Exact error messages
   - Request that caused the error
   - Debug logs (with DEBUG=mcp-ollama:*)

4. **Steps to Reproduce:**
   - Exact sequence that causes the issue
   - Expected vs actual behavior

5. **Attempted Solutions:**
   - What you've already tried
   - Results of troubleshooting steps

## 📊 Performance Monitoring

### 1. Continuous Monitoring Setup

```bash
# Create monitoring script
cat > monitor.sh << 'EOF'
#!/bin/bash
while true; do
  echo "=== $(date) ==="
  echo "Memory: $(free -m | grep Mem | awk '{print $3"MB/"$2"MB"}')"
  echo "Ollama processes: $(ps aux | grep ollama | wc -l)"
  echo "Available models: $(curl -s http://127.0.0.1:11434/api/tags | jq '.models | length')"
  echo "---"
  sleep 300  # 5 minutes
done
EOF

chmod +x monitor.sh
./monitor.sh > monitoring.log &
```

### 2. Performance Benchmarking

```bash
# Benchmark research performance
time curl -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:7b",
    "prompt": "What is machine learning?",
    "stream": false
  }'
```

This troubleshooting guide should help you resolve most common issues with the MCP Ollama Research Tool. Remember to always check the basics first (Ollama running, models available, correct configuration) before diving into complex debugging procedures.