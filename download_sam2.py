"""Download official Meta SAM2.1 checkpoints with SHA256 verification.

Try Meta's public Hugging Face repositories using normal certificate checks.
Fall back to Meta's original download server through Windows curl. The optional
best-effort revocation option is opt-in and never disables TLS verification.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

# Meta's official Hugging Face files and published SHA256 checksums.
CHECKPOINTS = {
    "sam2.1_hiera_tiny.pt": (
        "facebook/sam2.1-hiera-tiny",
        "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"),
    "sam2.1_hiera_small.pt": (
        "facebook/sam2.1-hiera-small",
        "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38"),
    "sam2.1_hiera_base_plus.pt": (
        "facebook/sam2.1-hiera-base-plus",
        "a2345aede8715ab1d5d31b4a509fb160c5a4af1970f199d9054ccfb746c004c5"),
    "sam2.1_hiera_large.pt": (
        "facebook/sam2.1-hiera-large",
        "2647878d5dfa5098f2f8649825738a9345572bae2d4350a2468587ece47dd318"),
}
META_URL = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified(path: Path, digest: str) -> bool:
    return path.is_file() and path.stat().st_size > 1_000_000 and file_sha256(path) == digest


def download_model(name: str, folder: Path, reuse: Path | None = None,
                   offline_revocation: bool = False) -> Path:
    if name not in CHECKPOINTS:
        raise ValueError(f"Unknown SAM2.1 checkpoint: {name}")
    repo_id, digest = CHECKPOINTS[name]
    target = folder / name
    folder.mkdir(parents=True, exist_ok=True)
    if verified(target, digest):
        print(f"Already present (SHA256 verified): {target}", flush=True)
        return target
    if reuse is not None and verified(reuse / name, digest):
        print(f"Reusing official checkpoint (SHA256 verified): {reuse / name}", flush=True)
        return reuse / name
    if target.exists():
        print(f"Cached file failed SHA256 verification; re-downloading: {target}", flush=True)
        target.unlink()

    print(f"Downloading from Meta's public Hugging Face repository: {repo_id}/{name}", flush=True)
    try:
        from huggingface_hub import hf_hub_download
        saved = Path(hf_hub_download(repo_id=repo_id, filename=name, local_dir=str(folder)))
        if not verified(saved, digest):
            raise RuntimeError(f"Hugging Face checkpoint failed official SHA256 verification: {saved}")
        print(f"Download verified (SHA256): {saved}", flush=True)
        return saved
    except Exception as exc:
        print(f"Hugging Face route failed: {type(exc).__name__}: {exc}", flush=True)
        if verified(target, digest):
            return target
        if target.exists():
            target.unlink()

    curl = shutil.which("curl.exe")
    if not curl:
        raise RuntimeError("Hugging Face failed and Windows curl.exe is unavailable")
    partial = folder / (name + ".part")
    args = [curl, "--location", "--fail", "--retry", "2", "--connect-timeout", "30"]
    if offline_revocation:
        # Narrow opt-in for a trusted/approved network; not --insecure.
        args += ["--ssl-revoke-best-effort"]
    args += ["--continue-at", "-", "--output", str(partial), META_URL + name]
    print("Trying original Meta public-file server with certificate checks ...", flush=True)
    result = subprocess.run(args, check=False)
    if result.returncode:
        raise RuntimeError(
            f"Both official routes failed; curl exit {result.returncode}. "
            "If Windows reports CRYPT_E_NO_REVOCATION_CHECK, contact IT about "
            "certificate revocation endpoints or use an approved network. "
            "With institutional approval, -AllowOfflineRevocation enables curl's "
            "limited --ssl-revoke-best-effort behavior. Never use --insecure.")
    if not verified(partial, digest):
        raise RuntimeError(f"Checkpoint failed official SHA256 verification: {partial}")
    partial.replace(target)
    print(f"Download verified (SHA256): {target}", flush=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Download verified Meta SAM2.1 .pt checkpoints")
    parser.add_argument("--name", choices=tuple(CHECKPOINTS), required=True)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--reuse", type=Path)
    parser.add_argument("--allow-offline-revocation", action="store_true")
    args = parser.parse_args()
    try:
        download_model(args.name, args.folder, args.reuse, args.allow_offline_revocation)
    except Exception as exc:
        print(f"SAM2.1 checkpoint download failed: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
