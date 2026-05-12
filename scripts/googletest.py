from google import genai
import time

client = genai.Client(api_key="AIzaSyBf8D6dewtnXpW_9Dz4IYwPByQS41YRNN8")

max_attempts = 4
delay_seconds = 10

for attempt in range(1, max_attempts + 1):
	try:
		response = client.models.generate_content(
			model="gemini-2.5-flash",
			contents="สวัสดี คุณชื่ออะไร?",
		)
		print(response.text)
		break
	except Exception as exc:
		message = str(exc)
		is_rate_limited = "429" in message or "RESOURCE_EXHAUSTED" in message
		is_busy = "503" in message or "UNAVAILABLE" in message
		if (is_rate_limited or is_busy) and attempt < max_attempts:
			label = "rate-limited (429)" if is_rate_limited else "busy (503)"
			print(f"Gemini {label}, retrying in {delay_seconds}s... ({attempt}/{max_attempts})")
			time.sleep(delay_seconds)
			delay_seconds *= 2
			continue
		raise