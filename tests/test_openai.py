import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from server import openai_answer


class OpenAIAdapterTest(unittest.TestCase):
    def test_responses_request_and_text_extraction(self):
        model_data = {"answer": "First, confirm your start date.", "calendar_intent": "none", "operations": [], "profile_updates": [{"field": "company_location", "value": "Zhangjiang Hi-Tech"}]}
        response = {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": json.dumps(model_data)}]}]}
        captured = {}

        def fake_urlopen(request, timeout, context):
            captured["request"] = request
            captured["timeout"] = timeout
            captured["context"] = context
            return io.BytesIO(json.dumps(response).encode())

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "gpt-5.6-luna"}):
            with patch("urllib.request.urlopen", fake_urlopen):
                answer = openai_answer([{"role": "user", "content": "I am moving to Shanghai."}], {"policies": []}, {"confirmed": [], "pending": None}, {"destination_city": "Shanghai"})
        self.assertEqual(answer, model_data)
        self.assertEqual(captured["request"].full_url, "https://api.openai.com/v1/responses")
        body = json.loads(captured["request"].data)
        self.assertEqual(body["model"], "gpt-5.6-luna")
        self.assertIs(body["store"], False)
        self.assertEqual(body["input"][-1]["content"], "I am moving to Shanghai.")
        self.assertIn('"destination_city": "Shanghai"', body["input"][0]["content"])
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertIn("Respond in English only", body["instructions"])
        self.assertIn("preserve verification status", body["instructions"])
        self.assertIn("up to three essential questions", body["instructions"])
        self.assertIn("one to three items", body["instructions"])


if __name__ == "__main__":
    unittest.main()
