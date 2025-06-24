# Query Blogger MCP Server

An MCP Server to **only query** (not modify), **your blog only** (and no other) hosted on [Blogger](https://www.blogger.com/) platform.

Why Query Blogger MCP Server to read a public blog posting on Blogger platform?
- Simple configuration and you are ready to go.
- This server is designed to be secure, efficient, and easy to use with LLMs.

---

## 1. How to use this library?

### 1.1. Obtain Blogger API Key

- Go to [Google Cloud Console](https://console.cloud.google.com/).
- Create a new project (or select an existing one).
- Navigate to `APIs & Services > Library`.
    - Search for "Blogger API" and enable it.
- Go to `APIs & Services > Credentials`.
    - Click "Create Credentials" and choose "API Key".
- Copy the generated API key.
- Crucially, **restrict your API key!** Edit the API key:
    - Under `API restrictions`, select `Restric key` and choose `Blogger API` from the dropdown. This ensures this key can only call Blogger API.
    - Under `Application restrictions`, you could optionally add `HTTP referrers` if your Core Agent will always call from a specific domain, or "IP addresses" if your MCP server will always run on a specific IP.
        - For most internal enterprise uses, API restrictions might be sufficient, but referrers or IP restrictions add another layer.


### 1.2. Setup `Query Blogger MCP Server` for your LLMs

1.2.1. **Clone the Repository:** git clone https://github.com/karthiks/query_blogger_mcp_server

1.2.2. **Set up Environment:**

> Prerequisites: pyenv is installed and is used to install python version 3.10.16.

```bash
cd query_blogger_mcp_server

python -m venv .venv
pyenv versions
pyenv local 3.10.16
pyenv version # python --version
python -m venv .venv
source .venv/bin/activate

pip install .
# pip install query_blogger_mcp_server
```
### 1.3. Configure this MCP Server

```bash
#Copy .env.example to .env:
cp .env.example .env

# Edit the .env file and fill in BLOGGER_API_KEY, ALLOWED_DOMAINS, and optionally adjust MCP_SERVER_NAME, MCP_SERVER_VERSION, UVICORN_HOST, UVICORN_PORT.

# On Windows (in cmd or PowerShell before starting server.py)
#$env:BLOGGER_API_KEY="YOUR_ACTUAL_BLOGGER_API_KEY"
# On Linux/macOS
#export BLOGGER_API_KEY="YOUR_ACTUAL_BLOGGER_API_KEY"
```

The end-user simply modifies the `.env` file (or sets environment variables directly in their deployment pipeline) to configure your MCP server, providing a much smoother and more secure experience.

### 1.4. Run this MCP Server

```bash
# run library module as a script
python -m query_blogger_mcp_server.server

# Or, the production-ready way if you have `query_blogger_mcp_server` installed:
# uvicorn query_blogger_mcp_server.server:mcp.app --host 0.0.0.0 --port 8000 --workers 1 # Add workers for production
```

This will start your MCP server, typically on http://0.0.0.0:8000.

### 1.5. Configure Your Core Agent (LLM System)

Your Core Agent (e.g., Ollama-deployed Qwen2.5 application) would then be configured to:

- Point to your MCP Server's URL (http://your-mcp-server-ip:8000).
- Be provided with the tool definitions that `FastMCP` automatically generates for `get_blog_info_by_url` and `get_latest_posts_by_blog_url`.

The LLM will then learn to call these tools when a user asks about blog content.

---

## 2. Testing with Your LLM:

When you send prompts to your LLM that's connected to this MCP server:

- **Allowed Domain:** "Can you tell me about the blog at `https://blog.codonomics.com`?"
    - **Expected:** LLM calls `get_blog_info_by_url` to your MCP server. MCP server calls Blogger API, returns info. LLM generates a summary.

- **Allowed Domain, Posts:** "What are the latest posts on `https://blog.codonomics.com`?"
    - **Expected:** LLM calls `get_latest_posts_by_blog_url` to your MCP server. MCP server calls Blogger API, returns posts. LLM summarizes.

- **Disallowed Domain:** "What's the news on `https://disallowed-website.com`?"
    - **Expected:** LLM might still call `get_blog_info_by_url` but your MCP server's `_is_allowed_domain` check will trigger. It will return an error message: `"Access denied: This tool can only query blogs from pre-approved domains"`. The LLM should then relay this message to the user.

- **Modification Attempt:** If you accidentally exposed a `create_post` tool, and the LLM tried to use it, the Blogger API itself would likely reject the API Key (as it's only for read-only access), and your MCP server would return an error. But by only defining read-only tools, you preempt this.

---
