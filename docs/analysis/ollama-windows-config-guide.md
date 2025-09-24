# Ollama Windows-to-WSL Configuration Guide

## Issue Identified
- **WSL Connection**: Can ping Windows host (10.0.0.225) but Ollama port 11434 is not accessible
- **Root Cause**: Ollama on Windows likely only listening on localhost (127.0.0.1:11434)

## Windows Configuration Steps

### Step 1: Configure Ollama for External Connections
On your Windows machine, you need to configure Ollama to accept connections from WSL:

```powershell
# Option 1: Set environment variable permanently
setx OLLAMA_HOST "0.0.0.0:11434"

# Option 2: Or start Ollama with external binding
ollama serve --host 0.0.0.0:11434
```

### Step 2: Windows Firewall Configuration
```powershell
# Allow Ollama through Windows Firewall (run as Administrator)
netsh advfirewall firewall add rule name="Ollama API" dir=in action=allow protocol=TCP localport=11434
```

### Step 3: Verify Configuration
```powershell
# Check if Ollama is listening on all interfaces
netstat -an | findstr 11434

# Should show: 0.0.0.0:11434 instead of 127.0.0.1:11434
```

### Step 4: Test from Windows
```powershell
# Test locally first
curl http://localhost:11434/api/version

# Test external interface
curl http://0.0.0.0:11434/api/version
```

## WSL Testing Commands
After Windows configuration, test from WSL:

```bash
# Test connection
curl http://10.0.0.225:11434/api/version

# List your models
curl http://10.0.0.225:11434/api/tags

# Test a simple generation
curl http://10.0.0.225:11434/api/generate -d '{
  "model": "your-model-name",
  "prompt": "Hello world",
  "stream": false
}'
```

## MCP Configuration Update
Once Windows is configured, we'll update the MCP server environment:

```bash
export OLLAMA_HOST="http://10.0.0.225:11434"
# or
export OLLAMA_HOST="http://host.docker.internal:11434"
```

## Next Steps
1. Apply Windows configuration above
2. Test connectivity from WSL
3. Update MCP server configuration
4. Test all Ollama MCP tools
5. Create integration workflows with Manus MCP