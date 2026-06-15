import logging
import re

logger = logging.getLogger(__name__)


def is_entry_level(title, config):
    title_lower = title.lower()

    exclude_keywords = config.get("entry_level", {}).get("exclude", [])
    for kw in exclude_keywords:
        if kw.lower() in title_lower:
            return False

    include_keywords = config.get("entry_level", {}).get("include", [])
    for kw in include_keywords:
        if kw.lower() in title_lower:
            return True

    if re.search(r"\b(\d{1,2})\s*(?:years?|yrs?)\b", title_lower):
        match = re.search(r"\b(\d{1,2})\s*(?:years?|yrs?)\b", title_lower)
        years = int(match.group(1))
        if years <= 2:
            return True
        return False

    return False


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

        filtered.append(job)

    logger.info(f"Filtered {len(jobs)} -> {len(filtered)} entry-level jobs")
    return filtered


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
