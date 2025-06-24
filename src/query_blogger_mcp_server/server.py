# Blogger MCP Server for querying public Blogger content
# This server provides read-only tools to query public Blogger content from specific, allowed domains.
# This is where you define your MCP tools, implement domain filtering, and map to the Blogger API client.

import uvicorn
from mcp.server.fastmcp import FastMCP
import logging
from urllib.parse import urlparse
from typing import Dict

# Import components from our own package
from query_blogger_mcp_server.blogger_api_client import BloggerAPIClient
from query_blogger_mcp_server.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("query_blogger_mcp_server")

# --- Initialize Blogger API client using settings ---
# This will raise a ValueError if BLOGGER_API_KEY is not set, as handled in BloggerAPIClient's __init__
blogger_client = BloggerAPIClient(settings.BLOGGER_API_KEY)

# --- Initialize FastMCP server using settings for metadata ---
mcp = FastMCP(
    name=settings.MCP_SERVER_NAME,
    version=settings.MCP_SERVER_VERSION,
    description=settings.MCP_SERVER_DESCRIPTION
)

# Helper function to check if a URL belongs to an allowed domain
def _is_allowed_domain(blog_url: str) -> bool:
    if not settings.ALLOWED_DOMAINS:
        logger.warning("ALLOWED_DOMAINS is empty. All domains will be disallowed by default for security.")
        return False # If no allowed domains are configured, disallow all

    try:
        parsed_url = urlparse(blog_url)
        # Check netloc (domain + port)
        is_allowed = parsed_url.netloc in settings.ALLOWED_DOMAINS
        if(not is_allowed):
            logger.warning(f"Domain {parsed_url.netloc} is not in allowed domains")
        return is_allowed
    except Exception as e:
        logger.warning(f"Failed to parse URL {blog_url} for domain check: {e}")
        return False

# --- MCP Tool: get_blog_info_by_url ---
@mcp.tool(
    annotations={"readOnlyHint": True},
    description="Retrieves public information about a Blogger blog given its URL. ONLY works for allowed, pre-configured domains."
)
async def get_blog_info_by_url(blog_url: str) -> Dict:
    """
    Retrieves public information about a Blogger blog by its URL.
    This tool only queries blogs from a list of pre-approved domains for security and scope.

    Args:
        blog_url (str): The full URL of the blog (e.g., "https://yourcompanyblog.blogspot.com").

    Returns:
        dict: A dictionary containing the blog's title, ID, URL, description, and published date,
              or an error message if the blog is not found or not from an allowed domain.
    """
    logger.info(f"Received tool call: get_blog_info_by_url for {blog_url}")

    if not _is_allowed_domain(blog_url):
        logger.warning(f"Attempted to query disallowed domain: {blog_url}")
        return {"error": "Access denied: This tool can only query blogs from pre-approved domains.", "requested_url": blog_url}

    blog_data = await blogger_client.get_blog_by_url(blog_url)

    if blog_data:
        # Check if blog_data contains an 'error' key from the client, indicating an API issue
        if "error" in blog_data:
            return {"error": f"Failed to retrieve blog info: {blog_data['error']}", "requested_url": blog_url}
        # Transform the raw API response to a clean, LLM-friendly format
        return {
            "blog_id": blog_data.get("id"),
            "blog_title": blog_data.get("name"),
            "blog_url": blog_data.get("url"),
            "description": blog_data.get("description", "No description available."),
            "published_date": blog_data.get("published")
        }
    else:
        return {"error": f"Could not find blog at {blog_url}. It might not exist or the URL is incorrect.", "requested_url": blog_url}

# --- MCP Tool: get_latest_posts_by_blog_url ---
@mcp.tool(
    annotations={"readOnlyHint": True},
    description="Fetches the most recent public blog posts for a specified blog URL. ONLY works for allowed, pre-configured domains."
)
async def get_latest_posts_by_blog_url(blog_url: str, num_posts: int = 3) -> Dict:
    """
    Fetches the most recent public blog posts for a given blog URL.
    This tool only queries blogs from a list of pre-approved domains.

    Args:
        blog_url (str): The full URL of the blog.
        num_posts (int): The maximum number of posts to retrieve (default is 3).

    Returns:
        dict: A dictionary containing the blog's title and a list of recent posts
              (each with title, URL, published date), or an error message.
    """
    logger.info(f"Received tool call: get_latest_posts_by_blog_url for {blog_url}, posts: {num_posts}")

    if not _is_allowed_domain(blog_url):
        logger.warning(f"Attempted to query disallowed domain: {blog_url}")
        return {"error": "Access denied: This tool can only query posts from pre-approved domains.", "requested_url": blog_url}

    blog_data = await blogger_client.get_blog_by_url(blog_url)
    if not blog_data or "error" in blog_data or not blog_data.get("id"):
        return {"error": f"Could not find blog for {blog_url}. It might not exist or there was an API issue.", "requested_url": blog_url}

    blog_id = blog_data["id"]
    posts_data = await blogger_client.get_posts_by_blog_id(blog_id, max_results=num_posts)

    if posts_data and posts_data.get("items"):
        # Check if posts_data contains an 'error' key from the client, indicating an API issue
        if "error" in posts_data:
            return {"error": f"Failed to retrieve posts: {posts_data['error']}", "blog_url": blog_url}

        # Transform posts data for LLM
        posts = [
            {
                "title": post.get("title"),
                "url": post.get("url"),
                "published": post.get("published")
            }
            for post in posts_data["items"]
        ]
        return {
            "blog_title": blog_data.get("name"),
            "blog_url": blog_url,
            "total_posts_found": posts_data.get("totalItems", len(posts)),
            "recent_posts": posts
        }
    else:
        return {"error": f"No recent posts found for {blog_url} or an issue with the Blogger API.", "blog_url": blog_url}

if __name__ == "__main__":
    logger.info("Starting QueryBlogger MCP Server via Uvicorn...")
    logger.info(f"Blogger API Key: {'Set' if settings.BLOGGER_API_KEY else 'NOT SET (CRITICAL!)'}")
    logger.info(f"Allowed Domains: {settings.ALLOWED_DOMAINS}")
    logger.info(f"Server Host: {settings.UVICORN_HOST}, Port: {settings.UVICORN_PORT}")

    uvicorn.run(mcp, host=settings.UVICORN_HOST, port=settings.UVICORN_PORT)