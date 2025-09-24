#!/bin/bash
# Enable debug logging for hook troubleshooting

echo "Enabling hook debug mode..."
export HOOK_DEBUG=true
echo "HOOK_DEBUG is now set to: $HOOK_DEBUG"
echo ""
echo "Debug mode enabled. When 'Tool used: unknown' appears, check stderr for debug output."
echo "To disable, run: unset HOOK_DEBUG"
echo ""
echo "You can also check the logs at:"
echo "  ~/.claude/logs/sessions/<session-id>/post_tool_use.json"