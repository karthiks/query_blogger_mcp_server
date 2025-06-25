import httpx
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple

# --- MCP Server Configuration (Assumed to be running) ---
MCP_SERVER_BASE_URL = "http://172.18.228.135:8000" # Know your WSL IP or use localhost if running on the same machine

# --- Configure basic logging for the agent client ---
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Use __name__ for module-specific logging

class MCPAgentTools:
    """
    A class encapsulating the MCP tools available from the query_blogger_mcp_server.
    """
    def __init__(self):
        self.client = httpx.AsyncClient()
        # Define common headers expected by the MCP server
        # Generate a session ID once for this client instance
        # self.session_id = str(uuid.uuid4())
        # Define common headers expected by the MCP server and pass them to AsyncClient
        self.headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            # "mcp-session-id": self.session_id, # Generate a session ID for each client instance
        }
        self.client = httpx.AsyncClient(headers=self.headers)
        logger.info(f"MCP Agent Tools initialized for fixed server: {MCP_SERVER_BASE_URL}")

        # These tool definitions mimic what an LLM would "know" about your server.
        # In a real scenario, the LLM would dynamically get this from /mcp endpoint.
        self.available_tools = {
            "get_blog_info_by_url": {
                "description": "Retrieves public information about a Blogger blog given its URL. ONLY works for allowed, pre-configured domains.",
                "parameters": {
                    "blog_url": {"type": "string", "description": "The full URL of the blog (e.g., 'https://yourcompanyblog.blogspot.com')."}
                }
            },
            "get_latest_posts_by_blog_url": {
                "description": "Fetches the most recent public blog posts for a specified blog URL. Optionally fetches full content for the knowledge base. ONLY works for allowed, pre-configured domains.",
                "parameters": {
                    "blog_url": {"type": "string", "description": "The full URL of the blog."},
                    "num_posts": {"type": "integer", "description": "The maximum number of posts to retrieve (default is 3)."},
                    "include_content": {"type": "boolean", "description": "Whether to fetch full post content and add to the knowledge base (default is false)."}
                }
            },
        }

    async def call_mcp_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Makes an asynchronous call to the MCP server for a specific tool.
        Handles SSE-formatted responses and nested JSON.
        """
        url = f"{MCP_SERVER_BASE_URL}/mcp/tool/{tool_name}"
        logger.info(f"Agent calling MCP tool: {tool_name} with params: {tool_params}")

        # Construct the full JSON-RPC 2.0 payload
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call", # Correct JSON-RPC method for calling a tool
            "params": {
                "name": tool_name,    # The actual tool name goes here
                "arguments": tool_params # The tool's arguments go under 'arguments'
            },
            "id": str(uuid.uuid4()) # Unique request ID for the JSON-RPC call
        }

        try:
            response = await self.client.post(url, json=json_rpc_payload)
            response.raise_for_status()

            raw_response_text = response.text
            logger.debug(f"Raw response status: {response.status_code}")
            logger.debug(f"Raw response headers: {response.headers}")
            logger.debug(f"Raw response text (first 500 chars): {raw_response_text[:500]}")

            parsed_sse_data = {}
            if raw_response_text.startswith("event: message"):
                # Extract the JSON string from the "data:" line
                data_line = raw_response_text.split("data:", 1)[1].strip()
                try:
                    parsed_sse_data = json.loads(data_line)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decoding error of SSE data payload: {e}. Data line: '{data_line}'")
                    return {"error": f"JSON decoding error of SSE data payload: {e}. Raw data: '{data_line}'"}
            else:
                # If it's not SSE, try to parse directly as JSON
                try:
                    parsed_sse_data = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decoding error of direct response: {e}. Raw response text: '{raw_response_text}'")
                    return {"error": f"JSON decoding error of direct response: {e}. Raw response: '{raw_response_text}'"}

            # Now, process the parsed_sse_data (which is the JSON from the 'data:' line)
            # This is where the actual JSON-RPC result or error is
            final_result = {}
            if "result" in parsed_sse_data:
                # Check for nested JSON string within content[0].text
                if (isinstance(parsed_sse_data["result"], dict) and
                    "content" in parsed_sse_data["result"] and
                    isinstance(parsed_sse_data["result"]["content"], list) and
                    len(parsed_sse_data["result"]["content"]) > 0 and
                    isinstance(parsed_sse_data["result"]["content"][0], dict) and
                    "type" in parsed_sse_data["result"]["content"][0] and
                    parsed_sse_data["result"]["content"][0]["type"] == "text" and
                    "text" in parsed_sse_data["result"]["content"][0]
                ):
                    nested_json_str = parsed_sse_data["result"]["content"][0]["text"]
                    try:
                        final_result = json.loads(nested_json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decoding error of nested content text: {e}. Nested text: '{nested_json_str}'")
                        return {"error": f"JSON decoding error of nested content: {e}. Raw nested text: '{nested_json_str}'"}
                else:
                    # If not nested text, assume the result itself is the final data
                    final_result = parsed_sse_data["result"]
            elif "error" in parsed_sse_data:
                # This handles JSON-RPC errors from the server
                return {"error": f"MCP server JSON-RPC error: {parsed_sse_data['error'].get('message', 'Unknown error')}"}
            else:
                return {"error": "Unexpected JSON-RPC response format from MCP server (missing 'result' or 'error' key)."}

            logger.info(f"MCP Tool {tool_name} final parsed response: {json.dumps(final_result, indent=2)}")
            return final_result # Return the final, correctly parsed dictionary

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {tool_name}: {e.response.status_code} - {e.response.text}")
            return {"error": f"Tool call failed: HTTP {e.response.status_code} - {e.response.text}"}
        except httpx.RequestError as e:
            logger.error(f"Network error calling {tool_name}: {e}")
            return {"error": f"Tool call failed: Network error - {e}"}
        except Exception as e:
            logger.error(f"Unexpected error calling {tool_name}: {e}", exc_info=True) # Add exc_info for full traceback
            return {"error": f"Tool call failed: Unexpected error - {e}"}

    async def close(self):
        """Close the httpx client session."""
        await self.client.aclose()

