import os
import logging
from datetime import datetime, timezone

from notion_client import Client as NotionClient

logger = logging.getLogger(__name__)


def _posted_to_sort_order(posted_date):
    if not posted_date:
        return 0
    try:
        dt = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return 0


def get_client():
    token = os.getenv("NOTION_TOKEN", "")
    if not token:
        raise ValueError("NOTION_TOKEN not set")
    return NotionClient(auth=token, notion_version="2022-06-28")


def get_database_id():
    db_id = os.getenv("NOTION_DATABASE_ID", "")
    if not db_id:
        raise ValueError("NOTION_DATABASE_ID not set")
    return db_id


def query_database(notion, database_id, start_cursor=None):
    body = {"page_size": 100}
    if start_cursor:
        body["start_cursor"] = start_cursor
    path = f"databases/{database_id}/query"
    return notion.request(path, "POST", body=body)


def create_page(notion, database_id, job, date_found):
    title = job.get("title", "Untitled")
    company = job.get("company", "Unknown")
    location = job.get("location", "")
    source = job.get("source", "")
    url = job.get("url", "")
    posted = job.get("posted_date", "")

    properties = {
        "Name": {
            "title": [{"text": {"content": title[:2000]}}]
        },
        "Company": {
            "rich_text": [{"text": {"content": company[:2000]}}]
        },
        "Location": {
            "rich_text": [{"text": {"content": location[:2000]}}]
        },
        "Source": {
            "select": {"name": source}
        },
        "Apply URL": {
            "url": url if url else None
        },
        "Date Found": {
            "date": {"start": date_found}
        },
    }

    tags = job.get("tags", [])
    if tags:
        properties["Tags"] = {
            "multi_select": [{"name": tag} for tag in tags[:10]]
        }

    sort_order = _posted_to_sort_order(posted)
    if sort_order:
        properties["Sort Order"] = {
            "number": sort_order
        }

    try:
        notion.pages.create(parent={"database_id": database_id}, properties=properties)
        return True
    except Exception as e:
        logger.error(f"Failed to create Notion page for '{title}' at '{company}': {e}")
        return False


def upload_jobs(jobs):
    notion = get_client()
    database_id = get_database_id()

    date_found = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    created = 0

    for job in jobs:
        if create_page(notion, database_id, job, date_found):
            created += 1

    logger.info(f"Notion: created {created} new pages")
    return created


def clear_database():
    notion = get_client()
    database_id = get_database_id()

    has_more = True
    start_cursor = None
    archived = 0

    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        response = notion.request(f"databases/{database_id}/query", "POST", body=body)

        for page in response.get("results", []):
            try:
                notion.pages.update(page_id=page["id"], archived=True)
                archived += 1
            except Exception as e:
                logger.warning("Failed to archive page %s: %s", page["id"], e)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    logger.info(f"Notion: archived {archived} old pages")
    return archived


def _clear_database(notion, database_id):
    has_more = True
    start_cursor = None
    archived = 0

    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        response = notion.request(f"databases/{database_id}/query", "POST", body=body)

        for page in response.get("results", []):
            try:
                notion.pages.update(page_id=page["id"], archived=True)
                archived += 1
            except Exception as e:
                logger.warning("Failed to archive page %s: %s", page["id"], e)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    logger.info(f"Notion: archived {archived} old pages")


def _backfill_sort_order(notion, database_id):
    has_more = True
    start_cursor = None
    updated = 0

    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        response = notion.request(f"databases/{database_id}/query", "POST", body=body)

        for page in response.get("results", []):
            page_id = page["id"]
            props = page.get("properties", {})

            sort_prop = props.get("Sort Order", {})
            if sort_prop.get("number") is not None:
                continue

            posted = ""
            date_prop = props.get("Date Found", {})
            date_obj = date_prop.get("date")
            if date_obj and date_obj.get("start"):
                posted = date_obj["start"]

            if not posted:
                url_prop = props.get("Apply URL", {})
                url_value = url_prop.get("url", "")

            sort_val = _posted_to_sort_order(posted)
            if sort_val:
                notion.pages.update(page_id=page_id, properties={
                    "Sort Order": {"number": sort_val}
                })
                updated += 1

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    if updated:
        logger.info(f"Notion: backfilled Sort Order for {updated} pages")
