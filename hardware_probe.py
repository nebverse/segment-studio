"""Conservative Windows hardware detection for Segment Studio; stdlib only.

Driver floors are conservative NVIDIA CUDA 12.6 Update 3 (561.17) and
12.8 Update 1 (572.61) for Windows. Final torch GPU operations are also tested.
"""
from __future__ import annotations
import argparse
import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

DRIVERS = {'cu126': (561, 17), 'cu128': (572, 61)}
OPTIONS = ('auto', 'cpu', 'cu126', 'cu128')


def parse_gpus(text: str) -> list[dict]:
    found = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) != 4:
            continue
        name, driver, memory, compute = parts
        cap = re.search(r'\d+\.\d+', compute)
        mem = re.search(r'\d+(?:\.\d+)?', memory)
        found.append({'name': name, 'driver': driver,
                      'capability': cap.group() if cap else None,
                      'vram_gib': round(float(mem.group())/1024, 2) if mem else None})
    return found


def select_backend(gpu: dict | None, requested: str = 'auto') -> tuple[str, str]:
    if requested not in OPTIONS:
        raise ValueError(f'Unsupported backend: {requested}')
    if requested == 'cpu':
        return 'cpu', 'CPU selected explicitly'
    if not gpu:
        if requested != 'auto':
            raise ValueError('CUDA requested but no NVIDIA GPU detected by nvidia-smi')
        return 'cpu', 'No NVIDIA GPU detected'
    try:
        cap = float(gpu['capability'])
        driver = tuple(int(n) for n in re.findall(r'\d+', gpu['driver']))
    except (ValueError, TypeError, KeyError):
        cap, driver = 0, ()
    # cu126 targets Maxwell 5.x through Hopper 9.x; newer Blackwell needs cu128.
    suitable = {'cu128': cap >= 7.5, 'cu126': 5 <= cap < 10}
    choices = ('cu128', 'cu126') if requested == 'auto' else (requested,)
    for choice in choices:
        if suitable[choice] and driver >= DRIVERS[choice]:
            return choice, f"{gpu['name']}, compute {gpu['capability']}, driver {gpu['driver']}"
    if requested != 'auto':
        raise ValueError(f'{requested} needs a supported NVIDIA GPU/driver (Windows driver >= {DRIVERS[requested][0]}.{DRIVERS[requested][1]})')
    return 'cpu', 'No tested CUDA wheel matches detected driver and GPU architecture'


def system_ram_gib() -> float | None:
    if sys.platform != 'win32':
        return None
    class Mem(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                    ('total', ctypes.c_ulonglong), ('available', ctypes.c_ulonglong),
                    ('page_total', ctypes.c_ulonglong), ('page_free', ctypes.c_ulonglong),
                    ('virtual_total', ctypes.c_ulonglong), ('virtual_free', ctypes.c_ulonglong),
                    ('extended', ctypes.c_ulonglong)]
    value = Mem()
    value.length = ctypes.sizeof(value)
    return round(value.total/1024**3, 1) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)) else None


def detect(folder: Path) -> dict:
    gpus = []
    smi = shutil.which('nvidia-smi')
    if smi:
        try:
            output = subprocess.run([smi, '--query-gpu=name,driver_version,memory.total,compute_cap',
                                     '--format=csv,noheader,nounits'], check=True,
                                    text=True, capture_output=True, timeout=15)
            gpus = parse_gpus(output.stdout)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        free_disk = round(shutil.disk_usage(folder).free/1024**3, 1)
    except OSError:
        free_disk = None
    return {'os': platform.system(), 'architecture': platform.machine(),
            'python': platform.python_version(), 'python_64bit': sys.maxsize > 2**32,
            'gpus': gpus, 'ram_gib': system_ram_gib(), 'disk_free_gib': free_disk}


def plan(profile: dict, backend: str, with_sam3: bool) -> dict:
    if profile['os'] != 'Windows' or not profile['python_64bit']:
        raise ValueError('This installer needs 64-bit Windows and Python')
    gpu = (profile['gpus'] or [None])[0]  # App uses CUDA device 0.
    chosen, reason = select_backend(gpu, backend)
    warnings = []
    if chosen == 'cpu':
        warnings.append('SAM2 on CPU is slow; AMD/Intel GPU backends are not configured')
    vram = gpu.get('vram_gib') if gpu else None
    if chosen != 'cpu' and vram is not None and vram < 6:
        warnings.append('Low VRAM: try SAM2.1 Tiny first')
    if with_sam3:
        if chosen != 'cu128':
            raise ValueError('SAM3 Windows/Triton 3.6 requires the tested cu128 profile; update the NVIDIA driver or omit -WithSAM3')
        if vram is not None and vram < 12:
            warnings.append('SAM3 might run out of GPU memory (12+ GiB is preferable, not a hard minimum)')
    if profile['ram_gib'] is not None and profile['ram_gib'] < 16:
        warnings.append('Less than 16 GiB system RAM: possible memory pressure')
    if profile['disk_free_gib'] is not None and profile['disk_free_gib'] < (20 if with_sam3 else 10):
        warnings.append('Low disk space for PyTorch wheels, models, and temporary files')
    if len(profile['gpus']) > 1:
        warnings.append('Multiple GPUs detected: the application currently uses GPU 0')
    return {**profile, 'backend': chosen, 'reason': reason, 'warnings': warnings,
            'torch_index': f'https://download.pytorch.org/whl/{chosen}'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Select safe Segment Studio PyTorch backend')
    parser.add_argument('--backend', choices=OPTIONS, default='auto')
    parser.add_argument('--with-sam3', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = plan(detect(Path(__file__).resolve().parent), args.backend, args.with_sam3)
    except ValueError as exc:
        print('Hardware check failed:', exc, file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"Windows hardware: {result['os']} {result['architecture']}; Python {result['python']}")
    for index, gpu in enumerate(result['gpus']):
        print(f"GPU {index}: {gpu['name']} | driver {gpu['driver']} | compute {gpu['capability']} | VRAM {gpu['vram_gib']} GiB")
    print(f"System RAM: {result['ram_gib']} GiB | free disk: {result['disk_free_gib']} GiB")
    print(f"Selected PyTorch backend: {result['backend']} ({result['reason']})")
    for warning in result['warnings']:
        print('WARNING:', warning)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())