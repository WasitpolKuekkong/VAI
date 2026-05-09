from __future__ import annotations

from pathlib import Path


def cleanup_old_files(output_dir: Path, max_files: int = 5) -> None:
    """Keep only the newest N files in the output directory, delete older ones."""
    if not output_dir.exists():
        return
    
    # Get all mp3/wav files sorted by modification time
    files = sorted(
        output_dir.glob("reply_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    # Delete files beyond the limit
    for old_file in files[max_files:]:
        try:
            old_file.unlink()
            print(f"Deleted old TTS file: {old_file.name}")
        except OSError as exc:
            print(f"Warning: Could not delete {old_file.name}: {exc}")
