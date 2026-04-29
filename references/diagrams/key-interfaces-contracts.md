# Key Interfaces & Contracts Diagram

Maps the contracts that implementation plans must obey.

Source reference: `references/feasibility/key-interfaces-contracts.md`

```mermaid
flowchart TB
  subgraph Tool["BaseTool Contract"]
    BaseTool["BaseTool"]
    ToolArgs["ToolArgs\nPydantic input"]
    ToolResult["ToolResult\nPydantic output"]
    ToolConfig["BaseToolConfig\npermission, allowlist,\ndenylist, sensitive_patterns"]
    InvokeContext["InvokeContext\ntool_call_id, session_dir,\nagent_manager, skill_manager,\napproval_callback, user_input_callback,\nswitch_agent_callback"]
    BaseTool --> ToolArgs
    BaseTool --> ToolResult
    BaseTool --> ToolConfig
    BaseTool --> InvokeContext
  end

  subgraph Middleware["ConversationMiddleware Protocol"]
    MiddlewareBase["Middleware.before_turn(messages)"]
    MiddlewareAction["MiddlewareAction\nCONTINUE, STOP,\nINJECT_MESSAGE, COMPACT"]
    MessageList["MessageList"]
    MiddlewareBase --> MessageList
    MiddlewareBase --> MiddlewareAction
  end

  subgraph Context["ConversationContext Fields"]
    LLMMessage["LLMMessage\nrole, content, reasoning_content,\ntool_calls, tool_call_id, message_id"]
    BaseEvent["BaseEvent"]
    AgentStats["AgentStats\ntokens, cost, tool metrics,\nsteps, duration"]
    BaseEvent --> AssistantEvent["AssistantEvent"]
    BaseEvent --> ToolCallEvent["ToolCallEvent"]
    BaseEvent --> ToolResultEvent["ToolResultEvent"]
  end
```

## Planning Rule

Any plan touching tools, middleware, events, or session state must name the exact contract it obeys.
