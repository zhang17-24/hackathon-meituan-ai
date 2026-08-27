#!/usr/bin/env python3
"""串行断点续传重试下载失败的美甲图（每次运行尽量多下，可反复运行）。

用法：cd backend && uv run python scripts/retry_download_commons.py [--rounds 3]
"""
import argparse
import json
import ssl
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "data" / "styles" / "commons"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _download(url: str, dest: Path) -> None:
    context = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, context=context, timeout=30) as resp:
        dest.write_bytes(resp.read())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    manifest_path = OUT_DIR / "bulk_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for round_no in range(1, args.rounds + 1):
        pending = [
            r for r in manifest["images"]
            if not r.get("downloaded") and not r.get("skipped") and r.get("download_url")
        ]
        if not pending:
            print("没有待下载项")
            return

        ok = 0
        for rec in pending:
            local_path = Path(rec["local_path"])
            if local_path.exists():
                rec["downloaded"] = True
                rec.pop("error", None)
                ok += 1
                continue
            for attempt in range(3):
                try:
                    _download(rec["download_url"], local_path)
                    rec["downloaded"] = True
                    rec.pop("error", None)
                    ok += 1
                    print(f"  [OK] {rec['title']}", flush=True)
                    break
                except Exception as exc:  # noqa: BLE001
                    time.sleep(1.0 * (attempt + 1))
                    if attempt == 2:
                        rec["error"] = str(exc)[:120]
            time.sleep(0.8)

        manifest["downloaded_count"] = sum(1 for r in manifest["images"] if r.get("downloaded"))
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        still_failed = sum(1 for r in manifest["images"] if r.get("error"))
        print(f"第 {round_no} 轮: 新增成功 {ok}, 仍失败 {still_failed}", flush=True)
        if ok == 0:
            print("本轮无进展，等待冷却后重试", flush=True)
            time.sleep(30)


if __name__ == "__main__":
    main()
