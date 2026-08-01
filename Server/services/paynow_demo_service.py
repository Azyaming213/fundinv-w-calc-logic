"""Deterministic, non-monetary PayNow QR support for local demonstrations."""

import base64
from decimal import Decimal
from io import BytesIO
from urllib.parse import urlencode

import qrcode


def build_paynow_demo_payload(
    *, request_id: str, amount: Decimal, currency: str, fund_name: str,
    recipient_name: str, recipient_uen: str,
) -> str:
    """Build a clearly non-production QR payload with an amount locked by the server."""
    query = urlencode({
        "recipient": recipient_name,
        "uen": recipient_uen,
        "amount": f"{amount.quantize(Decimal('0.01')):.2f}",
        "currency": currency,
        "reference": request_id,
        "fund": fund_name,
        "demo": "true",
    })
    return f"paynow-demo://pay?{query}"


def paynow_qr_data_url(payload: str) -> str:
    """Render a compact QR image as a browser-ready data URL."""
    qr = qrcode.QRCode(version=None, box_size=5, border=3)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
