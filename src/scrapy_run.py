import json
import logging
import os
import sys
import threading

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_settings():
    return {
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_TIMES": 2,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 429],
        "HTTPERROR_ALLOWED_CODES": [404, 429],
        "DOWNLOAD_TIMEOUT": 20,
        "LOG_LEVEL": "INFO",
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            "src.middlewares.RandomUserAgentMiddleware": 400,
        },
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "FEEDS": {},
        "CLOSESPIDER_TIMEOUT": 120,
    }


def _run_in_thread(queries, output_dir, result_container):
    try:
        from scrapy.crawler import CrawlerRunner
        from scrapy.utils.log import configure_logging
        from scrapy.utils.reactor import install_reactor
        from twisted.internet import defer, reactor as twisted_reactor

        from src.spiders.linkedin_search import LinkedInSearchSpider
        from src.spiders.linkedin_details import LinkedInDetailsSpider

        install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        configure_logging({"LOG_FORMAT": "%(levelname)s: %(message)s"})

        queries_json = json.dumps(queries)
        settings = _make_settings()

        runner = CrawlerRunner(settings=settings)

        @defer.inlineCallbacks
        def crawl():
            try:
                yield runner.crawl(
                    LinkedInSearchSpider,
                    queries_json=queries_json,
                    output_file="linkedin_search.json",
                )
                logger.info("LinkedIn search spider finished")
                yield runner.crawl(
                    LinkedInDetailsSpider,
                    search_results_file="linkedin_search.json",
                    output_file="linkedin_details.json",
                )
                logger.info("LinkedIn details spider finished")
            except Exception as e:
                logger.error("Spider error: %s", e)
            finally:
                twisted_reactor.stop()

        crawl()
        twisted_reactor.run()

        details_path = os.path.join(output_dir, "linkedin_details.json")
        if os.path.exists(details_path):
            with open(details_path, "r", encoding="utf-8") as f:
                result_container["jobs"] = json.load(f)
                return

        search_path = os.path.join(output_dir, "linkedin_search.json")
        if os.path.exists(search_path):
            with open(search_path, "r", encoding="utf-8") as f:
                result_container["jobs"] = json.load(f)
                return

        result_container["jobs"] = []

    except Exception as e:
        logger.error("LinkedIn scrape failed: %s", e)
        result_container["jobs"] = []


def run_spiders(queries, output_dir=None):
    if output_dir is None:
        output_dir = PROJECT_ROOT

    total_queries = sum(len(q.get("locations", ["remote"])) for q in queries)
    logger.info("Running LinkedIn spider (%d queries, ~%ds)...", total_queries, total_queries * 8)

    result_container = {"jobs": []}
    thread = threading.Thread(target=_run_in_thread, args=(queries, output_dir, result_container), daemon=True)
    thread.start()
    thread.join(timeout=180)

    if thread.is_alive():
        logger.warning("LinkedIn spider timed out after 180s, returning partial results")

    jobs = result_container.get("jobs", [])
    logger.info("LinkedIn: got %d jobs", len(jobs))
    return jobs
