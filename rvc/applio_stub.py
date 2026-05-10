from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from config.settings import AppConfig
from utils.logger import logger


_APPLIO_WORKER_LOCK = threading.RLock()
_APPLIO_WORKER_PROCESS: subprocess.Popen[str] | None = None


def _find_applio_executable(applio_dir: Path) -> Optional[Path]:
    candidates = ["applio.exe", "applio.bat", "run.bat", "process.bat", "process.exe", "main.py"]
    for c in candidates:
        p = applio_dir / c
        if p.exists():
            return p
    return None


def _get_applio_python_exec(applio_dir: Path) -> Path:
    python_exec = applio_dir / "env" / "python.exe"
    if not python_exec.exists():
        python_exec = Path(sys.executable)
    return python_exec


def _build_infer_kwargs(input_audio: Path, out_path: Path, config: AppConfig) -> dict:
    workspace_root = Path(__file__).resolve().parents[1]
    local_models_dir = workspace_root / "rvc" / "models"

    pth_path_final = None
    index_path_final = None
    if getattr(config, "rvc_model_pth", "") and Path(config.rvc_model_pth).exists():
        pth_path_final = Path(config.rvc_model_pth)
    else:
        pths = list(local_models_dir.rglob("*.pth")) if local_models_dir.exists() else []
        if pths:
            pth_path_final = pths[0]

    if getattr(config, "rvc_model_index", "") and Path(config.rvc_model_index).exists():
        index_path_final = Path(config.rvc_model_index)
    else:
        idxs = list(local_models_dir.rglob("*.index")) if local_models_dir.exists() else []
        if idxs:
            index_path_final = idxs[0]

    return {
        "pitch": 0,
        "index_rate": getattr(config, "rvc_index_rate", 1.0),
        "volume_envelope": 1.0,
        "protect": 0.0,
        "f0_method": getattr(config, "rvc_f0_method", "rmvpe"),
        "input_path": str(input_audio.resolve()),
        "output_path": str(out_path.resolve()),
        "pth_path": str(pth_path_final) if pth_path_final is not None else (str(config.rvc_model_pth) if getattr(config, "rvc_model_pth", "") else ""),
        "index_path": str(index_path_final) if index_path_final is not None else (str(config.rvc_model_index) if getattr(config, "rvc_model_index", "") else ""),
        "split_audio": False,
        "f0_autotune": False,
        "f0_autotune_strength": 0.0,
        "proposed_pitch": False,
        "proposed_pitch_threshold": 0.0,
        "clean_audio": False,
        "clean_strength": 0.0,
        "export_format": "wav",
        "embedder_model": getattr(config, "rvc_embedder_model", "contentvec") or "contentvec",
        "embedder_model_custom": getattr(config, "rvc_embedder_custom", "") or None,
    }


def _worker_script() -> str:
    return (
        "import contextlib\n"
        "import json\n"
        "import sys\n"
        "from core import run_infer_script\n"
        "\n"
        "def main():\n"
        "    print('READY', flush=True)\n"
        "    for raw_line in sys.stdin:\n"
        "        raw_line = raw_line.strip()\n"
        "        if not raw_line:\n"
        "            continue\n"
        "        if raw_line == 'EXIT':\n"
        "            print('BYE', flush=True)\n"
        "            return\n"
        "        try:\n"
        "            kwargs = json.loads(raw_line)\n"
        "            with contextlib.redirect_stdout(sys.stderr), contextlib.redirect_stderr(sys.stderr):\n"
        "                run_infer_script(**kwargs)\n"
        "            print(json.dumps({'ok': True, 'output_path': kwargs.get('output_path', '')}), flush=True)\n"
        "        except Exception as exc:\n"
        "            print(json.dumps({'ok': False, 'error': str(exc)}), flush=True)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )


def prime_applio_worker(config: AppConfig) -> bool:
    applio_dir = Path(config.applio_path)
    with _APPLIO_WORKER_LOCK:
        global _APPLIO_WORKER_PROCESS
        if _APPLIO_WORKER_PROCESS and _APPLIO_WORKER_PROCESS.poll() is None:
            return True

        try:
            worker_path = applio_dir / "aivt_infer_worker.py"
            worker_path.write_text(_worker_script(), encoding="utf-8")
            python_exec = _get_applio_python_exec(applio_dir)
            cmd = [str(python_exec), str(worker_path)]
            logger.info(f"Starting Applio worker: {cmd}")
            process = subprocess.Popen(
                cmd,
                cwd=str(applio_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
            ready_line = process.stdout.readline().strip() if process.stdout else ""
            if ready_line != "READY":
                logger.warning(f"Applio worker did not report READY: {ready_line!r}")
                process.terminate()
                return False

            _APPLIO_WORKER_PROCESS = process
            return True
        except Exception as exc:
            logger.error(f"Failed to start Applio worker: {exc}")
            _APPLIO_WORKER_PROCESS = None
            return False


def _run_with_worker(kwargs: dict, config: AppConfig) -> tuple[bool, str]:
    with _APPLIO_WORKER_LOCK:
        global _APPLIO_WORKER_PROCESS
        if not _APPLIO_WORKER_PROCESS or _APPLIO_WORKER_PROCESS.poll() is not None:
            if not prime_applio_worker(config):
                return False, "Applio worker unavailable"

        assert _APPLIO_WORKER_PROCESS is not None
        if _APPLIO_WORKER_PROCESS.stdin is None or _APPLIO_WORKER_PROCESS.stdout is None:
            return False, "Applio worker pipes unavailable"

        _APPLIO_WORKER_PROCESS.stdin.write(json.dumps(kwargs) + "\n")
        _APPLIO_WORKER_PROCESS.stdin.flush()
        response_line = _APPLIO_WORKER_PROCESS.stdout.readline().strip()
        if not response_line:
            return False, "Applio worker returned no response"
        response = json.loads(response_line)
        return bool(response.get("ok")), str(response.get("error", ""))


def process_with_rvc(input_audio: Path, config: AppConfig) -> Path:
    """Run Applio on the input audio and return the processed path."""
    applio_dir = Path(config.applio_path)
    output_dir = config.rvc_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    out_name = input_audio.stem + "_rvc.wav"
    out_path = output_dir / out_name

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
            logger.warning("Applio did not produce expected output or returned non-zero code")
        except Exception as exc:
            logger.error(f"Applio invocation failed: {exc}")

    # Try persistent worker first to avoid repeated startup/import overhead.
    try:
        step_start = time.perf_counter()
        kwargs = _build_infer_kwargs(input_audio, out_path, config)
        ok, error = _run_with_worker(kwargs, config)
        logger.info(f"Applio worker wall time: {time.perf_counter() - step_start:.3f}s")
        if ok and out_path.exists():
            logger.info(f"Applio worker produced output: {out_path}")
            return out_path
        logger.warning(f"Applio worker did not produce expected output: {error or 'unknown error'}")
    except Exception as exc:
        logger.error(f"Applio worker invocation failed: {exc}")

    # Fallback: one-shot runner if worker is unavailable.
    try:
        step_start = time.perf_counter()
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
        logger.info(f"Applio runner script write time: {time.perf_counter() - step_start:.3f}s")

        kwargs = _build_infer_kwargs(input_audio, out_path, config)
        step_start = time.perf_counter()
        args_path.write_text(json.dumps(kwargs), encoding="utf-8")
        logger.info(f"Applio args write time: {time.perf_counter() - step_start:.3f}s")

        python_exec = _get_applio_python_exec(applio_dir)
        cmd = [str(python_exec), str(runner_path), str(args_path)]
        logger.info(f"Invoking Applio runner: {cmd}")
        step_start = time.perf_counter()
        completed = subprocess.run(cmd, cwd=str(applio_dir), timeout=config.applio_timeout)
        logger.info(f"Applio runner subprocess wall time: {time.perf_counter() - step_start:.3f}s")
        logger.info(f"Applio runner return code: {completed.returncode}")
        if completed.returncode == 0 and out_path.exists():
            logger.info(f"Applio runner produced output: {out_path}")
            try:
                runner_path.unlink()
                args_path.unlink()
            except Exception:
                pass
            return out_path
        logger.warning("Applio runner did not produce expected output or returned non-zero code")
    except Exception as exc:
        logger.error(f"Applio runner invocation failed: {exc}")

    try:
        shutil.copy2(str(input_audio), str(out_path))
        return out_path
    except Exception:
        return input_audio
