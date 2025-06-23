import os
import uvicorn
from mcp.server.fastmcp import FastMCP
from blogger_api_client import BloggerAPIClient
import logging
from urllib.parse import urlparse

# Blogger MCP Server for querying public Blogger content
# This server provides read-only tools to query public Blogger content from specific, allowed domains.
# This is where you define your MCP tools, implement domain filtering, and map to the Blogger API client.

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("blogger_mcp_server")

# --- Configuration for Blogger API and Allowed Domains ---
# IMPORTANT: Store your API Key securely (e.g., in environment variables)
BLOGGER_API_KEY = os.getenv("BLOGGER_API_KEY")
if not BLOGGER_API_KEY:
    logger.error("BLOGGER_API_KEY environment variable not set. Please set it.")
    exit(1)

# Define your ALLOWED_DOMAINS (e.g., yourcompanyblog.blogspot.com, blog.yourcompany.com)
# These should be the *exact* domains you allow.
ALLOWED_DOMAINS = {
    "blog.codonomics.com", # custom domain
    "kartzontech.blogspot.com"
}
logger.info(f"Allowed Blogger Domains: {ALLOWED_DOMAINS}")

# Initialize your Blogger API client
blogger_client = BloggerAPIClient(BLOGGER_API_KEY)

# Initialize FastMCP server
mcp = FastMCP(
    name="QueryBloggerMCPServer",
    version="0.1.0",
    description="Provides read-only tools to query public Blogger content from specific, allowed domains."
)

# Helper function to check if a URL belongs to an allowed domain
def _is_allowed_domain(blog_url: str) -> bool:
    try:
        parsed_url = urlparse(blog_url)
        # Check netloc (domain + port)
        return parsed_url.netloc in ALLOWED_DOMAINS
    except Exception as e:
        logger.warning(f"Failed to parse URL {blog_url} for domain check: {e}")
        return False

# --- MCP Tool: get_blog_info_by_url ---
@mcp.tool(
    # readOnlyHint=True is a good practice for tools that only read data
    annotations={"readOnlyHint": True},
    # Provide a good description for the LLM
    description="Retrieves public information about a Blogger blog given its URL. ONLY works for allowed, pre-configured domains."
)
async def get_blog_info_by_url(blog_url: str) -> dict:
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
        # Transform the raw API response to a clean, LLM-friendly format
        return {
            "blog_id": blog_data.get("id"),
            "blog_title": blog_data.get("name"),
            "blog_url": blog_data.get("url"),
            "description": blog_data.get("description", "No description available."),
            "published_date": blog_data.get("published")
        }
    else:
        return {"error": f"Could not retrieve information for blog at {blog_url}. It might not exist or there was an API issue."}

# --- MCP Tool: get_latest_posts_by_blog_url ---
@mcp.tool(
    annotations={"readOnlyHint": True},
    description="Fetches the most recent public blog posts for a specified blog URL. ONLY works for allowed, pre-configured domains."
)
async def get_latest_posts_by_blog_url(blog_url: str, num_posts: int = 3) -> dict:
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
    if not blog_data or not blog_data.get("id"):
        return {"error": f"Could not find blog ID for {blog_url}. It might not exist or there was an API issue."}

    blog_id = blog_data["id"]
    posts_data = await blogger_client.get_posts_by_blog_id(blog_id, max_results=num_posts)

    if posts_data and posts_data.get("items"):
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
        return {"error": f"No recent posts found for {blog_url} or an issue with the Blogger API."}

# You can add more read-only tools as needed, always checking the domain
# Example: @mcp.tool(annotations={"readOnlyHint": True})
# async def get_post_content_by_url(post_url: str) -> dict:
#     # Implement logic similar to above, including domain check and parsing post_url
#     # to get blog_id and post_id if necessary, then call blogger_client.get_post_by_blog_id_and_post_id

if __name__ == "__main__":
    print("Starting Blogger MCP Server via Uvicorn...")
    print("This server will expose read-only Blogger tools.")
    print(f"Blogger API Key: {'Set' if BLOGGER_API_KEY else 'NOT SET'}")
    print(f"Allowed Domains: {ALLOWED_DOMAINS}")
    print(f"Base URL for Uvicorn: http://127.0.0.1:8000")

    app = mcp.app
    uvicorn.run(app, host="0.0.0.0", port=8000)