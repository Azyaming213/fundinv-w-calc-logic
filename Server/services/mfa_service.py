import io
import base64

import pyotp
import qrcode
from qrcode.image.pil import PilImage


def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def generate_otpauth_uri(secret: str, email: str, issuer: str = "FundInv") -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def generate_qr_code_base64(otpauth_uri: str) -> str:
    img = qrcode.make(otpauth_uri, image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)
