"""
PDF Report Generator using ReportLab
"""

import io
from datetime import datetime
from typing import List, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# Color palette
PRIMARY = colors.HexColor("#6366f1")       # Indigo
SUCCESS = colors.HexColor("#22c55e")       # Green
DANGER = colors.HexColor("#ef4444")        # Red
BG_LIGHT = colors.HexColor("#f8fafc")      # Light bg
BORDER = colors.HexColor("#e2e8f0")        # Border
TEXT_DARK = colors.HexColor("#0f172a")     # Dark text
TEXT_MUTED = colors.HexColor("#64748b")    # Muted text
SCORE_HIGH = colors.HexColor("#22c55e")
SCORE_MID = colors.HexColor("#f59e0b")
SCORE_LOW = colors.HexColor("#ef4444")


def score_color(score: float):
    if score >= 75:
        return SCORE_HIGH
    elif score >= 50:
        return SCORE_MID
    return SCORE_LOW


def generate_pdf_report(
    url: str,
    domain: str,
    score: float,
    results: List[Dict],
    scan_date: datetime,
    total_links: int,
) -> bytes:
    """
    Generate a PDF compliance audit report.
    Returns bytes of the PDF file.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "Title",
        fontSize=24,
        fontName="Helvetica-Bold",
        textColor=PRIMARY,
        spaceAfter=6,
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontSize=12,
        fontName="Helvetica",
        textColor=TEXT_MUTED,
        spaceAfter=4,
    )
    section_style = ParagraphStyle(
        "Section",
        fontSize=14,
        fontName="Helvetica-Bold",
        textColor=TEXT_DARK,
        spaceBefore=16,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "Body",
        fontSize=10,
        fontName="Helvetica",
        textColor=TEXT_DARK,
        spaceAfter=4,
        leading=16,
    )
    muted_style = ParagraphStyle(
        "Muted",
        fontSize=9,
        fontName="Helvetica",
        textColor=TEXT_MUTED,
    )
    url_style = ParagraphStyle(
        "URL",
        fontSize=9,
        fontName="Helvetica",
        textColor=PRIMARY,
        leading=13,
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("PolicyScout", title_style))
    story.append(Paragraph("Compliance Audit Report", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=12))

    # Scan info table
    info_data = [
        ["Website", url],
        ["Domain", domain or "N/A"],
        ["Scan Date", scan_date.strftime("%d %B %Y, %H:%M UTC")],
        ["Links Analysed", str(total_links)],
        ["Report Generated", datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")],
    ]
    info_table = Table(info_data, colWidths=[4 * cm, 13 * cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), TEXT_MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT_DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BG_LIGHT, colors.white]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDER),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # ── Compliance Score ──────────────────────────────────────────────────────
    story.append(Paragraph("Compliance Score", section_style))

    found_count = sum(1 for r in results if r["status"] == "found")
    total_count = len(results)
    sc = score_color(score)

    score_data = [
        [
            Paragraph(f'<font color="#{sc.hexval()[1:]}"><b>{score:.0f}%</b></font>', ParagraphStyle("big", fontSize=36, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(
                f"<b>{found_count} of {total_count}</b> compliance pages found.<br/><br/>"
                + ("✓ Your site has strong compliance coverage." if score >= 75 else
                   "⚠ Your site is missing some important compliance pages." if score >= 50 else
                   "✗ Your site has significant compliance gaps."),
                body_style
            )
        ]
    ]
    score_table = Table(score_data, colWidths=[5 * cm, 12 * cm])
    score_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (0, 0), BG_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 20))

    # ── Compliance Results Table ──────────────────────────────────────────────
    story.append(Paragraph("Compliance Pages Audit", section_style))

    table_header = ["Policy Page", "Status", "URL", "Confidence"]
    table_data = [table_header]

    for r in results:
        status_text = "✓  Found" if r["status"] == "found" else "✗  Missing"
        url_text = r.get("url") or "—"
        confidence = f"{r.get('confidence', 0) * 100:.0f}%" if r["status"] == "found" else "—"

        table_data.append([
            Paragraph(r["category"], body_style),
            status_text,
            Paragraph(url_text[:80], url_style),
            confidence,
        ])

    col_widths = [4.5 * cm, 3 * cm, 7.5 * cm, 2 * cm]
    results_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    row_colors = []
    for i, row in enumerate(results):
        bg = colors.white if i % 2 == 0 else BG_LIGHT
        row_colors.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))
        if row["status"] == "found":
            row_colors.append(("TEXTCOLOR", (1, i + 1), (1, i + 1), SUCCESS))
        else:
            row_colors.append(("TEXTCOLOR", (1, i + 1), (1, i + 1), DANGER))

    results_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        *row_colors,
    ]))
    story.append(results_table)
    story.append(Spacer(1, 20))

    # ── Missing Policies Section ──────────────────────────────────────────────
    missing = [r for r in results if r["status"] == "missing"]
    if missing:
        story.append(Paragraph("Missing Compliance Pages", section_style))
        story.append(Paragraph(
            "The following pages were not detected on your website. "
            "Missing compliance pages may expose your business to legal and regulatory risk.",
            body_style
        ))
        story.append(Spacer(1, 8))
        for item in missing:
            story.append(Paragraph(
                f"✗  <b>{item['category']}</b> — Not found on your website",
                ParagraphStyle("missing", fontSize=10, fontName="Helvetica", textColor=DANGER, spaceAfter=4)
            ))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Generated by PolicyScout · Automated Compliance Discovery Platform · policyscout.io",
        muted_style
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
