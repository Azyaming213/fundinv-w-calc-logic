from datetime import datetime, timezone

import yagmail
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Investor, InvestmentAccount, InvestmentTransaction, User
from config import settings


def _get_yag():
    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD:
        return None
    return yagmail.SMTP(user=settings.SMTP_EMAIL, password=settings.SMTP_PASSWORD)


def _send_portfolio_email(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    yag = _get_yag()
    if yag is None:
        return False
    try:
        yag.send(to=to_email, subject=subject, contents=html_body)
        return True
    except Exception:
        return False


def send_weekly_summaries():
    db: Session = SessionLocal()
    try:
        investors = db.query(Investor).filter(Investor.is_active == True).all()
        yag = _get_yag()
        if yag is None:
            return
        for investor in investors:
            try:
                accounts = (
                    db.query(InvestmentAccount)
                    .filter(InvestmentAccount.investor_id == investor.id, InvestmentAccount.deleted_at.is_(None))
                    .all()
                )
                total_value = sum(float(a.current_value) for a in accounts) + sum(float(v) for a in accounts for v in (a.manager_fund_balance or {}).values())
                html = f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1e293b">
                  <div style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:24px;border-radius:8px 8px 0 0">
                    <h1 style="color:#fff;margin:0;font-size:18px">Your Weekly Portfolio Summary</h1>
                  </div>
                  <div style="background:#fff;padding:24px;border:1px solid #e2e8f0">
                    <p style="margin:0 0 16px">Hi {investor.full_name},</p>
                    <p style="margin:0 0 16px;font-size:14px">Here's a quick snapshot of your portfolio this week:</p>
                    <div style="background:#f0f9ff;padding:16px;border-radius:8px;margin-bottom:16px">
                      <p style="margin:0;font-size:24px;font-weight:700;color:#2563eb">${total_value:,.2f}</p>
                      <p style="margin:4px 0 0;font-size:12px;color:#64748b">Total Portfolio Value across {len(accounts)} account(s)</p>
                    </div>
                    <p style="margin:0;font-size:13px;color:#64748b">
                      View your full portfolio on the <a href="{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/dashboard/investor" style="color:#2563eb">FundInv dashboard</a>.
                    </p>
                  </div>
                  <div style="padding:16px 24px;background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;text-align:center">
                    <p style="margin:0;font-size:11px;color:#94a3b8">FundInv Weekly Report — Do not reply</p>
                  </div>
                </div>
                """
                _send_portfolio_email(
                    to_email=investor.email,
                    to_name=investor.full_name,
                    subject="FundInv — Weekly Portfolio Summary",
                    html_body=html,
                )
            except Exception:
                continue
    finally:
        db.close()


def send_monthly_performance():
    db: Session = SessionLocal()
    try:
        investors = db.query(Investor).filter(Investor.is_active == True).all()
        for investor in investors:
            try:
                user = db.query(User).filter(User.email == investor.email).first()
                accounts = (
                    db.query(InvestmentAccount)
                    .filter(InvestmentAccount.investor_id == investor.id, InvestmentAccount.deleted_at.is_(None))
                    .all()
                )
                total_invested = sum(float(a.total_invested) for a in accounts)
                total_current = sum(float(a.current_value) for a in accounts)
                total_mfb = sum(float(v) for a in accounts for v in (a.manager_fund_balance or {}).values())
                pnl = total_current + total_mfb - total_invested
                pnl_pct = (pnl / total_invested * 100) if total_invested > 0 else 0

                account_rows = ""
                for a in accounts:
                    account_rows += f"""
                    <tr>
                      <td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">{a.account_name}</td>
                      <td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;text-align:right">${float(a.total_invested):,.2f}</td>
                      <td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;text-align:right">${float(a.current_value):,.2f}</td>
                      <td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;text-align:right">${sum(float(v) for v in (a.manager_fund_balance or {}).values()):,.2f}</td>
                    </tr>"""

                pnl_color = "#10b981" if pnl >= 0 else "#ef4444"
                html = f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1e293b">
                  <div style="background:linear-gradient(135deg,#7c3aed,#5b21b6);padding:24px;border-radius:8px 8px 0 0">
                    <h1 style="color:#fff;margin:0;font-size:18px">Monthly Performance Report</h1>
                  </div>
                  <div style="background:#fff;padding:24px;border:1px solid #e2e8f0">
                    <p style="margin:0 0 16px">Hi {investor.full_name},</p>
                    <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
                      <div style="flex:1;min-width:120px;background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0">
                        <p style="margin:0;font-size:10px;color:#64748b">Total Invested</p>
                        <p style="margin:4px 0 0;font-size:18px;font-weight:700">${total_invested:,.2f}</p>
                      </div>
                      <div style="flex:1;min-width:120px;background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0">
                        <p style="margin:0;font-size:10px;color:#64748b">Current Value</p>
                        <p style="margin:4px 0 0;font-size:18px;font-weight:700">${total_current + total_mfb:,.2f}</p>
                      </div>
                      <div style="flex:1;min-width:120px;background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0">
                        <p style="margin:0;font-size:10px;color:#64748b">P&L</p>
                        <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:{pnl_color}">${pnl:,.2f} ({pnl_pct:+.1f}%)</p>
                      </div>
                    </div>
                    <h2 style="font-size:13px;color:#475569;margin:0 0 8px">Account Breakdown</h2>
                    <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:16px">
                      <thead>
                        <tr style="background:#f1f5f9">
                          <th style="padding:6px 10px;text-align:left">Account</th>
                          <th style="padding:6px 10px;text-align:right">Invested</th>
                          <th style="padding:6px 10px;text-align:right">Value</th>
                          <th style="padding:6px 10px;text-align:right">Fund Balance</th>
                        </tr>
                      </thead>
                      <tbody>{account_rows if account_rows else '<tr><td colspan="4" style="padding:12px;text-align:center;color:#94a3b8">No accounts</td></tr>'}</tbody>
                    </table>
                  </div>
                  <div style="padding:16px 24px;background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;text-align:center">
                    <p style="margin:0;font-size:11px;color:#94a3b8">FundInv Monthly Report — Do not reply</p>
                  </div>
                </div>
                """
                _send_portfolio_email(
                    to_email=investor.email,
                    to_name=investor.full_name,
                    subject="FundInv — Monthly Performance Report",
                    html_body=html,
                )
            except Exception:
                continue
    finally:
        db.close()
