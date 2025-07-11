import httpx
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime, timedelta


logger = logging.getLogger(__name__) # Use __name__ for module-specific logging

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict
    method: str

    def to_dict(self) -> Dict[str, Any]:
        """Standardized serialization format for tools"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "method": self.method,
            "metadata": {
                "type": "mcp_tool",
                "version": "1.0"
            }
        }


class MCPAgentTools:
    """
    A class encapsulating the MCP tools available from the query_blogger_mcp_server.
    Dynamically fetches and manages MCP tools from the server.
    Implements caching with automatic refresh.
    """

    def __init__(self, base_url: str, cache_ttl: int = 300):
        self.base_url = base_url
        self.cache_ttl = timedelta(seconds=cache_ttl)
        self._last_refresh = None
        self._available_tools = None

        # Define common headers expected by the MCP server and pass them to AsyncClient
        self.headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        logger.info(f"MCP Agent Tools initialized for fixed server: {self.base_url}")

    def _parse_response(self, response) -> Dict:
        raw_response_text = response.text
        logger.debug(f"Raw response status: {response.status_code}")
        logger.debug(f"Raw response headers: {response.headers}")
        logger.debug(f"Raw response text (first 500 chars): {raw_response_text[:500]}")

        parsed_sse_data = {}
        if raw_response_text.startswith("event: message"):
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
        logger.debug(f"parsed_sse_data = {parsed_sse_data}")
        return parsed_sse_data

    async def _fetch_tools(self) -> List[ToolDefinition]:
        """Fetch tool definitions from MCP server's discovery endpoint"""
        # Ref.: https://modelcontextprotocol.io/specification/2025-06-18/server/tools#listing-tools
        try:
            response = await self.client.post(
                f"{self.base_url}/mcp/",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": 1
                }
            )
            response.raise_for_status()

            methods = self._parse_response(response) \
                .get("result", []) \
                .get("tools",[])
            logger.info(f"methods = {methods}")
            return [
                ToolDefinition(
                    name=method["name"],
                    description=method.get("description", ""),
                    parameters=method.get("parameters", {}),
                    method=method["name"]
                )
                for method in methods
            ]
        except Exception as e:
            logger.error(f"Failed to fetch tools: {str(e)}")
            return []

    async def get_tools(self, force_refresh: bool = False) -> List[ToolDefinition]:
        """Get available tools with caching"""
        now = datetime.now()

        if force_refresh or not self._available_tools or \
           (self._last_refresh and (now - self._last_refresh) > self.cache_ttl):
            logger.info("Refreshing tool definitions from MCP server")
            self._available_tools = await self._fetch_tools()
            self._last_refresh = now

        return self._available_tools or []

    async def call_mcp_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool via JSON-RPC
        Handles SSE-formatted responses and nested JSON.
        """
        # url = f"{self.base_url}/mcp/tool/{tool_name}"
        # url = f"{self.base_url}/mcp/call_tool" # Updated to match MCP spec for calling tools
        # url = f"{self.base_url}/mcp/tools/call" # Updated to match MCP spec for calling tools
        url = f"{self.base_url}/mcp/" # Note the ending /, without it the MCP server will return 307 Temporary Redirect
        logger.info(f"Agent calling MCP tool: {tool_name} with params: {tool_params}")

        # Construct the full JSON-RPC 2.0 payload
        # Ref.: https://modelcontextprotocol.io/specification/2025-06-18/server/tools#calling-tools
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

