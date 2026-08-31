#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
COMPACT = ROOT / "working" / "compact"
OUT = ROOT / "working" / "figures"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    count = 0
    for compact_file in sorted(COMPACT.glob("*.jsonl")):
        year = compact_file.stem
        year_out = OUT / year
        year_out.mkdir(parents=True, exist_ok=True)
        for line in compact_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            for idx, url in enumerate(record.get("figure_urls") or [], start=1):
                if url in seen:
                    continue
                seen.add(url)
                suffix = Path(urlparse(url).path).suffix or ".png"
                target = year_out / f"{record['id']}-fig{idx}{suffix}"
                req = urllib.request.Request(url, headers={"User-Agent": "gaokao-independent-verifier/1.0"})
                with urllib.request.urlopen(req, timeout=60) as response:
                    target.write_bytes(response.read())
                print(f"downloaded {url} -> {target.relative_to(ROOT)}")
                count += 1
    print(f"downloaded {count} figures")


if __name__ == "__main__":
    main()
