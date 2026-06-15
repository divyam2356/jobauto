import logging
import re
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

MAX_POSTED_AGE_HOURS = 72


def is_entry_level(title, config):
    title_lower = title.lower()

    exclude_keywords = config.get("entry_level", {}).get("exclude", [])
    for kw in exclude_keywords:
        if kw.lower() in title_lower:
            return False

    years_match = re.search(r"\b(\d{1,2})\+?\s*(?:years?|yrs?)\b", title_lower)
    if years_match:
        years = int(years_match.group(1))
        if years >= 3:
            return False

    return True


def is_relevant_location(location, config):
    if not location:
        return True

    loc_lower = location.lower().strip()

    remote_keywords = ["remote", "worldwide", "global", "anywhere", "distributed"]
    for kw in remote_keywords:
        if kw in loc_lower:
            return True

    india_keywords = ["india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
                      "chennai", "pune", "kolkata", "ahmedabad", "jaipur", "noida",
                      "gurgaon", "gurugram", "coimbatore", "kochi", "indore"]
    for kw in india_keywords:
        if kw in loc_lower:
            return True

    return False


def is_recent(posted_date, max_hours=MAX_POSTED_AGE_HOURS):
    if not posted_date:
        return False
    try:
        posted = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - posted) <= timedelta(hours=max_hours)
    except (ValueError, TypeError):
        return False


def filter_jobs(jobs, config):
    filtered = []
    for job in jobs:
        title = job.get("title", "")
        location = job.get("location", "")

        if not title:
            continue

        if not is_entry_level(title, config):
            continue

        if not is_relevant_location(location, config):
            continue

        if not is_recent(job.get("posted_date", "")):
            continue

        filtered.append(job)

    logger.info(f"Filtered {len(jobs)} -> {len(filtered)} entry-level jobs (last {MAX_POSTED_AGE_HOURS}h)")
    return filtered


def sort_by_recency(jobs):
    def _parse_date(job):
        posted = job.get("posted_date", "")
        if not posted:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=timezone.utc)

    sorted_jobs = sorted(jobs, key=_parse_date, reverse=True)
    logger.info(f"Sorted {len(sorted_jobs)} jobs by recency (newest first)")
    return sorted_jobs


def deduplicate(jobs):
    seen = set()
    deduped = []

    for job in jobs:
        title = job.get("title", "").lower().strip()
        company = job.get("company", "").lower().strip()
        key = f"{title}|{company}"

        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    logger.info(f"Deduplicated {len(jobs)} -> {len(deduped)} jobs")
    return deduped
