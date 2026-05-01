# Tool System Diagram

Human-readable Mermaid reconstruction of the ToolManager architecture.

Source capture:

- `deepwiki-vibe-capture/out/7.5-tool-manager-architecture/context.txt`
- `deepwiki-vibe-capture/out/3.4-tool-system/context.txt`

## Tool Discovery And Execution

```mermaid
flowchart TB
  TM["ToolManager"]

  subgraph Discovery["Tool Discovery System"]
    SearchPaths["_compute_search_paths()\nOrder: builtins first, then custom paths"]
    DefaultDir["1. DEFAULT_TOOL_DIR\nvibe/core/tools/builtins/"]
    ConfigPaths["2. config.tool_paths\n(custom — overrides builtins on name collision)"]
    ProjectTools["3. project tool dirs\n(overrides builtins on name collision)"]
    UserTools["4. user tool dirs\n(overrides builtins on name collision)"]
    Iter["_iter_tool_classes()"]
    Load["_load_tools_from_file()"]
    Inspect["inspect.isclass + issubclass(BaseTool)"]
    Available["_available: dict[str, type[BaseTool]]\n(later paths win on name collision)"]
  end

  subgraph Config["Configuration System"]
    ConfigGetter["_config_getter()"]
    ToolConfigClass["_get_tool_config_class()"]
    ConfigTools["config.tools"]
    GetToolConfig["get_tool_config()"]
  end

  subgraph MCP["MCP Integration System"]
    MCPRegistry["MCPRegistry.get_tools()"]
    MCPServers["config.mcp_servers"]
    Proxy["HTTP/stdio proxy tool class generation"]
  end

  subgraph Instances["Instance Management"]
    FromConfig["BaseTool.from_config()"]
    InstancesDict["_instances: dict[str, BaseTool]"]
    AvailableTools["available_tools property"]
  end

  TM --> SearchPaths
  SearchPaths --> DefaultDir
  SearchPaths --> ConfigPaths
  SearchPaths --> ProjectTools
  SearchPaths --> UserTools
  SearchPaths --> Iter
  Iter --> Load
  Load --> Inspect
  Inspect --> Available

  TM --> MCPRegistry
  MCPServers --> MCPRegistry
  MCPRegistry --> Proxy
  Proxy --> Available

  TM --> ConfigGetter
  ConfigGetter --> ToolConfigClass
  ConfigTools --> GetToolConfig
  ToolConfigClass --> GetToolConfig
  GetToolConfig --> FromConfig
  Available --> FromConfig
  FromConfig --> InstancesDict
  InstancesDict --> AvailableTools
```

## Design Use

Use Tier B when the workflow needs a new executable action but does not need to change AgentLoop, middleware timing, events, or session semantics.
