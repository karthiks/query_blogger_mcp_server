# README For Developer Onboarding

## How this project was setup?

```bash
mkdir query_blogger_mcp_server
cd query_blogger_mcp_server
pyenv versions
pyenv local 3.10.16
pyenv version # python --version
python -m venv .venv
source .venv/bin/activate

pip list
pip install --upgrade pip
pip install "mcp[cli]" fastapi uvicorn httpx
pip list

git init
```

## Project Directory Structure

```
query_blogger_mcp_server/
├── .gitignore
├── .env.example    # Sample env file
├── pyproject.toml  # The central project config file that defines project metadata, dependencies etc.
├── README.md       # For clients/consumers' reference
├── README-DEV.md   # For developers' reference
├── src/
│   └── query_blogger_mcp_server/   # This is the Python package that gets installed when someone installs this project.
│       ├── __init__.py     # Marks this directory as Python package
│       ├── blogger_api_client.py   # Contains the Blogger API wrapper
│       └── server.py   # Contains FastMCP server logic and tool definitions
│       └── config.py   # For config settings (allowed domains, API keys, etc)
├── tests/
│   ├── __init__.py
│   ├── test_blogger_api_client.py  # Unit tests for BloggerAPIClient
│   ├── test_mcp_tools.py           # Unit/integration tests for your MCP tools
│   └── conftest.py                 # pytest fixtures
├── .env.example                    # Example of environment variables file (DON'T commit .env)
```

## Developer Workflow

> Prerequisites: pyenv is installed and is used to install python version 3.10.16.

- Import this project from git
    ```bash
    git clone <>
    ```

- Install this project locally
    ```bash
    cd query_blogger_mcp_server

    pyenv versions
    pyenv local 3.10.16
    pyenv version # python --version
    python -m venv .venv
    source .venv/bin/activate

    pip install -e '.[dev]' # Install in editable mode
    pip list
    ```

## References

- [Python Development Tools You Must Leverage For Productivity](https://blog.codonomics.com/2025/01/python-development-tools-you-must-leverage.html.html)

- [Blogger API: Using the API](https://developers.google.com/blogger/docs/3.0/using#APIKey)
    - Every request your application sends to the Blogger APIs needs to identify your application to Google. There are two ways to identify your application:
        - If the request requires authorization (such as a request for an individual's private data), then the application must provide an [OAuth 2.0 token](https://developers.google.com/blogger/docs/3.0/using#AboutAuthorization) with the request.
        - If the request doesn't require authorization (such as a request for public data), then the application must provide either the [API key](https://developers.google.com/blogger/docs/3.0/using#APIKey) or an OAuth 2.0 token, or both—whatever option is most convenient for you. Providing API Key is easier for read-only access to public data.

- [Docs: Pydantic > Settings Management > Disabling JSON Parsing](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#disabling-json-parsing)
    - `pydantic-settings` by default parses complex types from environment variables as JSON strings.