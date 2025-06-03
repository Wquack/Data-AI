from notion_client import Client
import logging
from datetime import datetime
from utils.token_store import load_tokens

logger = logging.getLogger(__name__)

def get_notion_client(user_id: str) -> Client:
    """Get authenticated Notion client for the user"""
    tokens = load_tokens(user_id)
    if not tokens or "notion" not in tokens:
        raise Exception("Notion not connected. Please authenticate via /auth/notion.")
    
    notion_tokens = tokens["notion"]
    access_token = notion_tokens.get("access_token")
    
    if not access_token:
        raise Exception("Notion access token not found. Please re-authenticate via /auth/notion.")
    
    return Client(auth=access_token)

def list_notion_pages(user_id: str):
    """List all pages accessible to the user's Notion integration."""
    try:
        notion = get_notion_client(user_id)
        
        search_response = notion.search(
            query="",  # Empty query to return all results
            filter={"value": "page", "property": "object"}
        )
        pages = search_response.get("results", [])
        page_list = []
        
        for page in pages:
            # Handle different page title structures
            title = "Untitled"
            if page.get("properties", {}).get("title", {}).get("title"):
                title_array = page["properties"]["title"]["title"]
                if title_array and len(title_array) > 0:
                    title = title_array[0]["plain_text"]
            elif page.get("properties", {}).get("Name", {}).get("title"):
                # Some pages use "Name" instead of "title"
                name_array = page["properties"]["Name"]["title"]
                if name_array and len(name_array) > 0:
                    title = name_array[0]["plain_text"]
            
            page_list.append({
                "id": page["id"], 
                "title": title, 
                "url": page["url"]
            })
        
        logger.info(f"Retrieved {len(page_list)} accessible pages for user {user_id}")
        return page_list
    except Exception as e:
        logger.error(f"Error listing Notion pages for user {user_id}: {e}")
        raise

def create_notion_page(event_summary: str, parent_page_id: str = None, user_id: str = None, drive_link: str = None, extra_text: str = None):
    """Generate a new page in Notion under the specified parent page."""
    try:
        if not user_id:
            raise Exception("User ID is required for Notion operations")
            
        notion = get_notion_client(user_id)
        
        # If no parent page specified, get user's pages and use the first one
        if not parent_page_id:
            user_pages = list_notion_pages(user_id)
            if not user_pages:
                raise Exception("No accessible pages found in user's Notion workspace. Please ensure the integration has access to at least one page.")
            
            parent_page_id = user_pages[0]["id"]  # Use first available page
            logger.info(f"Using first available page as parent: {user_pages[0]['title']}")

        # Clean the page ID (remove any URL parameters)
        if "?" in parent_page_id:
            parent_page_id = parent_page_id.split("?")[0]
        
        # Remove dashes from page ID for API compatibility
        parent_page_id = parent_page_id.replace("-", "")

        # Unique title with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_title = f"Notes for {event_summary} - {timestamp}"

        # Build dynamic blocks
        children_blocks = []

        # ✍️ Optional extra text (e.g., Zoom/Calendar summary)
        if extra_text:
            children_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": extra_text}
                    }]
                }
            })

        # 📎 Optional drive link block
        if drive_link:
            children_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"Slides: {drive_link}"}
                    }]
                }
            })

        # 🧾 Fallback block if no extra data
        if not children_blocks:
            children_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": "Review relevant project notes."}
                    }]
                }
            })

        response = notion.pages.create(
            parent={"page_id": parent_page_id},
            properties={
                "title": {
                    "title": [{
                        "type": "text",
                        "text": {"content": unique_title}
                    }]
                }
            },
            children=children_blocks
        )

        logger.info(f"Created Notion page for user {user_id}: {response['url']}")
        return {
            "action": "Created note",
            "details": {
                "page_id": response['id'],
                "url": response['url'],
                "title": unique_title
            }
        }

    except Exception as e:
        logger.error(f"Error creating Notion page for user {user_id}: {e}")
        raise

def search_notion_pages(user_id: str, query: str):
    """Search for pages in user's Notion workspace"""
    try:
        notion = get_notion_client(user_id)
        
        search_response = notion.search(
            query=query,
            filter={"value": "page", "property": "object"}
        )
        
        pages = search_response.get("results", [])
        page_list = []
        
        for page in pages:
            title = "Untitled"
            if page.get("properties", {}).get("title", {}).get("title"):
                title_array = page["properties"]["title"]["title"]
                if title_array and len(title_array) > 0:
                    title = title_array[0]["plain_text"]
            
            page_list.append({
                "id": page["id"],
                "title": title,
                "url": page["url"]
            })
        
        logger.info(f"Found {len(page_list)} pages matching '{query}' for user {user_id}")
        return page_list
        
    except Exception as e:
        logger.error(f"Error searching Notion pages for user {user_id}: {e}")
        raise