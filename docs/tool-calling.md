# Voice Tool Calling Architecture

## Overview

The voice tool calling framework allows the LLM to autonomously decide when real-time internet data or external database operations are required.

## Tools & Execution

- `web_search`: Live real-time internet search via DuckDuckGo / SearXNG fallback.
- `web_fetch`: Page content reader for deep context.
- `ToolExecutor`: Manages strict timeouts, prompt injection security wrappers, and barge-in cancellation handles.

## Barge-in Interruption Handling

If the user interrupts while a tool call is running, `ToolExecutor.cancel_tool_call(tool_call_id)` cancels the running task, flushes stale audio frames, and immediately starts processing the new turn.
