# Architecture Overview Diagram

Human-readable Mermaid reconstruction of the DeepWiki architecture overview.

Source capture:

- `deepwiki-vibe-capture/out/7-architecture/context.txt`
- `deepwiki-vibe-capture/out/7-architecture/diagram-00.png`

## Component Map

```mermaid
flowchart TB
  subgraph Entry["Entry Points"]
    CLI["vibe.cli.entrypoint:main\nCLI Entry"]
    ACP["vibe.acp.entrypoint:main\nACP Entry"]
  end

  subgraph Core["Core Agent System"]
    AgentLoop["vibe.core.agent_loop:AgentLoop\nConversation orchestration"]
    ToolManager["vibe.core.tools.manager:ToolManager\nTool discovery and execution"]
    SessionLogger["vibe.core.session.session_logger:SessionLogger\nPersistence"]
  end

  subgraph Types["Type System"]
    CoreTypes["vibe.core.types\nLLMMessage, LLMChunk, Events, AgentStats"]
  end

  subgraph LLM["LLM Integration Layer"]
    MistralBackend["vibe.core.llm.backend.mistral:MistralBackend\nMistral API client"]
    GenericBackend["vibe.core.llm.backend.generic:GenericBackend\nOpenAI-compatible API"]
    MistralMapper["vibe.core.llm.backend.mistral:MistralMapper\nType conversion"]
    OpenAIAdapter["vibe.core.llm.backend.generic:OpenAIAdapter\nType conversion"]
  end

  subgraph Config["Configuration"]
    VibeConfig["vibe.core.config:VibeConfig\nRuntime configuration"]
  end

  CLI --> AgentLoop
  ACP --> AgentLoop
  AgentLoop --> ToolManager
  AgentLoop --> SessionLogger
  AgentLoop --> CoreTypes
  AgentLoop --> MistralBackend
  AgentLoop --> GenericBackend
  MistralBackend --> MistralMapper
  GenericBackend --> OpenAIAdapter
  MistralMapper --> CoreTypes
  OpenAIAdapter --> CoreTypes
  VibeConfig --> AgentLoop
  VibeConfig --> ToolManager
  VibeConfig --> MistralBackend
  VibeConfig --> GenericBackend
```

## Design Use

Use this diagram during `design` to decide which runtime surface a requested workflow touches:

- command/config only: likely Tier A
- tool behavior: likely Tier B
- turn-level control: likely Tier C
- AgentLoop/type/event/session internals: likely Tier D
