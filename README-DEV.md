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

query_blogger_mcp_server/
├── .gitignore
├── pyproject.toml              # The central project config file that defines project metadata, dependencies etc.
├── README.md                   # A Readme file for all clients/consumers of this project
├── README-DEV.md               # A Readme file for all developers of this project
├── src/
│   └── query_blogger_mcp_server/   # This is the Python package that gets installed when someone installs this project.
│       ├── __init__.py             # Marks query_blogger_mcp_server as a Python package
│       ├── blogger_api_client.py   # Contains the Blogger API wrapper
│       └── server.py               # Contains your FastMCP server logic and tool definitions
│       └── config.py               # For configuration settings (e.g., allowed domains, API keys)
├── tests/
│   ├── __init__.py
│   ├── test_blogger_api_client.py  # Unit tests for BloggerAPIClient
│   ├── test_mcp_tools.py           # Unit/integration tests for your MCP tools
│   └── conftest.py                 # pytest fixtures
├── .env.example                    # Example of environment variables file (DON'T commit .env)

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

    pip install -e .
    pip list
    ```

