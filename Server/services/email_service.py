import yagmail
from config import settings


def _get_yag():
    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD:
        raise RuntimeError("Email service not configured. Set SMTP_EMAIL and SMTP_PASSWORD.")
    return yagmail.SMTP(user=settings.SMTP_EMAIL, password=settings.SMTP_PASSWORD)


def send_invite_email(to_email: str, full_name: str, token: str, expires_at: str, role: str) -> bool:
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    register_url = f"{frontend_url}/register?token={token}"

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#1e293b">
      <div style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:32px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:22px">You're Invited to FundInv</h1>
        <p style="color:#bfdbfe;margin:6px 0 0;font-size:13px">Complete your registration to get started</p>
      </div>
      <div style="background:#fff;padding:32px;border:1px solid #e2e8f0;border-top:none">
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6">Hi {full_name},</p>
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6">
          You have been invited to join <strong>FundInv</strong> as a <strong>{role}</strong>.
          Click the button below to create your account.
        </p>
        <div style="text-align:center;margin:24px 0">
          <a href="{register_url}" style="display:inline-block;padding:14px 36px;background:#2563eb;color:#fff;text-decoration:none;border-radius:8px;font-size:15px;font-weight:600">
            Create Account
          </a>
        </div>
        <p style="margin:0;font-size:13px;color:#64748b">
          Or copy and paste this link into your browser:
        </p>
        <p style="margin:8px 0 0;font-size:12px;color:#94a3b8;word-break:break-all">
          {register_url}
        </p>
        <div style="margin-top:24px;padding-top:16px;border-top:1px solid #e2e8f0">
          <p style="margin:0;font-size:12px;color:#94a3b8">
            This invite expires on <strong>{expires_at}</strong>. If you believe this was sent in error, you can safely ignore this email.
          </p>
        </div>
      </div>
      <div style="padding:20px 24px;background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;text-align:center">
        <p style="margin:0;font-size:12px;color:#94a3b8">This email was sent by FundInv. Do not reply to this email.</p>
      </div>
    </div>
    """

    try:
        yag = _get_yag()
        yag.send(
            to=to_email,
            subject=f"FundInv — You've been invited as {role}",
            contents=html_body,
        )
        return True
    except Exception:
        return False


def send_fund_flow_approved_email(
    to_email: str,
    investor_name: str,
    flow_type: str,
    amount: float,
    request_id: str,
    account_name: str = None,
    checkout_url: str = None,
) -> bool:
    flow_label = "deposit" if flow_type == "deposit" else "withdrawal"
    amount_fmt = f"${amount:,.2f}"

    if flow_type == "deposit" and checkout_url:
        subject = f"FundInv — Deposit Approved — {request_id}"
        description = "Your deposit request has been approved. Click the button below to complete your payment."
        action_block = f"""
        <div style="text-align:center;margin:24px 0">
          <a href="{checkout_url}" style="display:inline-block;padding:14px 40px;background:#2563eb;color:#fff;text-decoration:none;border-radius:8px;font-size:16px;font-weight:700">
            Pay ${amount:,.2f}
          </a>
          <p style="margin:12px 0 0;font-size:12px;color:#94a3b8">
            Secure payment via Stripe (card / PayNow)
          </p>
        </div>
        """
        next_step = "Your wallet will be credited automatically once payment is confirmed."
    elif flow_type == "deposit":
        subject = f"FundInv — Deposit Approved — {request_id}"
        description = "Your deposit request has been approved and is being processed."
        action_block = ""
        next_step = "The operations team will contact you with payment details."
    elif flow_type == "withdrawal" and checkout_url:
        subject = f"FundInv — Withdrawal Setup Required — {request_id}"
        description = "Your withdrawal request was approved. Complete the secure payout setup so we can send your funds."
        action_block = f"""
        <div style="text-align:center;margin:24px 0">
          <a href="{checkout_url}" style="display:inline-block;padding:14px 40px;background:#2563eb;color:#fff;text-decoration:none;border-radius:8px;font-size:16px;font-weight:700">
            Set Up Withdrawal Account
          </a>
        </div>
        """
        next_step = "Your withdrawal will be sent after payout setup is complete."
    else:
        subject = f"FundInv — Withdrawal Approved — {request_id}"
        description = "Your withdrawal request has been approved and is being processed."
        action_block = ""
        next_step = "You will be notified once the transfer is complete."

    account_line = f"<p style=\"margin:4px 0;font-size:14px;color:#475569\">Account: <strong>{account_name}</strong></p>" if account_name else ""

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#1e293b">
      <div style="background:linear-gradient(135deg,#059669,#047857);padding:32px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:22px">{flow_label.title()} Approved</h1>
        <p style="color:#a7f3d0;margin:6px 0 0;font-size:13px">Request ID: {request_id}</p>
      </div>
      <div style="background:#fff;padding:32px;border:1px solid #e2e8f0;border-top:none">
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6">Hi {investor_name},</p>
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6">{description}</p>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:16px 0">
          <p style="margin:0;font-size:14px;color:#64748b">Amount</p>
          <p style="margin:4px 0 0;font-size:24px;font-weight:700;color:#1e293b">{amount_fmt}</p>
          <p style="margin:4px 0;font-size:14px;color:#475569">Request ID: <strong>{request_id}</strong></p>
          {account_line}
        </div>
        {action_block}
        <p style="margin:16px 0 0;font-size:14px;color:#475569;line-height:1.6">{next_step}</p>
      </div>
      <div style="padding:20px 24px;background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;text-align:center">
        <p style="margin:0;font-size:12px;color:#94a3b8">This email was sent by FundInv. Do not reply to this email.</p>
      </div>
    </div>
    """

    try:
        yag = _get_yag()
        yag.send(to=to_email, subject=subject, contents=html_body)
        return True
    except Exception:
        return False


def send_fund_flow_completed_email(
    to_email: str,
    investor_name: str,
    flow_type: str,
    amount: float,
    request_id: str,
) -> bool:
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    wallet_url = f"{frontend_url}/dashboard/investor/wallet"
    flow_label = "deposit" if flow_type == "deposit" else "withdrawal"
    amount_fmt = f"${amount:,.2f}"

    if flow_type == "deposit":
        result = "Funds have been received and credited to your wallet."
    else:
        result = "Funds have been sent to your account."

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#1e293b">
      <div style="background:linear-gradient(135deg,#059669,#047857);padding:32px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:22px">{flow_label.title()} Completed</h1>
        <p style="color:#a7f3d0;margin:6px 0 0;font-size:13px">Request ID: {request_id}</p>
      </div>
      <div style="background:#fff;padding:32px;border:1px solid #e2e8f0;border-top:none">
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6">Hi {investor_name},</p>
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6">Your {flow_label} request has been completed.</p>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:16px 0">
          <p style="margin:0;font-size:14px;color:#166534">{result}</p>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:16px 0">
          <p style="margin:0;font-size:14px;color:#64748b">Amount</p>
          <p style="margin:4px 0 0;font-size:24px;font-weight:700;color:#1e293b">{amount_fmt}</p>
          <p style="margin:4px 0 0;font-size:14px;color:#475569">Request ID: <strong>{request_id}</strong></p>
        </div>
        <div style="text-align:center;margin:24px 0">
          <a href="{wallet_url}" style="display:inline-block;padding:12px 32px;background:#059669;color:#fff;text-decoration:none;border-radius:8px;font-size:15px;font-weight:600">
            View Wallet
          </a>
        </div>
      </div>
      <div style="padding:20px 24px;background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;text-align:center">
        <p style="margin:0;font-size:12px;color:#94a3b8">This email was sent by FundInv. Do not reply to this email.</p>
      </div>
    </div>
    """

    try:
        yag = _get_yag()
        yag.send(to=to_email, subject=f"FundInv — {flow_label.title()} Completed — {request_id}", contents=html_body)
        return True
    except Exception:
        return False


def send_fund_flow_rejected_email(
    to_email: str,
    investor_name: str,
    flow_type: str,
    amount: float,
    request_id: str,
    notes: str = None,
) -> bool:
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    wallet_url = f"{frontend_url}/dashboard/investor/wallet"
    flow_label = "deposit" if flow_type == "deposit" else "withdrawal"
    amount_fmt = f"${amount:,.2f}"

    reason_block = ""
    if notes:
        reason_block = f"""
        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;margin:16px 0">
          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#991b1b">Reason</p>
          <p style="margin:0;font-size:14px;color:#7f1d1d;line-height:1.6">{notes}</p>
        </div>
        """

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#1e293b">
      <div style="background:linear-gradient(135deg,#dc2626,#b91c1c);padding:32px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:22px">{flow_label.title()} Rejected</h1>
        <p style="color:#fecaca;margin:6px 0 0;font-size:13px">Request ID: {request_id}</p>
      </div>
      <div style="background:#fff;padding:32px;border:1px solid #e2e8f0;border-top:none">
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6">Hi {investor_name},</p>
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6">Your {flow_label} request has been rejected.</p>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:16px 0">
          <p style="margin:0;font-size:14px;color:#64748b">Amount</p>
          <p style="margin:4px 0 0;font-size:24px;font-weight:700;color:#1e293b">{amount_fmt}</p>
          <p style="margin:4px 0 0;font-size:14px;color:#475569">Request ID: <strong>{request_id}</strong></p>
        </div>
        {reason_block}
        <p style="margin:16px 0 0;font-size:14px;color:#475569;line-height:1.6">
          If you have questions, please contact the operations team. You may submit a new request at any time.
        </p>
        <div style="text-align:center;margin:24px 0">
          <a href="{wallet_url}" style="display:inline-block;padding:12px 32px;background:#dc2626;color:#fff;text-decoration:none;border-radius:8px;font-size:15px;font-weight:600">
            View Wallet
          </a>
        </div>
      </div>
      <div style="padding:20px 24px;background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;text-align:center">
        <p style="margin:0;font-size:12px;color:#94a3b8">This email was sent by FundInv. Do not reply to this email.</p>
      </div>
    </div>
    """

    try:
        yag = _get_yag()
        yag.send(to=to_email, subject=f"FundInv — {flow_label.title()} Rejected — {request_id}", contents=html_body)
        return True
    except Exception:
        return False
