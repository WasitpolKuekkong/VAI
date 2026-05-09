from config.settings import load_settings
from pathlib import Path
from rvc.applio_stub import process_with_rvc

conf = load_settings()
# adjust this path if different
sample = Path(r"tts\output\reply_20260508_170322.mp3")
print('Using sample:', sample.resolve())
out = process_with_rvc(sample, conf)
print('Result:', out)
