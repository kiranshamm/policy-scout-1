"""
Celery Tasks — Background scan worker
"""

import logging
from datetime import datetime
from celery import Celery
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Scan, PolicyPage, ScanStatus, PolicyStatus
from crawler import crawl_website, fetch_page_details
from classifier import classify_link, build_compliance_results

import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

logger = logging.getLogger(__name__)


def get_db() -> Session:
    return SessionLocal()


@celery_app.task(bind=True, name="tasks.run_scan", max_retries=0)
def run_scan(self, scan_id: str):
    """
    Main background task: crawl → classify → store results.
    """
    db = get_db()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            logger.error(f"Scan {scan_id} not found")
            return

        # Mark as running
        scan.status = ScanStatus.running
        db.commit()

        # ── Step 1: Crawl the website ──────────────────────────────────────
        logger.info(f"[{scan_id}] Starting crawl: {scan.url}")
        crawl_result = crawl_website(scan.url)

        if crawl_result["error"]:
            scan.status = ScanStatus.failed
            scan.error_message = crawl_result["error"]
            db.commit()
            return

        scan.domain = crawl_result["domain"]
        scan.total_links_found = crawl_result["total"]
        db.commit()

        # ── Step 2: Classify all links ─────────────────────────────────────
        # Prioritize footer links (more likely to contain policy pages)
        all_links = crawl_result["footer_links"] + crawl_result["links"]

        # Deduplicate by URL
        seen_urls = set()
        unique_links = []
        for link in all_links:
            if link["url"] not in seen_urls:
                seen_urls.add(link["url"])
                unique_links.append(link)

        classified = []
        for link in unique_links:
            match = classify_link(url=link["url"], title=link.get("text", ""))

            # If URL-based match is low confidence, fetch page content for verification
            if match and match.confidence < 0.75:
                try:
                    details = fetch_page_details(link["url"])
                    if details["title"] or details["content"]:
                        match = classify_link(
                            url=link["url"],
                            title=details["title"],
                            content=details["content"]
                        )
                        link["title"] = details["title"]
                except Exception as e:
                    logger.warning(f"Content fetch failed for {link['url']}: {e}")

            if match:
                classified.append({
                    "category": match.category,
                    "url": link["url"],
                    "title": link.get("title") or link.get("text", ""),
                    "confidence": match.confidence,
                })

        # ── Step 3: Build compliance results ───────────────────────────────
        results, score = build_compliance_results(classified)

        # ── Step 4: Persist results ────────────────────────────────────────
        # Remove any existing pages for this scan
        db.query(PolicyPage).filter(PolicyPage.scan_id == scan_id).delete()

        for item in results:
            page = PolicyPage(
                scan_id=scan_id,
                category=item["category"],
                url=item["url"],
                title=item.get("title"),
                status=PolicyStatus.found if item["status"] == "found" else PolicyStatus.missing,
                confidence=item["confidence"],
            )
            db.add(page)

        scan.score = score
        scan.status = ScanStatus.completed
        scan.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"[{scan_id}] Completed. Score: {score}%")

    except Exception as e:
        logger.exception(f"[{scan_id}] Scan failed: {e}")
        try:
            scan = db.query(Scan).filter(Scan.id == scan_id).first()
            if scan:
                scan.status = ScanStatus.failed
                scan.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
