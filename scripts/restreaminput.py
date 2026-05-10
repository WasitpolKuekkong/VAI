import requests
import webbrowser
import asyncio
import websockets
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import secrets
from config.settings import load_settings

config = load_settings()
CLIENT_ID = config.restream_client_id
CLIENT_SECRET = config.restream_client_secret
REDIRECT_URI = config.restream_redirect_uri
STATE = secrets.token_hex(16)

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("Missing RESTREAM_CLIENT_ID or RESTREAM_CLIENT_SECRET in .env")

access_token = None

# ====== STEP 1: รับ Token ======

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global access_token
        params = parse_qs(urlparse(self.path).query)
        code = params.get("code", [None])[0]

        if code:
            res = requests.post("https://api.restream.io/oauth/token", data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            })
            data = res.json()
            access_token = data.get("access_token")
            print(f"\n✅ Access Token ได้แล้ว!")

        self.send_response(200)
        self.end_headers()
        self.wfile.write("Done! กลับไปดู terminal ได้เลย".encode("utf-8"))

    def log_message(self, format, *args):
        pass

auth_url = (
    f"https://api.restream.io/login"
    f"?response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&state={STATE}"
)

print("เปิด browser...")
webbrowser.open(auth_url)
print("รอ login...")
HTTPServer(("localhost", 8080), CallbackHandler).handle_request()

# ====== STEP 2: อ่าน Chat ======

async def read_chat():
    URL = f"wss://chat.api.restream.io/ws?accessToken={access_token}"
    async with websockets.connect(URL) as ws:
        print("✅ เชื่อมต่อ chat สำเร็จ รอข้อความ...\n")
        async for message in ws:
            data = json.loads(message)
            action = data.get("action")

            if action == "heartbeat":
                continue

            if action == "event":
                payload = data.get("payload", {})
                event_payload = payload.get("eventPayload", {})  # ✅ แก้ตรงนี้
                author = event_payload.get("author", {}).get("displayName", "Unknown")
                text = event_payload.get("text", "")

                if text:
                    print(f"💬 {author}: {text}")

asyncio.run(read_chat())