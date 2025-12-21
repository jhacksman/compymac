# MCP Servers Reference

A comprehensive guide to Model Context Protocol (MCP) servers, including official reference implementations, company-maintained servers, and popular community options.

## Security Warning

MCP servers are executable programs that run with your user's permissions. They can read files, access tokens, make network requests, and execute arbitrary code. Before using any MCP server:

1. **Only use servers from trusted sources** - Official MCP org, verified companies, or code you've audited
2. **Pin versions** - Never use `latest` or `-y` with npx in production
3. **Review permissions** - Understand what each server can access
4. **Use sandboxing** - Consider containers or restricted users for sensitive environments
5. **Never let AI modify MCP config** - Treat configuration as trusted operator input only

## Discovery Resources

- **Official MCP Registry**: https://registry.modelcontextprotocol.io/
- **GitHub MCP Registry**: https://github.com/topics/mcp-server
- **Awesome MCP Servers**: https://github.com/wong2/awesome-mcp-servers
- **MCP Server Directory**: https://mcpserverdirectory.org/

## Official Reference Servers

These servers are maintained by the MCP team in the official repository: https://github.com/modelcontextprotocol/servers

| Server | Description | npm Package |
|--------|-------------|-------------|
| **Everything** | Reference/test server with prompts, resources, and tools | `@modelcontextprotocol/server-everything` |
| **Fetch** | Web content fetching and conversion for efficient LLM usage | `@modelcontextprotocol/server-fetch` |
| **Filesystem** | Secure file operations with configurable access controls | `@modelcontextprotocol/server-filesystem` |
| **Git** | Tools to read, search, and manipulate Git repositories | `@modelcontextprotocol/server-git` |
| **Memory** | Knowledge graph-based persistent memory system | `@modelcontextprotocol/server-memory` |
| **Sequential Thinking** | Dynamic and reflective problem-solving through thought sequences | `@modelcontextprotocol/server-sequentialthinking` |
| **Time** | Time and timezone conversion capabilities | `@modelcontextprotocol/server-time` |

### Archived Reference Servers

These were previously in the official repo but are now archived at https://github.com/modelcontextprotocol/servers-archived:

| Server | Description | Status |
|--------|-------------|--------|
| **Brave Search** | Web and local search | Replaced by official Brave server |
| **GitHub** | Repository management, file operations | Community maintained |
| **GitLab** | GitLab API, project management | Community maintained |
| **Google Drive** | File access and search | Community maintained |
| **Google Maps** | Location services, directions | Community maintained |
| **PostgreSQL** | Database read-only access | Community maintained |
| **Puppeteer** | Browser automation | Community maintained |
| **Slack** | Channel management, messaging | Community maintained |
| **Sentry** | Error tracking integration | Community maintained |
| **SQLite** | Local database operations | Community maintained |

## Company-Maintained Official Servers

These servers are maintained by the companies themselves for their platforms:

### Developer Tools & Version Control

| Server | Maintainer | Description |
|--------|------------|-------------|
| **[GitHub](https://github.com/github/github-mcp-server)** | GitHub | Official GitHub integration for repos, issues, PRs |
| **[GitLab](https://gitlab.com/gitlab-org/editor-extensions/gitlab-mcp-server)** | GitLab | Official GitLab integration |
| **[Bitbucket](https://bitbucket.org/atlassian/bitbucket-mcp-server)** | Atlassian | Bitbucket repository management |
| **[Linear](https://github.com/linear/linear-mcp-server)** | Linear | Issue tracking and project management |
| **[Jira](https://github.com/atlassian/jira-mcp-server)** | Atlassian | Jira issue management |

### Cloud Platforms

| Server | Maintainer | Description |
|--------|------------|-------------|
| **[AWS](https://github.com/aws/aws-mcp-servers)** | Amazon | AWS service integration |
| **[Cloudflare](https://github.com/cloudflare/mcp-server-cloudflare)** | Cloudflare | Workers, KV, R2, D1 management |
| **[Vercel](https://github.com/vercel/mcp-server-vercel)** | Vercel | Deployment and project management |
| **[Supabase](https://github.com/supabase/supabase-mcp)** | Supabase | Database, auth, storage |
| **[Neon](https://github.com/neondatabase/mcp-server-neon)** | Neon | Serverless Postgres management |

### Databases

| Server | Maintainer | Description |
|--------|------------|-------------|
| **[PostgreSQL](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres)** | MCP (archived) | Read-only PostgreSQL access |
| **[MongoDB](https://github.com/mongodb/mongodb-mcp-server)** | MongoDB | MongoDB database operations |
| **[Redis](https://github.com/redis/redis-mcp-server)** | Redis | Redis data store operations |
| **[Pinecone](https://github.com/pinecone-io/pinecone-mcp-server)** | Pinecone | Vector database operations |
| **[Qdrant](https://github.com/qdrant/mcp-server-qdrant)** | Qdrant | Vector search engine |

### Search & Data

| Server | Maintainer | Description |
|--------|------------|-------------|
| **[Brave Search](https://github.com/brave/brave-search-mcp-server)** | Brave | Web and local search |
| **[Exa](https://github.com/exa-labs/exa-mcp-server)** | Exa | Neural search API |
| **[Tavily](https://github.com/tavily-ai/tavily-mcp-server)** | Tavily | AI-optimized search |
| **[Perplexity](https://github.com/perplexity-ai/perplexity-mcp-server)** | Perplexity | AI search integration |

### Communication & Productivity

| Server | Maintainer | Description |
|--------|------------|-------------|
| **[Slack](https://github.com/slackapi/slack-mcp-server)** | Slack | Channel management, messaging |
| **[Discord](https://github.com/discord/discord-mcp-server)** | Discord | Server and channel management |
| **[Notion](https://github.com/makenotion/notion-mcp-server)** | Notion | Page and database operations |
| **[Obsidian](https://github.com/obsidianmd/obsidian-mcp-server)** | Obsidian | Note management |
| **[Todoist](https://github.com/doist/todoist-mcp-server)** | Doist | Task management |

### Browser Automation

| Server | Maintainer | Description |
|--------|------------|-------------|
| **[Puppeteer](https://github.com/anthropics/mcp-server-puppeteer)** | Anthropic | Browser automation with Puppeteer |
| **[Playwright](https://github.com/anthropics/mcp-server-playwright)** | Anthropic | Browser automation with Playwright |
| **[Browserbase](https://github.com/browserbase/mcp-server-browserbase)** | Browserbase | Cloud browser automation |

### AI & ML

| Server | Maintainer | Description |
|--------|------------|-------------|
| **[OpenAI](https://github.com/openai/openai-mcp-server)** | OpenAI | GPT and DALL-E integration |
| **[Anthropic](https://github.com/anthropics/anthropic-mcp-server)** | Anthropic | Claude API integration |
| **[Hugging Face](https://github.com/huggingface/huggingface-mcp-server)** | Hugging Face | Model hub integration |
| **[Replicate](https://github.com/replicate/replicate-mcp-server)** | Replicate | ML model deployment |

## Popular Community Servers

These are well-maintained community servers with significant usage:

### File & System

| Server | Stars | Description |
|--------|-------|-------------|
| **[mcp-server-filesystem](https://github.com/anthropics/mcp-server-filesystem)** | 60k+ | Local filesystem access |
| **[mcp-server-docker](https://github.com/ckreiling/mcp-server-docker)** | 1k+ | Docker container management |
| **[mcp-server-kubernetes](https://github.com/strowk/mcp-k8s-go)** | 500+ | Kubernetes cluster management |

### Development

| Server | Stars | Description |
|--------|-------|-------------|
| **[mcp-server-sqlite](https://github.com/anthropics/mcp-server-sqlite)** | 5k+ | SQLite database operations |
| **[mcp-server-postgres](https://github.com/anthropics/mcp-server-postgres)** | 5k+ | PostgreSQL operations |
| **[mcp-server-shell](https://github.com/anthropics/mcp-server-shell)** | 3k+ | Shell command execution |

### Web & APIs

| Server | Stars | Description |
|--------|-------|-------------|
| **[mcp-server-fetch](https://github.com/anthropics/mcp-server-fetch)** | 5k+ | HTTP requests and web fetching |
| **[mcp-server-youtube](https://github.com/anthropics/mcp-server-youtube)** | 2k+ | YouTube video/transcript access |
| **[mcp-server-twitter](https://github.com/anthropics/mcp-server-twitter)** | 1k+ | Twitter/X API integration |

## Example Configurations

### Minimal Safe Configuration

```json
{
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem@0.6.2", "/allowed/path/only"],
      "env": {}
    }
  }
}
```

### Development Configuration

```json
{
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem@0.6.2", "/home/user/projects"],
      "env": {}
    },
    "git": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-git@0.6.2"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["@github/github-mcp-server@latest"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."
      }
    }
  }
}
```

### Full Productivity Configuration

```json
{
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem@0.6.2", "/home/user"],
      "env": {}
    },
    "git": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-git@0.6.2"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["@github/github-mcp-server@latest"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."
      }
    },
    "slack": {
      "command": "npx",
      "args": ["@slackapi/slack-mcp-server@latest"],
      "env": {
        "SLACK_BOT_TOKEN": "xoxb-..."
      }
    },
    "brave-search": {
      "command": "npx",
      "args": ["@anthropic/mcp-server-brave-search@latest"],
      "env": {
        "BRAVE_API_KEY": "..."
      }
    }
  }
}
```

## Best Practices

### Version Pinning

Always pin versions in production:

```json
// Good - pinned version
"args": ["@modelcontextprotocol/server-filesystem@0.6.2", "/path"]

// Bad - floating version
"args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
```

### Least Privilege

Only grant access to what's needed:

```json
// Good - specific directory
"args": ["@modelcontextprotocol/server-filesystem@0.6.2", "/home/user/projects/myapp"]

// Bad - entire home directory
"args": ["@modelcontextprotocol/server-filesystem@0.6.2", "/home/user"]
```

### Environment Isolation

For sensitive environments, run servers in containers:

```bash
docker run --rm -i \
  -v /allowed/path:/data:ro \
  mcp/filesystem /data
```

### Audit Before Use

Before adding any MCP server:

1. Check the source repository
2. Review recent commits and maintainers
3. Look for security advisories
4. Verify the npm package matches the repo
5. Consider running in a sandbox first

## CompyMac Integration

To use MCP servers with CompyMac, set one of these environment variables:

```bash
# Option 1: Path to config file
export MCP_CONFIG_PATH=/path/to/mcp-config.json

# Option 2: Inline JSON
export MCP_SERVERS='{"servers": {"filesystem": {"command": "npx", "args": ["@modelcontextprotocol/server-filesystem@0.6.2", "/path"]}}}'
```

Then use the `mcp_tool` in your agent:

```python
# List configured servers
result = harness._mcp_tool("list_servers")

# List tools on a server
result = harness._mcp_tool("list_tools", server="filesystem")

# Call a tool
result = harness._mcp_tool("call_tool", server="filesystem", tool_name="read_file", tool_args='{"path": "/path/to/file"}')

# Read a resource
result = harness._mcp_tool("read_resource", server="filesystem", resource_uri="file:///path/to/file")
```

## References

- MCP Specification: https://modelcontextprotocol.io/
- Official Servers Repo: https://github.com/modelcontextprotocol/servers
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk
