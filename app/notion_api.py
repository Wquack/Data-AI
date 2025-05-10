
 # Replace with your Notion API token
from notion_client import Client
import logging

logger = logging.getLogger(__name__)

NOTION_TOKEN = "ntn_m5661501363RL0yPcwtcZL8NiyvuIWWnRgnWwNddQUx4qT"  # Replace with your Notion API token
notion = Client(auth=NOTION_TOKEN)

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

def create_notion_page(event_summary, parent_page_id=None):
    """Generate a new page in Notion under the specified parent page."""
    try:
        if not parent_page_id:
            # Fallback: Search for a default page or create one
            search_response = notion.search(
                query="DATA_AI Notes",
                filter={"value": "page", "property": "object"}
            )
            pages = search_response.get("results", [])
            for page in pages:
                if page["properties"]["title"]["title"][0]["plain_text"] == "DATA_AI Notes":
                    parent_page_id = page["id"]
                    logger.info(f"Found default parent page 'DATA_AI Notes' with ID: {parent_page_id}")
                    break
            if not parent_page_id:
                create_response = notion.pages.create(
                    parent={"type": "workspace"},
                    properties={
                        "title": {
                            "type": "title",
                            "title": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": "DATA_AI Notes"
                                    }
                                }
                            ]
                        }
                    }
                )
                parent_page_id = create_response["id"]
                logger.info(f"Created default parent page 'DATA_AI Notes' with ID: {parent_page_id}")

        response = notion.pages.create(
            parent={"page_id": parent_page_id},
            properties={
                "title": {
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {
                                "content": f"Notes for {event_summary}"
                            }
                        }
                    ]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": "Review relevant project notes."
                                }
                            }
                        ]
                    }
                }
            ]
        )
        logger.info(f"Created Notion page: {response['url']}")
        return {"action": "Created note", "details": {"page_id": response['id'], "url": response['url']}}
    except Exception as e:
        logger.error(f"Error creating Notion page: {e}")
        raise