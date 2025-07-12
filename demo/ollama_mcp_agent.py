import sys
import httpx
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

from query_blogger_mcp_client import QueryBloggerMCPClient

# --- LLM API Configuration ---
LLM_API_URL = "http://codonomics.local:11434/api/chat"
OLLAMA_STATUS_URL = "http://codonomics.local:11434/api/tags"
MODEL_NAME = "qwen2.5:0.5b" # Choose a lightweight model suitable for your laptop

# --- MCP Server Configuration (Assumed to be running) ---
MCP_SERVER_BASE_URL = "http://172.18.228.135:8000" # Know your WSL IP or use localhost if running on the same machine

# --- Configure basic logging for the agent client ---
logging.basicConfig(level= logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Ollama API Interaction ---
async def _call_ollama_raw(user_input: str, context: Optional[str] = None) -> str:
    """Call the local Ollama API for chat completion with optional context."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Provide concise answers."},
    ]
    if context:
        messages.append({"role": "user", "content": f"Based on the following context, answer the question: {context}\n\nQuestion: {user_input}"})
    else:
        messages.append({"role": "user", "content": user_input})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False # Non-streaming response for simplicity
    }
    logger.info(f"Calling Ollama with prompt (first 10000 chars): {str(messages)[:10000]}...")
    try:
        async with httpx.AsyncClient(timeout=60) as client: # Increased timeout for LLM
            response = await client.post(LLM_API_URL, json=payload)
            response.raise_for_status()

            result = response.json()
            return result["message"]["content"]
    except httpx.RequestError as e:
        logger.error(f"Error calling Ollama: {str(e)}")
        return f"Error calling Ollama: {str(e)}"
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding error from Ollama response: {e}. Response text: {response.text}")
        return "Error: Could not decode Ollama's response."
    except Exception as e:
        logger.error(f"An unexpected error occurred during Ollama call: {e}")
        return f"An unexpected error occurred with Ollama."


# --- Agent Orchestration Logic ---
class LLMAgentWithMCP:
    """
    Orchestrates user queries by deciding between MCP tool calls and direct LLM calls.
    """
    def __init__(self):
        self.mcp_tools = QueryBloggerMCPClient(MCP_SERVER_BASE_URL)
        self.known_blogs = {
            "our company blog": "https://blog.codonomics.com",
            "company blog's alias URL": "https://kartzontech.blogspot.com",
        }
        logger.info("LLM Agent with MCP initialized.")

    async def list_available_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the MCP server."""
        tools = await self.mcp_tools.get_tools()
        logger.info(f"Discovered {len(tools)} tools")
        return [tool.to_dict() for tool in tools]

    async def _get_blog_url_from_query(self, query: str) -> Optional[str]:
        """Helper to extract blog URL based on keywords."""
        for key, url in self.known_blogs.items():
            if key in query.lower():
                return url
        return None

    async def process_user_query(self, user_query: str) -> str:
        """
        Processes a user query by attempting to use MCP tools first,
        then falling back to the LLM if no tool is applicable or
        to synthesize a response from tool output.
        """
        lower_query = user_query.lower()
        blog_url = await self._get_blog_url_from_query(lower_query)

        # --- Tool 1: Get latest posts ---
        if "latest posts from" in lower_query and blog_url:
            num_posts_str = ''.join(filter(str.isdigit, lower_query.split("latest posts from")[0]))
            num_posts = int(num_posts_str) if num_posts_str.isdigit() else 3

            include_content = "with content" in lower_query or "for answering questions" in lower_query

            tool_output = await self.mcp_tools.call_mcp_tool(
                "get_latest_posts_by_blog_url",
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
                return await _call_ollama_raw(lower_query, context=context) # Synthesize with Ollama
            else:
                return f"Failed to get latest posts: {tool_output.get('error', 'No posts found.')}"

        # --- Tool 2: Get blog info ---
        elif ("about our blog" in lower_query) or (f"about {blog_url}" in lower_query and blog_url):
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
                return await _call_ollama_raw(lower_query, context=context) # Synthesize with Ollama
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

async def ollama_status_check():
    """Check if Ollama is running by querying its status endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(OLLAMA_STATUS_URL, timeout=10)
            response.raise_for_status()
            return True
    except httpx.RequestError as e:
        logger.error(f"Error connecting to Ollama at {OLLAMA_STATUS_URL}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking Ollama status: {e}")
        return False

def show_console_intro_prompt():
    print(f"Using local LLM model: {MODEL_NAME}")
    print(f"Connecting to MCP Server at: {MCP_SERVER_BASE_URL}")

    print("\nHow can I help you with your Blogger content? (Type 'exit' to quit)")
    print("Try questions like:")
    print("  - 'Tell me about our company blog.'")
    print("  - 'Get latest 3 posts from the dev blog with content for answering questions.'")
    print("  - 'Answer question about the dev blog: What is X?' (requires content loaded first)")
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
    if(not ollama_status_check()):
        print(f"Error: Ollama is not running or not reachable at {OLLAMA_STATUS_URL}.")
        print("Please ensure Ollama is running and the model is available.")
        sys.exit(1)

    show_console_intro_prompt()

    async with LLMAgentWithMCP() as agent:
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
