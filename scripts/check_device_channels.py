import sounddevice as sd
from typing import Any, cast

device_id = 13
info = cast(dict[str, Any], sd.query_devices(device_id))
print(f"Device {device_id}:")
print(f"  Name: {info['name']}")
print(f"  Max output channels: {info['max_output_channels']}")

# Try to get supported channel counts
try:
    for channels in [1, 2, 4, 6, 8]:
        try:
            # Create stream to test
            stream = sd.OutputStream(device=device_id, channels=channels, samplerate=22050)
            print(f"  ✓ Supports {channels} channels")
            stream.close()
        except Exception as e:
            print(f"  ✗ {channels} channels: {str(e)[:50]}")
except Exception as e:
    print(f"Error testing channels: {e}")
