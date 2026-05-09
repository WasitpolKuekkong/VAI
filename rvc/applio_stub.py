from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from config.settings import AppConfig
from utils.logger import logger


def _find_applio_executable(applio_dir: Path) -> Optional[Path]:
    # Look for common entrypoints
    candidates = ["applio.exe", "applio.bat", "run.bat", "process.bat", "process.exe", "main.py"]
    for c in candidates:
        p = applio_dir / c
        if p.exists():
            return p
    return None


def process_with_rvc(input_audio: Path, config: AppConfig) -> Path:
    """Attempt to run Applio on the input audio and return processed path.

    Strategy:
    1. Try to invoke a detected executable/script in the Applio folder with
       arguments (input_path, output_path).
    2. If no executable or invocation fails, write a small runner script and
       args JSON into the Applio folder and call `core.run_infer_script` via
       Applio's Python environment.
    3. If all else fails, copy the input to rvc output folder (fallback).
    """
    applio_dir = Path(config.applio_path)
    output_dir = config.rvc_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Force output to WAV (Applio respects export_format + output extension)
    out_name = input_audio.stem + "_rvc.wav"
    out_path = output_dir / out_name

    # 1) Try direct executable invocation
    exe = _find_applio_executable(applio_dir)
    if exe:
        try:
            if exe.suffix == ".py":
                cmd = [sys.executable, str(exe), str(input_audio), str(out_path)]
            else:
                cmd = [str(exe), str(input_audio), str(out_path)]
            logger.info(f"Invoking Applio: {cmd} (cwd={applio_dir})")
            completed = subprocess.run(cmd, cwd=str(applio_dir), timeout=config.applio_timeout)
            logger.info(f"Applio return code: {completed.returncode}")
            if completed.returncode == 0 and out_path.exists():
                logger.info(f"Applio produced output: {out_path}")
                return out_path
            else:
                logger.warning("Applio did not produce expected output or returned non-zero code")
        except Exception as exc:
            logger.error(f"Applio invocation failed: {exc}")

    # 2) Try runner that calls core.run_infer_script inside Applio environment
    try:
        runner_path = applio_dir / "aivt_infer_runner.py"
        args_path = applio_dir / "aivt_infer_args.json"

        runner_code = (
            "import json\n"
            "import sys\n"
            "from core import run_infer_script\n"
            "\n"
            "def main(args_file):\n"
            "    with open(args_file, 'r', encoding='utf-8') as f:\n"
            "        kwargs = json.load(f)\n"
            "    run_infer_script(**kwargs)\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    main(sys.argv[1])\n"
        )

        runner_path.write_text(runner_code, encoding="utf-8")

        # Determine model paths: prefer project-local models under rvc/models if present
        workspace_root = Path(__file__).resolve().parents[1]
        local_models_dir = workspace_root / "rvc" / "models"
        # find any .pth / .index in local models if config does not point to an existing file
        pth_path_final = None
        index_path_final = None
        if getattr(config, 'rvc_model_pth', '') and Path(config.rvc_model_pth).exists():
            pth_path_final = Path(config.rvc_model_pth)
        else:
            pths = list(local_models_dir.rglob('*.pth')) if local_models_dir.exists() else []
            if pths:
                pth_path_final = pths[0]

        if getattr(config, 'rvc_model_index', '') and Path(config.rvc_model_index).exists():
            index_path_final = Path(config.rvc_model_index)
        else:
            idxs = list(local_models_dir.rglob('*.index')) if local_models_dir.exists() else []
            if idxs:
                index_path_final = idxs[0]

        # Minimal kwargs for run_infer_script; adjust these based on your models/presets
        kwargs = {
            "pitch": 0,
            "index_rate": 1.0,
            "volume_envelope": 1.0,
            "protect": 0.0,
            "f0_method": getattr(config, 'rvc_f0_method', 'rmvpe'),
            "input_path": str(input_audio.resolve()),
            "output_path": str(out_path.resolve()),
            "pth_path": str(pth_path_final) if pth_path_final is not None else (str(config.rvc_model_pth) if getattr(config, 'rvc_model_pth', '') else ""),
            "index_path": str(index_path_final) if index_path_final is not None else (str(config.rvc_model_index) if getattr(config, 'rvc_model_index', '') else ""),
            "split_audio": False,
            "f0_autotune": False,
            "f0_autotune_strength": 0.0,
            "proposed_pitch": False,
            "proposed_pitch_threshold": 0.0,
            "clean_audio": False,
            "clean_strength": 0.0,
            "export_format": "wav",
            "embedder_model": getattr(config, 'rvc_embedder_model', 'contentvec') or 'contentvec',
            "embedder_model_custom": getattr(config, 'rvc_embedder_custom', '') or None,
        }

        args_path.write_text(json.dumps(kwargs), encoding="utf-8")
        logger.info(f"Wrote Applio args: {json.dumps(kwargs)}")

        # Prefer Applio's bundled python environment if available
        python_exec = applio_dir / "env" / "python.exe"
        if not python_exec.exists():
            python_exec = Path(sys.executable)

        cmd = [str(python_exec), str(runner_path), str(args_path)]
        logger.info(f"Invoking Applio runner: {cmd}")
        completed = subprocess.run(cmd, cwd=str(applio_dir), timeout=config.applio_timeout)
        logger.info(f"Applio runner return code: {completed.returncode}")
        if completed.returncode == 0 and out_path.exists():
            logger.info(f"Applio runner produced output: {out_path}")
            try:
                runner_path.unlink()
                args_path.unlink()
            except Exception:
                pass
            return out_path
        else:
            logger.warning("Applio runner did not produce expected output or returned non-zero code")
    except Exception as exc:
        logger.error(f"Applio runner invocation failed: {exc}")

    # 3) Fallback: copy input to output so pipeline continues
    try:
        shutil.copy2(str(input_audio), str(out_path))
        return out_path
    except Exception:
        return input_audio
