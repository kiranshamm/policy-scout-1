"""
FastAPI Application — PolicyScout Backend
"""

import uuid
import logging
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import io

from database import get_db, create_tables
from models import Scan, PolicyPage, ScanStatus, PolicyStatus
from schemas import ScanRequest, ScanOut, PolicyPageOut, ScanCreateResponse
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PolicyScout API",
    description="Website Compliance & Policy Discovery API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_tables()
    logger.info("Database tables created/verified.")


# ─── Routes ──────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "service": "PolicyScout API", "version": "1.0.0"}


@app.post("/scan", response_model=ScanCreateResponse, status_code=202)
def start_scan(request: ScanRequest, db: Session = Depends(get_db)):
    """
    Submit a URL for compliance scanning.
    Returns a scan_id to poll for results.
    """
    url = request.url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    scan_id = str(uuid.uuid4())
    scan = Scan(id=scan_id, url=url, status=ScanStatus.queued)
    db.add(scan)
    db.commit()

    # Dispatch background task via Celery
    try:
        from tasks import run_scan
        run_scan.delay(scan_id)
    except Exception as e:
        logger.error(f"Failed to dispatch Celery task: {e}")
        # Fallback: run scan inline (for testing without Redis)
        _run_scan_inline(scan_id)

    return ScanCreateResponse(
        scan_id=scan_id,
        status="queued",
        message="Scan started. Poll /scan/{scan_id} for results."
    )


def _run_scan_inline(scan_id: str):
    """Fallback synchronous scan when Celery is unavailable."""
    import threading
    from database import SessionLocal
    from crawler import crawl_website, fetch_page_details
    from classifier import classify_link, build_compliance_results

    def worker():
        db = SessionLocal()
        try:
            scan = db.query(Scan).filter(Scan.id == scan_id).first()
            if not scan:
                return
            scan.status = ScanStatus.running
            db.commit()

            crawl_result = crawl_website(scan.url)

            if crawl_result["error"]:
                scan.status = ScanStatus.failed
                scan.error_message = crawl_result["error"]
                db.commit()
                return

            scan.domain = crawl_result["domain"]
            scan.total_links_found = crawl_result["total"]
            db.commit()

            all_links = crawl_result["footer_links"] + crawl_result["links"]
            seen_urls = set()
            unique_links = []
            for link in all_links:
                if link["url"] not in seen_urls:
                    seen_urls.add(link["url"])
                    unique_links.append(link)

            classified = []
            for link in unique_links:
                match = classify_link(url=link["url"], title=link.get("text", ""))
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
                    except Exception:
                        pass

                if match:
                    classified.append({
                        "category": match.category,
                        "url": link["url"],
                        "title": link.get("title") or link.get("text", ""),
                        "confidence": match.confidence,
                    })

            results, score = build_compliance_results(classified)

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
            logger.info(f"[{scan_id}] Inline scan complete. Score: {score}%")

        except Exception as e:
            logger.exception(f"Inline scan failed: {e}")
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

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


@app.get("/scan/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    """Poll scan status and results."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    pages = db.query(PolicyPage).filter(PolicyPage.scan_id == scan_id).all()

    return ScanOut(
        scan_id=scan.id,
        url=scan.url,
        domain=scan.domain,
        status=scan.status.value,
        score=scan.score or 0.0,
        total_links_found=scan.total_links_found or 0,
        error_message=scan.error_message,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
        results=[
            PolicyPageOut(
                category=p.category,
                status=p.status.value,
                url=p.url,
                title=p.title,
                confidence=p.confidence or 0.0,
            )
            for p in pages
        ],
    )


@app.get("/report/{scan_id}")
def download_report(scan_id: str, db: Session = Depends(get_db)):
    """Download a PDF compliance audit report for a completed scan."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status != ScanStatus.completed:
        raise HTTPException(status_code=400, detail="Scan not yet completed")

    pages = db.query(PolicyPage).filter(PolicyPage.scan_id == scan_id).all()

    from report import generate_pdf_report
    results = [
        {
            "category": p.category,
            "status": p.status.value,
            "url": p.url,
            "title": p.title,
            "confidence": p.confidence or 0.0,
        }
        for p in pages
    ]

    pdf_bytes = generate_pdf_report(
        url=scan.url,
        domain=scan.domain or "",
        score=scan.score or 0.0,
        results=results,
        scan_date=scan.created_at,
        total_links=scan.total_links_found or 0,
    )

    filename = f"compliance-report-{scan.domain or 'scan'}-{scan_id[:8]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/scans", response_model=List[ScanOut])
def list_scans(limit: int = 20, db: Session = Depends(get_db)):
    """List recent scans."""
    scans = db.query(Scan).order_by(Scan.created_at.desc()).limit(limit).all()
    result = []
    for scan in scans:
        pages = db.query(PolicyPage).filter(PolicyPage.scan_id == scan.id).all()
        result.append(ScanOut(
            scan_id=scan.id,
            url=scan.url,
            domain=scan.domain,
            status=scan.status.value,
            score=scan.score or 0.0,
            total_links_found=scan.total_links_found or 0,
            error_message=scan.error_message,
            created_at=scan.created_at,
            completed_at=scan.completed_at,
            results=[
                PolicyPageOut(
                    category=p.category,
                    status=p.status.value,
                    url=p.url,
                    title=p.title,
                    confidence=p.confidence or 0.0,
                )
                for p in pages
            ],
        ))
    return result
