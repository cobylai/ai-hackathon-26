"""The one llm/client.py change: sampling= merges over the preset for one call."""
import unittest
from unittest import mock

from llm import client, config


def fake_request(method, path, body=None):
    fake_request.body = body
    return {"choices": [{"message": {"content": '{"a": 1}'}}], "usage": {}}


class Sampling(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.object(client, "_request", side_effect=fake_request),
                  mock.patch.object(client, "loaded_model", return_value="m")):
            p.start()
            self.addCleanup(p.stop)

    def test_default_unchanged(self):
        client.chat([{"role": "user", "content": "hi"}], max_tokens=5)
        self.assertEqual(fake_request.body["temperature"], config.PRESETS["non_thinking"]["temperature"])

    def test_override(self):
        client.complete_json("hi", max_tokens=5, sampling={"temperature": 0.2})
        b = fake_request.body
        self.assertEqual(b["temperature"], 0.2)
        self.assertEqual(b["top_p"], config.PRESETS["non_thinking"]["top_p"])
        client.complete("hi", max_tokens=5, sampling={"temperature": 0.1})
        self.assertEqual(fake_request.body["temperature"], 0.1)


if __name__ == "__main__":
    unittest.main()
