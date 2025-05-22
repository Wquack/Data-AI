
 # Replace with your Notion API token
from notion_client import Client
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

NOTION_TOKEN = "ntn_m5661501363RL0yPcwtcZL8NiyvuIWWnRgnWwNddQUx4qT"  # Replace with your Notion API token
notion = Client(auth=NOTION_TOKEN)

DEFAULT_PARENT_PAGE_ID = "1ee15173a7b3802cb116cd53d86d1973?pvs=12"

def list_notion_pages():
    """List all pages accessible to the integration."""
    try:
        search_response = notion.search(
            query="",  # Empty query to return all results
            filter={"value": "page", "property": "object"}
        )
        pages = search_response.get("results", [])
        page_list = []
        for page in pages:
            title = page["properties"]["title"]["title"][0]["plain_text"] if page["properties"]["title"]["title"] else "Untitled"
            page_list.append({"id": page["id"], "title": title, "url": page["url"]})
        logger.info(f"Retrieved {len(page_list)} accessible pages")
        return page_list
    except Exception as e:
        logger.error(f"Error listing Notion pages: {e}")
        raise

def create_notion_page(event_summary, parent_page_id=None, drive_link=None, extra_text=None):
    """Generate a new page in Notion under the specified parent page."""
    try:
        if not parent_page_id:
            parent_page_id = DEFAULT_PARENT_PAGE_ID
            logger.info(f"Using default parent page ID: {parent_page_id}")

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
                    "type": "title",
                    "title": [{
                        "type": "text",
                        "text": {"content": unique_title}
                    }]
                }
            },
            children=children_blocks
        )

        logger.info(f"Created Notion page: {response['url']}")
        return {
            "action": "Created note",
            "details": {
                "page_id": response['id'],
                "url": response['url']
            }
        }

    except Exception as e:
        logger.error(f"Error creating Notion page: {e}")
        raise
