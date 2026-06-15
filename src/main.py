import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    config_path = os.path.join(PROJECT_ROOT, "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_api_jobs(config):
    from src.api_fetchers import adzuna, remoteok, arbeitnow, greenhouse, ashby

    fetchers = [
        ("adzuna", adzuna),
        ("remoteok", remoteok),
        ("arbeitnow", arbeitnow),
        ("greenhouse", greenhouse),
        ("ashby", ashby),
    ]

    all_jobs = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_name = {}
        for name, fetcher in fetchers:
            future = executor.submit(fetcher.fetch, config)
            future_to_name[future] = name

        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
                logger.info(f"{name}: {len(jobs)} jobs")
            except Exception as e:
                logger.error(f"{name} fetcher failed: {e}")

    return all_jobs


def fetch_linkedin_jobs(config):
    from src.scrapy_run import run_spiders

    queries = []
    linkedin_config = config.get("linkedin", {})
    search_queries = linkedin_config.get("search_queries", [])
    max_pages = linkedin_config.get("max_pages_per_query", 5)

    for sq in search_queries:
        queries.append({
            "keywords": sq["keywords"],
            "locations": sq.get("locations", ["remote"]),
            "max_pages": max_pages,
        })

    jobs = run_spiders(queries)
    return jobs


def main():
    logger.info("=" * 60)
    logger.info("Job Aggregator - Starting daily run")
    logger.info("=" * 60)

    config = load_config()

    logger.info("Step 1: Clearing Notion database...")
    from src.notion_client import clear_database
    cleared = clear_database()
    logger.info(f"Cleared {cleared} old jobs from Notion")

    logger.info("Step 2: Fetching jobs from APIs...")
    api_jobs = fetch_api_jobs(config)
    logger.info(f"Total API jobs: {len(api_jobs)}")

    logger.info("Step 3: Fetching LinkedIn jobs...")
    linkedin_jobs = fetch_linkedin_jobs(config)
    logger.info(f"Total LinkedIn jobs: {len(linkedin_jobs)}")

    all_jobs = api_jobs + linkedin_jobs
    logger.info(f"Total combined jobs: {len(all_jobs)}")

    from src.filters import filter_jobs, deduplicate, sort_by_recency
    filtered = filter_jobs(all_jobs, config)
    deduped = deduplicate(filtered)
    sorted_jobs = sort_by_recency(deduped)
    logger.info(f"After filtering + dedup: {len(sorted_jobs)} jobs")

    if not sorted_jobs:
        logger.info("No new jobs to upload")
        return

    logger.info("Step 4: Uploading new jobs to Notion...")
    from src.notion_client import upload_jobs
    created = upload_jobs(sorted_jobs)
    logger.info(f"Uploaded {created} new jobs to Notion")

    logger.info("=" * 60)
    logger.info(f"Done! {created} new jobs added to Notion database")
    logger.info("=" * 60)


def ensure_notion_db():
    db_id = os.getenv("NOTION_DATABASE_ID", "")
    token = os.getenv("NOTION_TOKEN", "")
    if db_id:
        return True

    is_ci = os.getenv("CI", "") or os.getenv("GITHUB_ACTIONS", "")
    if is_ci:
        logger.error("NOTION_DATABASE_ID not set in GitHub secrets. Skipping Notion upload.")
        return False

    if not token:
        print("\nNOTION_TOKEN not found. Let's set up your Notion database.\n")
    else:
        print("\nNOTION_DATABASE_ID not found. Let's create your Notion database.\n")
    try:
        from setup_notion import main as setup_main
        setup_main()
        load_dotenv(override=True)
        return bool(os.getenv("NOTION_DATABASE_ID", ""))
    except Exception as e:
        print(f"\nSetup failed: {e}")
        print("Run manually: python setup_notion.py")
        return False


if __name__ == "__main__":
    if "--setup" in sys.argv or not os.getenv("NOTION_DATABASE_ID", ""):
        if not ensure_notion_db():
            is_ci = os.getenv("CI", "") or os.getenv("GITHUB_ACTIONS", "")
            if not is_ci:
                sys.exit(1)
    main()
