import unittest

import stripe

from routers.admin_routers import _stripe_object_dict


class StripePayloadTests(unittest.TestCase):
    def test_normalizes_stripe_object_for_webhook_handlers(self):
        value = stripe.checkout.Session.construct_from(
            {"id": "cs_test_acceptance", "amount_total": 12345, "currency": "usd"},
            "test-key",
        )

        self.assertEqual(
            _stripe_object_dict(value),
            {"id": "cs_test_acceptance", "amount_total": 12345, "currency": "usd"},
        )

    def test_accepts_plain_dictionary(self):
        self.assertEqual(_stripe_object_dict({"id": "evt_test"}), {"id": "evt_test"})

    def test_rejects_unknown_payload_type(self):
        with self.assertRaises(ValueError):
            _stripe_object_dict("not-an-event-object")


if __name__ == "__main__":
    unittest.main()
