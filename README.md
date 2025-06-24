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


### 1.2. Setup `Query Blogger MCP Server`

#### 1.2.1 Clone the Repository
    ```bash
    git clone https://github.com/karthiks/query_blogger_mcp_server
    ```

#### 1.2.2 **Container-less Approach:** In host machine having Python installed

- **Set up Environment:**

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

- **Configure this MCP Server**

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

- **Run this MCP Server**

    ```bash
    # run library module as a script
    python -m query_blogger_mcp_server.server

    # Or, the production-ready way if you have `query_blogger_mcp_server` installed:
    # uvicorn query_blogger_mcp_server.server:mcp.app --host 0.0.0.0 --port 8000 --workers 1 # Add workers for production
    ```

    This will start your MCP server, typically on http://0.0.0.0:8000.

#### 1.2.2 **Container-ized Approach:** In host machine having Docker installed

- **Set up Environment:**

    ```bash
    cd query_blogger_mcp_server

    # Build Docker Image: This command reads your Dockerfile and creates a Docker image for your application. Wait for the build process to complete. You should see output indicating each step of the Dockerfile being executed.
    docker build -t query-blogger-mcp-server .

    ```

- **Run the Docker Container to fire-up MCP Server**
    ```bash
    docker run -d \
    --name blogger_mcp_instance \
    -p 8000:8000 \
    -e BLOGGER_API_KEY="your_actual_google_blogger_api_key_here" \
    -e ALLOWED_DOMAINS="kartzontech.blogspot.com,blog.codonomics.com" \
    query-blogger-mcp-server
    ```
    - `docker run`: The command to create and run a container.
    - `-d`: Runs the container in "detached" mode (in the background), so your terminal remains free.
    - `--name blogger_mcp_instance`: Assigns a unique name `blogger_mcp_instance` to your running container. This makes it easier to refer to later (e.g., for stopping or viewing logs).
    - `-p 8000:8000`: This is the port mapping. It maps port 8000 on your host machine (your computer) to port 8000 inside the Docker container.
    - `-e BLOGGER_API_KEY="..."`: This sets an environment variable named BLOGGER_API_KEY inside the container.
    - `query-blogger-mcp-server`: This is the name of the Docker image you built in the previous step.
    > Your MCP server should now be running inside a Docker container, accessible via http://localhost:8000 from your host machine!

- **Verify if Docker Container is up and running**
    ```bash
    docker ps
    # You should see a list of running containers, and blogger_mcp_instance should be among them, with 0.0.0.0:8000->8000/tcp in the PORTS column.
    ```

- **View Container Logs (For debugging/monitoring)**
    ```bash
    docker logs blogger_mcp_instance
    ```

- **Stop and Remove the Container (When finished)**
    ```bash
    docker stop blogger_mcp_instance
    docker rm blogger_mcp_instance
    ```
    > When you're done, it's good practice to stop and remove the container to free up resources.

### 1.3. Configure Your Core Agent (LLM System)

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

## ToDos

    [X] MVP: Allow Single Domain
    [X] Allow Multiple Domains
    [X] User Oboarding with README.md
    [X] Dev Onboarding with README-DEV.md
    [X] Externalize configurations
    [X] Containerize with Docker
    [ ] Security Fix: Upgrade to Vulnerable free Docker Image version (3.10 images have 2 critical vulnerabilityes) - Python-v3.14??
    [ ] Unit Test Cases
    [ ] Features
        - [X] Get Blog Information by URL (get_blog_info_by_url)
        - [X] Get Latest Posts by Blog URL (get_latest_posts_by_blog_url)
        - [] Get Comments for a Specific Blog Post (get_post_comments)
            - Prompt: Are there any comments on the post, "The Truth About AI Coding Agents"?
            - Prompts: What are the comments on the blog post titled "The Truth About AI Coding Agents"?
            - Prompt: Summarize the feedback from the comments section of the article "The Truth About AI Coding Agents"




