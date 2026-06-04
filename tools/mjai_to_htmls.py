#!/usr/bin/env python3
"""Convert mjai jsonl.gz logs to standalone HTML files using Mortal's log-viewer.

Each input *.json.gz becomes <out_dir>/hanchan_NNN.html, viewable in any browser.
Mortal log-viewer expects mjai jsonl content as the JS variable `allActions`.
"""
import gzip, sys, shutil
from pathlib import Path

TEMPLATE = """<!DOCTYPE html>
<html><head>
  <meta charset="utf-8">
  <title>{title}</title>
  <link rel="stylesheet" type="text/css" href="files/css/style.css">
  <script src="files/js/jquery-1.7.2.min.js"></script>
  <script src="files/js/dytem.js"></script>
  <script>
    allActions = `
{actions}
`;
  </script>
</head><body><div id="content"></div></body></html>
"""


def main():
    if len(sys.argv) < 4:
        print("Usage: mjai_to_htmls.py <log_viewer_dir> <input_mjai_dir> <output_dir>")
        return 1
    viewer_dir = Path(sys.argv[1])
    in_dir = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    # Copy files/ from viewer template (CSS/JS)
    if not (out_dir / "files").exists() and (viewer_dir / "files").exists():
        shutil.copytree(viewer_dir / "files", out_dir / "files")
    logs = sorted(in_dir.glob("*.json.gz"))
    print(f"converting {len(logs)} logs to HTML in {out_dir}")
    for i, p in enumerate(logs):
        with gzip.open(p, "rt") as f:
            content = f.read()
        html = TEMPLATE.format(title=f"Hanchan {i:03d} ({p.stem})", actions=content)
        (out_dir / f"hanchan_{i:03d}.html").write_text(html)
    # Index page
    items = "\n".join(
        f'<li><a href="hanchan_{i:03d}.html">Hanchan {i:03d}</a></li>'
        for i in range(len(logs))
    )
    (out_dir / "index.html").write_text(
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{out_dir.name}</title></head>"
        f"<body><h1>{out_dir.name}</h1><ul>{items}</ul></body></html>"
    )
    print(f"wrote {len(logs)} HTML + index.html to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
