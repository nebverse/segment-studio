"""Print local model/dependency diagnostics without running heavy inference."""
import platform
import sys
from sam_backends import sam2_checkpoint, sam3_checkpoint, sam3_python, SAM2_CONFIGS

print('Operating system:', platform.platform())
print('GUI Python:', sys.version.split()[0], sys.executable)
for name in SAM2_CONFIGS:
    path = sam2_checkpoint(name)
    state = f'FOUND ({path.stat().st_size / 1024**2:.1f} MiB)' if path.is_file() else 'MISSING'
    print(f'{name:16s}: {state} | {path}')
for name, path in [('SAM3 Python', sam3_python()), ('SAM3 checkpoint', sam3_checkpoint())]:
    print(name + ':', ('FOUND' if path.is_file() else 'MISSING'), '|', path)
for name in ('PIL', 'numpy', 'cv2', 'torch'):
    try:
        module = __import__(name)
        print(name, getattr(module, '__version__', 'OK'))
    except Exception as exc:
        print(name, 'UNAVAILABLE:', exc)
try:
    import torch
    print('CUDA available:', torch.cuda.is_available())
    if torch.cuda.is_available():
        print('GPU:', torch.cuda.get_device_name(0))
except ImportError:
    pass

# Optional hardware report from the Windows installer.
from pathlib import Path
import json
_report = Path(__file__).resolve().parent / '.local' / 'hardware.json'
if _report.exists():
    try:
        _plan = json.loads(_report.read_text(encoding='utf-8-sig'))
        print('Selected PyTorch backend:', _plan.get('backend'))
        for _warning in _plan.get('warnings', []):
            print('Hardware warning:', _warning)
    except (OSError, ValueError) as _exc:
        print('Hardware report could not be read:', _exc)
