from decimal import Decimal
import unittest

from services.paynow_demo_service import build_paynow_demo_payload, paynow_qr_data_url


class PayNowDemoTests(unittest.TestCase):
    def test_payload_and_qr_lock_requested_amount(self):
        payload = build_paynow_demo_payload(
            request_id="REQ-123",
            amount=Decimal("123.456"),
            currency="USD",
            fund_name="Balanced Fund",
            recipient_name="FundInv Demo",
            recipient_uen="T00FUNDINV",
        )

        self.assertIn("amount=123.46", payload)
        self.assertIn("reference=REQ-123", payload)
        self.assertIn("demo=true", payload)
        self.assertTrue(paynow_qr_data_url(payload).startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
