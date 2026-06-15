import os
import sys
import logging

from dotenv import load_dotenv
from notion_client import Client as NotionClient

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


DATABASE_TITLE = "Job Aggregator"
DATABASE_SCHEMA = {
    "Title": {"title": {}},
    "Company": {"rich_text": {}},
    "Location": {"rich_text": {}},
    "Source": {
        "select": {
            "options": [
                {"name": "linkedin", "color": "blue"},
                {"name": "adzuna", "color": "green"},
                {"name": "remoteok", "color": "purple"},
                {"name": "arbeitnow", "color": "yellow"},
                {"name": "greenhouse", "color": "orange"},
                {"name": "ashby", "color": "red"},
            ]
        }
    },
    "Apply URL": {"url": {}},
    "Date Found": {"date": {}},
    "Tags": {
        "multi_select": {
            "options": [
                {"name": "ml-engineer", "color": "blue"},
                {"name": "software-engineer", "color": "green"},
                {"name": "data-scientist", "color": "purple"},
            ]
        }
    },
}


def find_parent_page(notion):
    response = notion.search(filter={"property": "object", "value": "page"}, page_size=20)
    pages = response.get("results", [])

    if not pages:
        print("\nNo pages found! Make sure your integration is connected to a page.")
        print("Run this locally first, then set NOTION_DATABASE_ID in GitHub secrets.")
        return None

    if len(pages) == 1:
        page_id = pages[0]["id"]
        title_prop = pages[0].get("properties", {}).get("title", {})
        title_items = title_prop.get("title", [])
        title = title_items[0].get("plain_text", "Untitled") if title_items else "Untitled"
        print(f"\nUsing page: {title} ({page_id})")
        return page_id

    print("\nFound these Notion pages:\n")
    for i, page in enumerate(pages):
        title_prop = page.get("properties", {}).get("title", {})
        title_items = title_prop.get("title", [])
        title = title_items[0].get("plain_text", "Untitled") if title_items else "Untitled"
        page_id = page["id"]
        print(f"  [{i + 1}] {title}  (id: {page_id})")

    print(f"\n  [0] Create a NEW top-level page\n")

    while True:
        try:
            choice = int(input("Pick a page number to create the database in: "))
            if choice == 0:
                return None
            if 1 <= choice <= len(pages):
                return pages[choice - 1]["id"]
        except (ValueError, EOFError):
            pass
        print("Invalid choice, try again.")


def create_database(notion, parent_page_id=None):
    if parent_page_id:
        parent = {"type": "page_id", "page_id": parent_page_id}
    else:
        parent = {"type": "workspace", "workspace": True}

    database = notion.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": DATABASE_TITLE}}],
        properties=DATABASE_SCHEMA,
    )

    db_id = database["id"]
    db_url = database.get("url", "")

    print("\n" + "=" * 60)
    print("Notion database created successfully!")
    print("=" * 60)
    print(f"\n  Database ID:  {db_id}")
    print(f"  Database URL: {db_url}")
    print(f"\n  Add this to your .env file or GitHub secrets:")
    print(f"    NOTION_DATABASE_ID={db_id}")
    print("=" * 60)

    return db_id


def main():
    token = os.getenv("NOTION_TOKEN", "")
    if not token:
        token = input("Enter your Notion integration token (starts with ntn_): ").strip()
        if not token:
            print("Error: No token provided")
            sys.exit(1)
        os.environ["NOTION_TOKEN"] = token

    notion = NotionClient(auth=token, notion_version="2022-06-28")

    print("\nNotion Database Setup")
    print("=" * 60)
    print("This will create a 'Job Aggregator' database in your Notion workspace.")
    print("Make sure your Notion integration has been added to a page first.")
    print("=" * 60)

    parent_page_id = find_parent_page(notion)

    if parent_page_id:
        print(f"\nCreating database in selected page...")
    else:
        print(f"\nCreating database at workspace root...")

    db_id = create_database(notion, parent_page_id)

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "NOTION_DATABASE_ID=" in content:
            import re
            content = re.sub(
                r"NOTION_DATABASE_ID=.*",
                f"NOTION_DATABASE_ID={db_id}",
                content,
            )
        else:
            content += f"\nNOTION_DATABASE_ID={db_id}\n"

        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n  Updated .env with NOTION_DATABASE_ID")
    else:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"NOTION_TOKEN={token}\nNOTION_DATABASE_ID={db_id}\n")
        print(f"\n  Created .env with NOTION_DATABASE_ID")

    print("\nDone! You can now run: python -m src.main\n")


if __name__ == "__main__":
    main()
