import os
import unittest
from unittest.mock import MagicMock, patch

from app.security import TOKEN_URL, get_token


class GetTokenTest(unittest.TestCase):
    def test_missing_env(self):
        with patch.dict(os.environ, {"API_CLIENT_SECRET": "secret"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "API_CLIENT_ID"):
                get_token()

    def test_request(self):
        env = {"API_CLIENT_ID": "my-id", "API_CLIENT_SECRET": "my-secret"}
        resp = MagicMock()
        resp.json.return_value = {"access_token": "abc123"}

        with patch.dict(os.environ, env, clear=True), patch(
            "app.security.requests.post", return_value=resp
        ) as post:
            self.assertEqual(get_token(), "abc123")

        self.assertEqual(post.call_args.args[0], TOKEN_URL)
        self.assertEqual(
            post.call_args.kwargs["data"],
            {
                "grant_type": "client_credentials",
                "client_id": "my-id",
                "client_secret": "my-secret",
            },
        )
        resp.raise_for_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
