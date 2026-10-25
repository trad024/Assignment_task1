"""Minimal, local-only web form for the customer inquiry assistant."""

from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
from urllib.parse import parse_qs

from assistant import reply_to


MAX_MESSAGE_LENGTH = 5000
logger = logging.getLogger("test_studio.web")


def render_page(message: str = "", error: str = "", history: list = ()) -> bytes:
    bubbles = "".join(
        f'<div class="msg user"><p>{escape(text)}</p></div>' if role == "user"
        else f'<div class="msg bot"><p>{escape(text)}</p></div>'
        for role, text in history
    )
    if error:
        bubbles += f'<div class="notice" role="alert">{escape(error)}</div>'

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Test Studio · Customer inquiry assistant</title>
  <style>
    :root {{ color-scheme: light; --plum: #4a2c4a; --pink: #fbe3ea; --line: #f0d6df; --ink: #2d2230; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; background: #fff6f9; color: var(--ink); font-family: "Segoe UI", system-ui, Arial, sans-serif; line-height: 1.5; }}
    .wrap {{ width: min(100% - 24px, 680px); margin: 0 auto; padding: 32px 0 40px; }}
    h1 {{ margin: 0; text-align: center; color: var(--plum); font-size: clamp(1.8rem, 6vw, 2.4rem); font-weight: 700; }}
    .tagline {{ margin: 6px 0 24px; text-align: center; color: #7a7280; }}
    .card {{ background: #fff; border: 1px solid var(--line); border-radius: 20px; box-shadow: 0 8px 28px rgb(74 44 74 / 8%); padding: 18px; }}
    .chat {{ display: flex; flex-direction: column; gap: 12px; min-height: 240px; max-height: 60vh; overflow-y: auto; padding: 4px 2px 14px; }}
    .msg {{ max-width: 82%; padding: 10px 14px; border-radius: 18px; overflow-wrap: anywhere; }}
    .msg p {{ margin: 0; white-space: pre-wrap; }}
    .msg.user {{ align-self: flex-end; background: var(--plum); color: #fff; border-bottom-right-radius: 6px; }}
    .msg.bot {{ align-self: flex-start; background: var(--pink); color: var(--ink); border-bottom-left-radius: 6px; }}
    .notice {{ align-self: stretch; padding: 10px 14px; border-radius: 12px; background: #fff0f0; color: #8a2f2f; font-size: .92rem; }}
    form {{ display: flex; gap: 10px; padding-top: 14px; border-top: 1px solid var(--line); }}
    input[type=text] {{ flex: 1; min-width: 0; padding: 12px 16px; border: 1px solid #e3cdd6; border-radius: 999px; font: inherit; color: var(--ink); background: #fffdfd; }}
    input[type=text]:focus {{ outline: 3px solid rgb(74 44 74 / 18%); border-color: var(--plum); }}
    button {{ padding: 12px 22px; border: 0; border-radius: 999px; background: var(--plum); color: #fff; font: inherit; font-weight: 600; cursor: pointer; }}
    button:hover {{ background: #351f35; }}
    button:focus-visible {{ outline: 3px solid #d9a5bb; outline-offset: 2px; }}
    .new {{ display: block; margin-top: 12px; text-align: center; color: var(--plum); font-size: .88rem; }}
  </style>
</head>
<body>
  <main class="wrap">
    <h1>Test Studio</h1>
    <p class="tagline">Specialist in professional hair removal and eyebrow shaping</p>
    <section class="card" aria-label="Customer inquiry chat">
      <div class="chat" aria-live="polite">{bubbles}</div>
      <form method="post" action="/">
        <input type="hidden" name="history" value="{escape(json.dumps(history))}">
        <input type="text" name="message" maxlength="{MAX_MESSAGE_LENGTH}" required autofocus autocomplete="off" aria-label="Customer message" placeholder="Type the customer's message…" value="{escape(message)}">
        <button type="submit">Send</button>
      </form>
      <a class="new" href="/">Start a new conversation</a>
    </section>
  </main>
</body>
</html>"""
    return document.encode("utf-8")


def parse_history(raw: str) -> list:
    """Display-only chat history carried in the form; never sent to the model."""
    try:
        items = json.loads(raw)
        history = [[r, t] for r, t in items if r in ("user", "bot") and isinstance(t, str)]
    except (ValueError, TypeError):
        return []
    while len(json.dumps(history)) > 20000:
        history = history[2:]
    return history


class InquiryHandler(BaseHTTPRequestHandler):
    def send_html(self, body: bytes, status: int = 200) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # A browser tab may close or reload while Groq is generating a reply.
            logger.debug("Browser disconnected before the response finished")

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_html(render_page(error="Page not found."), 404)
            return
        self.send_html(render_page())

    def do_POST(self) -> None:
        if self.path != "/":
            self.send_html(render_page(error="Page not found."), 404)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_html(render_page(error="Please submit a valid message."), 400)
            return
        if content_length <= 0 or content_length > MAX_MESSAGE_LENGTH * 12:
            self.send_html(render_page(error="Please enter a message under 5,000 characters."), 413)
            return
        form = parse_qs(self.rfile.read(content_length).decode("utf-8", errors="replace"), keep_blank_values=True)
        message = form.get("message", [""])[0].strip()
        history = parse_history(form.get("history", ["[]"])[0])
        if not message:
            self.send_html(render_page(error="Please enter a customer message.", history=history), 400)
            return
        if len(message) > MAX_MESSAGE_LENGTH:
            self.send_html(render_page(error="Please keep the message under 5,000 characters.", history=history), 413)
            return
        try:
            reply = reply_to(message)
        except Exception as error:
            if isinstance(error, RuntimeError) and str(error) == "GROQ_API_KEY is not set":
                notice = "Set GROQ_API_KEY in your environment to draft replies that need the assistant."
            else:
                notice = "The assistant could not prepare a reply just now. Please try again."
            self.send_html(render_page(message=message, error=notice, history=history), 503)
            return
        self.send_html(render_page(history=history + [["user", message], ["bot", reply]]))

    def log_message(self, format: str, *args: object) -> None:
        # Keep customer message contents out of the development server log.
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = HTTPServer(("127.0.0.1", int(os.getenv("PORT", "8000"))), InquiryHandler)
    print(f"Test Studio assistant running at http://{server.server_address[0]}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
