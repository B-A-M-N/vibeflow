# Configuration System Diagram

Human-readable Mermaid reconstruction of configuration discovery and resolution.

Source capture:

- `deepwiki-vibe-capture/out/2.2-configuration/context.txt`

## File Layout

```mermaid
flowchart TB
  subgraph Global["Global Configuration [VIBE_HOME]"]
    GlobalDir["~/.config/vibe/"]
    GlobalConfig["config.toml"]
    GlobalEnv[".env"]
    UpdateCache["update_cache.json"]
  end

  subgraph Project["Project Configuration [trusted folder]"]
    ProjectDir[".vibe/"]
    ProjectConfig["config.toml"]
    ProjectEnv[".env"]
  end

  subgraph Sessions["Session Storage [SESSION_LOG_DIR]"]
    SessionRoot["~/.config/vibe/sessions/"]
    SessionDir["session_YYYYMMDD_HHMMSS_ID/"]
    Messages["messages.jsonl"]
    Meta["meta.json"]
  end

  ProjectConfig -->|overrides| GlobalConfig
  ProjectEnv -->|overrides| GlobalEnv
  SessionRoot --> SessionDir
  SessionDir --> Messages
  SessionDir --> Meta
```

## Resolution Priority

```mermaid
flowchart TB
  Env["OS environment variables\nhighest priority"]
  Dotenv[".env files\nload_dotenv_values"]
  ProjectToml[".vibe/config.toml\nif trusted"]
  GlobalToml["~/.config/vibe/config.toml"]
  Defaults["Pydantic field defaults\nlowest priority"]
  Config["VibeConfig instance"]

  Env --> Config
  Dotenv --> Config
  ProjectToml --> Config
  GlobalToml --> Config
  Defaults --> Config
```

## VibeConfig Class Shape

```mermaid
classDiagram
  class VibeConfig {
    active_model: str
    models: list[ModelConfig]
    providers: list[ProviderConfig]
    session_logging: SessionLoggingConfig
    project_context: ProjectContextConfig
    mcp_servers: list[MCPServer]
  }

  class ModelConfig {
    name: str
    provider: str
    auto_compact_threshold: int
  }

  class ProviderConfig {
    name: str
    api_base: str
    backend: Backend
    reasoning_field_name: str
  }

  class SessionLoggingConfig {
    enabled: bool
    save_dir: str
    session_prefix: str
  }

  class MCPServer {
    name: str
    transport: str
    sampling_enabled: bool
  }

  VibeConfig --> ModelConfig
  VibeConfig --> ProviderConfig
  VibeConfig --> SessionLoggingConfig
  VibeConfig --> MCPServer
```

## Design Use

Prefer configuration when the workflow only needs to expose or tune existing behavior. Do not claim config can change AgentLoop semantics, middleware timing, or event consumers.
