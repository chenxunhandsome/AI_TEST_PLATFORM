from datetime import timedelta

from django.conf import settings
from django.test import SimpleTestCase


class JwtTokenLifetimeTests(SimpleTestCase):
    def test_jwt_tokens_expire_after_24_hours_and_refresh_rotates(self):
        jwt_settings = settings.SIMPLE_JWT

        self.assertEqual(jwt_settings['ACCESS_TOKEN_LIFETIME'], timedelta(hours=24))
        self.assertEqual(jwt_settings['REFRESH_TOKEN_LIFETIME'], timedelta(hours=24))
        self.assertTrue(jwt_settings['ROTATE_REFRESH_TOKENS'])
