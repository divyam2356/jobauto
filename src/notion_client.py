import os
import logging
from datetime import datetime, timezone

from notion_client import Client as NotionClient

logger = logging.getLogger(__name__)


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


def fetch_existing_urls(notion, database_id):
    urls = set()
    has_more = True
    start_cursor = None

    while has_more:
        response = query_database(notion, database_id, start_cursor)

        for page in response.get("results", []):
            props = page.get("properties", {})
            url_prop = props.get("Apply URL", {})
            url_value = url_prop.get("url")
            if url_value:
                urls.add(url_value)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    logger.info(f"Notion: found {len(urls)} existing job URLs")
    return urls


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

    try:
        notion.pages.create(parent={"database_id": database_id}, properties=properties)
        return True
    except Exception as e:
        logger.error(f"Failed to create Notion page for '{title}' at '{company}': {e}")
        return False


def upload_jobs(jobs):
    notion = get_client()
    database_id = get_database_id()
    existing_urls = fetch_existing_urls(notion, database_id)

    date_found = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    created = 0
    skipped = 0

    for job in jobs:
        url = job.get("url", "")

        if url and url in existing_urls:
            skipped += 1
            continue

        if create_page(notion, database_id, job, date_found):
            created += 1
            if url:
                existing_urls.add(url)

    logger.info(f"Notion: created {created} new pages, skipped {skipped} duplicates")
    return created
