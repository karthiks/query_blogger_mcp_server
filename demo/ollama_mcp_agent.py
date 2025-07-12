import sys
import asyncio
import logging
from typing import Dict, Any, List, Optional
import ollama

from query_blogger_mcp_client import QueryBloggerMCPClient

# --- LLM API Configuration ---
OLLAMA_HOST = "http://codonomics.local:11434"
MODEL_NAME = "qwen2.5:0.5b" # Choose a lightweight model suitable for your laptop

# --- MCP Server Configuration (Assumed to be running) ---
MCP_SERVER_BASE_URL = "http://172.18.228.135:8000" # Know your WSL IP or use localhost if running on the same machine

# --- Configure basic logging for the agent client ---
logging.basicConfig(level= logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LLMAgent:
    """
    Orchestrates user queries by deciding between MCP tool calls and direct LLM calls.
    """
    def __init__(self):
        self.mcp_tools = QueryBloggerMCPClient(MCP_SERVER_BASE_URL)
        self.known_blogs = {
            "our company blog": "https://blog.codonomics.com",
            "our blog": "https://blog.codonomics.com",
            "https://kartzontech.blogspot.com" : "https://blog.codonomics.com",
        }
        self.ollama_client = ollama.AsyncClient(host=OLLAMA_HOST, timeout=10)
        logger.info("LLM Agent with MCP initialized.")

    async def call_ollama(self, user_input: str, context: Optional[str] = None) -> str:
        """Call the local Ollama API for chat completion with optional context."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Provide concise answers."},
        ]
        if context:
            messages.append({"role": "user", "content": f"Based on the following context, answer the question: {context}\n\nQuestion: {user_input}"})
        else:
            messages.append({"role": "user", "content": user_input})

        try:
            response = await self.ollama_client.chat(
                model=MODEL_NAME,
                messages=messages,
                options={"num_ctx": 4096},  # Adjust context window if needed
                stream=False,  # Non-streaming for simplicity
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error(f"Error calling Ollama: {str(e)}")
            return f"Error calling Ollama: {str(e)}"

    async def list_available_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the MCP server."""
        tools = await self.mcp_tools.get_tools()
        logger.info(f"Discovered {len(tools)} tools")
        return [tool.to_dict() for tool in tools]

    def _get_blog_url_from_query(self, query: str) -> Optional[str]:
        """Helper to extract blog URL based on keywords."""
        for key, url in self.known_blogs.items():
            if key in query.lower():
                logger.info(f"Returning known blog URL for '{key}': {url}")
                return url
        return None

    async def process_user_query(self, user_query: str) -> str:
        """
        Processes a user query by attempting to use MCP tools first,
        then falling back to the LLM if no tool is applicable or
        to synthesize a response from tool output.
        """
        user_query = user_query.lower().replace("recent", "latest").replace("blogs","posts")  # Normalize query for easier matching
        blog_url = self._get_blog_url_from_query(user_query)

        # --- Tool 1: Get latest posts ---
        if ("latest posts from" in user_query) and blog_url:
            num_posts_str = ''.join(filter(str.isdigit, user_query.split("latest posts from")[0]))
            num_posts = int(num_posts_str) if num_posts_str.isdigit() else 3

            include_content = "with content" in user_query or "for answering questions" in user_query

            tool_output = await self.mcp_tools.call_mcp_tool(
                "get_recent_posts",
                {"blog_url": blog_url, "num_posts": num_posts, "include_content": include_content}
            )

            if "error" not in tool_output and tool_output.get("recent_posts"):
                posts_summary = "\n".join([
                    f"- {p['title']} ({p['url']}) published {p['published']}" + (f"\n  Content Preview: {p['content_preview']}" if p.get('content_preview') else "")
                    for p in tool_output['recent_posts']
                ])
                context = (
                    f"Here are the latest posts from {tool_output.get('blog_title', 'N/A')}:\n"
                    f"{posts_summary}\n\n"
                    f"Please summarize this information for the user's request: '{user_query}'"
                )
                return await self.call_ollama(user_query, context=context) # Synthesize with Ollama
            else:
                return f"Failed to get latest posts: {tool_output.get('error', 'No posts found.')}"

        # --- Tool 2: Get blog info ---
        elif ("about our blog" in user_query) or (f"about {blog_url}" in user_query and blog_url):
            if(not blog_url):
                blog_url = self.known_blogs.get("our company blog", None)
            tool_output = await self.mcp_tools.call_mcp_tool(
                "get_blog_info_by_url",
                {"blog_url": blog_url}
            )
            if "error" not in tool_output:
                context = (
                    f"Blog Info: Title: {tool_output.get('blog_title', 'N/A')}, "
                    f"URL: {tool_output.get('blog_url', 'N/A')}, "
                    f"Published: {tool_output.get('published_date', 'N/A')}, "
                    f"Description: {tool_output.get('description', 'No description available.')}\n\n"
                    f"Please summarize this blog information for the user's request: '{user_query}'"
                )
                return await self.call_ollama(user_query, context=context) # Synthesize with Ollama
            else:
                return f"Failed to get blog info: {tool_output['error']}"

    async def close(self):
        """Close the httpx client sessions."""
        await self.mcp_tools.close()

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager and close resources."""
        await self.close()

async def ollama_status_check(agent: LLMAgent):
    """ Check if Ollama is running and Model is loaded """
    try:
        processes = await agent.ollama_client.ps()
        running_models = [p["model"] for p in processes.get("models", [])]
        if MODEL_NAME not in running_models:
            print(f"Error: Model {MODEL_NAME} is not running. Available running models: {running_models}")
            print(f"Please run `ollama run {MODEL_NAME}` or pull the model with `ollama pull {MODEL_NAME}`.")
            sys.exit(1)
        print(f"Ollama is running with model {MODEL_NAME}.")
    except Exception as e:
        print(f"Error connecting to Ollama at {OLLAMA_HOST}: {e}")
        print("Please ensure Ollama is running and accessible.")
        sys.exit(1)

def show_console_intro_prompt():
    print(f"Using local LLM model: {MODEL_NAME}")
    print(f"Connecting to MCP Server at: {MCP_SERVER_BASE_URL}")

    print("\nHow can I help you with your Blogger content? (Type 'exit' to quit)")
    print("Try questions like:")
    print("  - 'Tell me about our company blog.'")
    print("  - 'Get latest posts from our blog.'")
    print("  - 'Get latest posts from our blog with content.'")
    print("  - 'Answer question about our blog: What is X?' (requires content loaded first)")
    print("  - 'List static pages on our company blog.'")
    print("  - 'Search for 'Python' posts on the dev blog.'")

async def show_available_tools(agent):
    print("Loading available MCP tools...")
    tools = await agent.list_available_tools()
    tool_names = [tool['name'] for tool in tools]
    print(f"Available MCP tools: {tool_names}")

async def start_conversation(agent):
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() == "exit":
                break

            response = await agent.process_user_query(user_input)
            print("AI:", response)

        except Exception as e:
            logger.error(f"An error occurred during query processing: {e}", exc_info=True)
            print("AI: An unexpected error occurred. Please try again.")

# --- Main Execution Loop ---
async def main():
    async with LLMAgent() as agent:
        await ollama_status_check(agent)
        show_console_intro_prompt()
        await show_available_tools(agent)
        await start_conversation(agent)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error in main execution: {e}", exc_info=True)
        sys.exit(1)
