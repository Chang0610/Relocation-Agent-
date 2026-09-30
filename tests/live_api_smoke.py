"""One-request live OpenAI smoke test through the English HTTP chat API.

This is intentionally opt-in because it sends one billable request. It uses
synthetic relocation details and never prints the API key or response body.
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from datetime import timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BACKEND = Path(__file__).resolve().parents[1] / "backend"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

import server  # noqa: E402
from time_utils import shanghai_today  # noqa: E402


def load_project_local_key():
    """Read only the configured key/model into process environment; never print them."""
    server.load_local_config()
    if os.getenv("OPENAI_API_KEY", "").strip():
        return
    local_file = PROJECT_ROOT / ".env.local"
    if not local_file.is_file():
        return
    for raw in local_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in ("OPENAI_API_KEY", "OPENAI_MODEL"):
            os.environ.setdefault(name, value.strip().strip('"').strip("'"))


class QuietHandler(server.Handler):
    def log_message(self, _format, *_args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-one-billable-call",
        action="store_true",
        help="Explicitly allow exactly one live model request.",
    )
    args = parser.parse_args()
    if not args.confirm_one_billable_call:
        parser.error("Pass --confirm-one-billable-call to allow the single billable API request.")

    load_project_local_key()
    if not os.getenv("OPENAI_API_KEY", "").strip():
        parser.error("OPENAI_API_KEY is not configured in the environment or local .env.local file.")

    start = shanghai_today() + timedelta(days=30)
    move = start - timedelta(days=2)
    message = (
        "Using my saved details, create a concise dated relocation plan now. "
        f"My office is near Zhangjiang Hi-Tech, I start work on {start.isoformat()}, "
        f"and I want to finish moving by {move.isoformat()}. Keep all tasks as a draft for my confirmation."
    )
    body = {
        "messages": [{"role": "user", "content": message}],
        "calendar": {"confirmed": [], "pending": None},
        "profile": {
            "company_location": "Zhangjiang Hi-Tech",
            "start_date": start.isoformat(),
            "move_deadline": move.isoformat(),
        },
    }

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    request = Request(
        f"http://127.0.0.1:{httpd.server_port}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=90) as response:
            result = json.load(response)
    except HTTPError as error:
        print(f"Live API smoke test failed with HTTP {error.code}; response body suppressed.", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Live API smoke test could not connect: {error.reason}", file=sys.stderr)
        return 1
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

    answer = result.get("answer")
    proposal = result.get("proposal")
    if not isinstance(answer, str) or not answer.strip():
        print("Live API returned an empty answer.", file=sys.stderr)
        return 1
    if re.search(r"[\u3400-\u9fff]", answer):
        print("Live API answer contains non-English CJK text; response body suppressed.", file=sys.stderr)
        return 1
    if not isinstance(proposal, dict) or not proposal.get("events"):
        print(
            f"Live API returned a response (mode={result.get('response_mode')}) but no plan proposal; response body suppressed.",
            file=sys.stderr,
        )
        return 1
    event_text = " ".join(
        str(event.get(field, ""))
        for event in proposal["events"]
        for field in ("title", "detail", "source_note")
    )
    if re.search(r"[\u3400-\u9fff]", event_text):
        print("Live API proposal contains non-English task text; response body suppressed.", file=sys.stderr)
        return 1
    if result.get("response_mode") != "B":
        print(f"Live API produced proposal in unexpected mode {result.get('response_mode')}.", file=sys.stderr)
        return 1

    elapsed = time.monotonic() - started
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    print(f"Live API smoke test passed: model={model}, mode=B, draft_events={len(proposal['events'])}, elapsed={elapsed:.1f}s.")
    print("Synthetic data only; one billable API request; response text and credentials were not logged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
