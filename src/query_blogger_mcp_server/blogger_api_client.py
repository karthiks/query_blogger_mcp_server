# This class will encapsulate the logic for calling the actual Blogger API.

import httpx
import logging
import json
from typing import Dict, List, Optional
from query_blogger_mcp_server.html_util import html_to_markdown

logger = logging.getLogger(__name__)

class BloggerAPIClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Blogger API Key must be provided.")
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/blogger/v3"
        self.client = httpx.AsyncClient() # Asynchronous HTTP client

    async def get_blog_by_url(self, blog_url: str) -> Optional[Dict]:
        """
        Retrieves blog by its URL.
        https://developers.google.com/blogger/docs/3.0/reference/blogs/getByUrl
        """
        params = {"url": blog_url, "key": self.api_key}
        try:
            response = await self.client.get(f"{self.base_url}/blogs/byurl", params=params)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error retrieving blog by URL {blog_url}: {e.response.status_code} - {e.response.text}")
            # Consider specific error handling for 404 vs other errors
            if e.response.status_code == 404:
                return None # Blog not found
            return {"error": f"Blogger API error: {e.response.status_code} - {e.response.text}"}
        except httpx.RequestError as e:
            logger.error(f"Network error retrieving blog by URL {blog_url}: {e}")
            return {"error": f"Network error connecting to Blogger API: {e}"}


    async def get_recent_posts(self, blog_id: str, max_results: int = 3, with_body:bool = True) -> Optional[Dict]:
        """
        Retrieves a list of posts for a given blog ID.
        https://developers.google.com/blogger/docs/3.0/reference/posts/list
        """
        params = {
            "key": self.api_key,
            "maxResults": max_results,
            "orderBy": "updated",
            "fetchBodies": with_body
        }
        try:
            response = await self.client.get(f"{self.base_url}/blogs/{blog_id}/posts", params=params)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"RESULT: BLOG TITLES = {[item['title'] for item in result.get('items',[])]}")  # Debugging line to check the raw response
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error retrieving posts for blog {blog_id}: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 404:
                return None # Blog or posts not found
            return {"error": f"Blogger API error: {e.response.status_code} - {e.response.text}"}
        except httpx.RequestError as e:
            logger.error(f"Network error retrieving posts for blog {blog_id}: {e}")
            return {"error": f"Network error connecting to Blogger API: {e}"}


    async def list_recent_posts(self, blog_id: str, max_results: int = 5) -> Optional[Dict]:
        """
        Lists recent posts for a given blog ID.
        This is a convenience method that uses get_recent_posts.
        """
        result =  await self.get_recent_posts(blog_id, max_results=max_results, with_body=False)
        return result


    async def search_posts(self, blog_id:str, query_terms: str, max_results: int = 5, with_body:bool = True) -> Optional[Dict]:
        """
        Searches for posts in a blog by query terms.
        https://developers.google.com/blogger/docs/3.0/reference/posts/list
        """
        params = {
            "key": self.api_key,
            "q": query_terms,
            "orderBy":"published",
            "fetchBodies": with_body
        }
        try:
            response = await self.client.get(f"{self.base_url}/blogs/{blog_id}/posts/search", params=params)
            response.raise_for_status()
            result = BloggerAPIClient.process_blog_posts(response.json(), max_results)
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error searching posts in blog {blog_id}: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 404:
                return None

    @staticmethod
    def process_blog_posts(dict_data,max_results):
        """Process JSON data to convert all HTML fields to Markdown"""

        if 'items' in dict_data:
            dict_data['items'] = dict_data['items'][:max_results]
            for item in dict_data['items']:
                if 'content' in item:
                    item['content'] = html_to_markdown(item['content'])

        return dict_data
