"""Cross-platform portfolio PDF generation using ReportLab."""

from datetime import datetime, timezone
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BLUE = colors.HexColor("#2563eb")
SLATE_900 = colors.HexColor("#1e293b")
SLATE_600 = colors.HexColor("#475569")
SLATE_500 = colors.HexColor("#64748b")
SLATE_400 = colors.HexColor("#94a3b8")
SLATE_200 = colors.HexColor("#e2e8f0")
SLATE_100 = colors.HexColor("#f1f5f9")
SLATE_50 = colors.HexColor("#f8fafc")
SKY_50 = colors.HexColor("#f0f9ff")
SKY_200 = colors.HexColor("#bae6fd")
GREEN = colors.HexColor("#10b981")
RED = colors.HexColor("#ef4444")


def _text(value) -> str:
    return escape(str(value if value not in (None, "") else "N/A"))


def _money(value) -> str:
    return f"${float(value or 0):,.2f}"


def _page_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(SLATE_200)
    canvas.line(document.leftMargin, 0.42 * inch, landscape(letter)[0] - document.rightMargin, 0.42 * inch)
    canvas.setFillColor(SLATE_400)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(document.leftMargin, 0.24 * inch, "FundInv - Confidential Portfolio Report")
    canvas.drawRightString(
        landscape(letter)[0] - document.rightMargin,
        0.24 * inch,
        f"Page {document.page}",
    )
    canvas.restoreState()


def build_portfolio_pdf(investor, accounts, transactions, generated_at: datetime | None = None) -> bytes:
    """Return a complete portfolio report as PDF bytes."""
    generated_at = generated_at or datetime.now(timezone.utc)
    output = BytesIO()
    page_width, _ = landscape(letter)
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.58 * inch,
        title="FundInv Portfolio Report",
        author="FundInv",
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FundInvTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=BLUE,
        alignment=0,
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "FundInvSubtitle",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=SLATE_500,
    )
    heading_style = ParagraphStyle(
        "FundInvHeading",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=SLATE_600,
        spaceBefore=5,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "FundInvBody",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=SLATE_900,
    )
    table_text = ParagraphStyle(
        "FundInvTableText",
        parent=body_style,
        fontSize=8,
        leading=10,
    )
    table_text_center = ParagraphStyle("FundInvTableCenter", parent=table_text, alignment=TA_CENTER)
    table_text_right = ParagraphStyle("FundInvTableRight", parent=table_text, alignment=TA_RIGHT)

    total_current_value = sum(float(account.current_value or 0) for account in accounts)
    total_fund_balance = sum(
        float(value or 0)
        for account in accounts
        for value in (account.manager_fund_balance or {}).values()
    )
    total_account_value = total_current_value + total_fund_balance

    story = [
        Paragraph("FundInv Portfolio Report", title_style),
        Paragraph(f"Generated: {generated_at.strftime('%B %d, %Y %H:%M UTC')}", subtitle_style),
        Spacer(1, 8),
        Paragraph("Investor", heading_style),
        Paragraph(f"<b>{_text(investor.full_name)}</b> - {_text(investor.email)}", body_style),
        Spacer(1, 7),
        Paragraph("Account Summary", heading_style),
    ]

    summary_data = [[
        Paragraph(f"<b>Total Value</b><br/>{_money(total_account_value)}", body_style),
        Paragraph(f"<b>Invested</b><br/>{_money(total_current_value)}", body_style),
        Paragraph(f"<b>Fund Balance</b><br/>{_money(total_fund_balance)}", body_style),
        Paragraph(f"<b>Accounts</b><br/>{len(accounts)}", body_style),
    ]]
    summary = Table(summary_data, colWidths=[2.45 * inch] * 4)
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), SKY_50),
        ("BACKGROUND", (1, 0), (-1, -1), SLATE_50),
        ("BOX", (0, 0), (0, 0), 0.75, SKY_200),
        ("BOX", (1, 0), (-1, -1), 0.75, SLATE_200),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, SLATE_200),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.extend([summary, Spacer(1, 10), Paragraph("Investment Accounts", heading_style)])

    account_data = [["Account", "Number", "Strategy", "Invested", "Value", "Fund Balance"]]
    for account in accounts:
        fund_balance = sum(float(value or 0) for value in (account.manager_fund_balance or {}).values())
        account_data.append([
            Paragraph(_text(account.account_name), table_text),
            Paragraph(_text(account.account_number), table_text),
            Paragraph(_text(account.investment_strategy), table_text),
            Paragraph(_money(account.total_invested), table_text_right),
            Paragraph(_money(account.current_value), table_text_right),
            Paragraph(_money(fund_balance), table_text_right),
        ])
    if len(account_data) == 1:
        account_data.append([Paragraph("No accounts", table_text_center), "", "", "", "", ""])

    account_table = Table(
        account_data,
        colWidths=[2.0 * inch, 1.4 * inch, 1.55 * inch, 1.45 * inch, 1.45 * inch, 1.65 * inch],
        repeatRows=1,
        hAlign="LEFT",
    )
    account_style = [
        ("BACKGROUND", (0, 0), (-1, 0), SLATE_100),
        ("TEXTCOLOR", (0, 0), (-1, 0), SLATE_600),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, SLATE_200),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if len(accounts) == 0:
        account_style.append(("SPAN", (0, 1), (-1, 1)))
        account_style.append(("ALIGN", (0, 1), (-1, 1), "CENTER"))
    account_table.setStyle(TableStyle(account_style))
    story.extend([account_table, Spacer(1, 10), Paragraph("Recent Transactions", heading_style)])

    transaction_data = [["Symbol", "Type", "Qty", "Price", "P&L", "Date"]]
    pnl_colors: list[tuple[int, colors.Color]] = []
    for row_index, transaction in enumerate(transactions, start=1):
        pnl_value = float(transaction.net_pnl or 0)
        pnl_colors.append((row_index, GREEN if pnl_value >= 0 else RED))
        transaction_data.append([
            Paragraph(_text(transaction.symbol), table_text),
            Paragraph(_text(transaction.trade_type), table_text_center),
            Paragraph(_text(transaction.volume), table_text_right),
            Paragraph(_money(transaction.price), table_text_right),
            Paragraph(_money(pnl_value), table_text_right),
            Paragraph(
                transaction.trade_time.strftime("%Y-%m-%d %H:%M") if transaction.trade_time else "N/A",
                table_text_right,
            ),
        ])
    if len(transaction_data) == 1:
        transaction_data.append([Paragraph("No transactions", table_text_center), "", "", "", "", ""])

    transaction_table = Table(
        transaction_data,
        colWidths=[1.5 * inch, 1.2 * inch, 1.0 * inch, 1.3 * inch, 1.3 * inch, 2.2 * inch],
        repeatRows=1,
        hAlign="LEFT",
    )
    transaction_style = [
        ("BACKGROUND", (0, 0), (-1, 0), SLATE_100),
        ("TEXTCOLOR", (0, 0), (-1, 0), SLATE_600),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, SLATE_200),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if len(transactions) == 0:
        transaction_style.append(("SPAN", (0, 1), (-1, 1)))
        transaction_style.append(("ALIGN", (0, 1), (-1, 1), "CENTER"))
    for row_index, color in pnl_colors:
        transaction_style.append(("TEXTCOLOR", (4, row_index), (4, row_index), color))
    transaction_table.setStyle(TableStyle(transaction_style))
    story.append(transaction_table)

    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return output.getvalue()
