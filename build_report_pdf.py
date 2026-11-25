#!/usr/bin/env python3
"""Render 实验报告.md to a PDF with Microsoft Edge's headless print-to-pdf.

Usage (from the repository root):
    python build_report_pdf.py

The converter implements only the Markdown subset used by the report:
headings, paragraphs, fenced code blocks, tables, ordered/unordered lists,
block quotes, inline code, bold, and Obsidian style ![[image.png]] embeds.
Missing images are rendered as a visible placeholder so the PDF never
silently loses a screenshot reference.
"""

import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "实验报告.md"
OUT = ROOT / "实验报告.pdf"
SHOT_DIR = ROOT / "screenshot"

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 16mm 16mm 14mm 16mm; }
body {
  font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
  font-size: 10.5pt; line-height: 1.65; color: #1a1a1a;
  width: 178mm; margin: 0 auto;   /* A4 210mm - 2*16mm: 屏幕预览 = PDF 版心 */
}
h1 { font-size: 19pt; text-align: center; margin: 0 0 6pt 0; }
h2 { font-size: 14.5pt; margin: 20pt 0 8pt 0; padding-bottom: 3pt;
     border-bottom: 1.2pt solid #333; page-break-after: avoid; }
h3 { font-size: 12pt; margin: 14pt 0 6pt 0; page-break-after: avoid; }
p { margin: 5pt 0; text-align: justify; }
ul, ol { margin: 5pt 0 5pt 0; padding-left: 20pt; }
li { margin: 2.5pt 0; }
code {
  font-family: Consolas, "Courier New", monospace; font-size: 9.2pt;
  background: #f2f2f2; padding: 0.5pt 2pt; border-radius: 2pt;
}
pre {
  background: #f7f7f7; border: 0.6pt solid #d8d8d8; border-radius: 3pt;
  padding: 6pt 8pt; margin: 7pt 0; overflow-x: hidden;
  page-break-inside: avoid;
}
pre code { background: none; padding: 0; font-size: 8.6pt; line-height: 1.42;
           white-space: pre-wrap; word-break: break-all; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9.3pt;
        page-break-inside: avoid; }
th, td { border: 0.6pt solid #999; padding: 3.2pt 5pt; text-align: left;
         vertical-align: top; }
th { background: #ececec; font-weight: 600; }
blockquote { margin: 7pt 0; padding: 4pt 9pt; border-left: 3pt solid #bbb;
             background: #fafafa; color: #444; font-size: 10pt; }
blockquote p { margin: 0; }
img { max-width: 100%; height: auto; display: block; margin: 8pt auto;
      border: 0.6pt solid #ddd; page-break-inside: avoid; }
.missing { border: 0.8pt dashed #c00; color: #b00; background: #fff5f5;
           padding: 6pt 8pt; margin: 8pt 0; font-size: 9.5pt; text-align: center; }
hr { border: none; border-top: 0.6pt solid #ccc; margin: 12pt 0; }
"""


def resolve_image(name: str) -> str:
    """Return an <img> for an Obsidian embed, or a visible placeholder.

    Obsidian writes `![[name.png]]`, optionally with a display width
    (`![[name.png|346]]`), and rewrites it to `![[screenshot/name.png]]` when
    "Automatically update internal links" moves the file, so accept all three.
    The file is looked up in screenshot/ first, then in the repository root.
    """
    spec, _, width = name.partition("|")
    style = f' style="width:{width.strip()}px"' if width.strip().isdigit() else ""
    clean = spec.strip().replace("\\", "/").lstrip("./")
    if clean.startswith("screenshot/"):
        clean = clean[len("screenshot/"):]
    for base in (SHOT_DIR, ROOT):
        candidate = base / clean
        if candidate.is_file():
            # absolute file:// URL: the HTML lives in .build/, so a relative
            # path would resolve against the wrong directory
            return (f'<img src="{candidate.resolve().as_uri()}" '
                    f'alt="{html.escape(clean)}"{style}>')
    return (f'<div class="missing">〔缺少截图文件：screenshot/{html.escape(clean)}'
            f'　（导出前请把图片放进 screenshot/ 目录）〕</div>')


def inline(text: str) -> str:
    """Inline formatting: escape first, then apply the report's markup."""
    out = html.escape(text, quote=False)
    # Obsidian embeds, before the generic escape turned them into text.
    out = re.sub(r"!\[\[([^\]]+)\]\]", lambda m: resolve_image(m.group(1)), out)
    # Standard markdown images: ![alt](path)
    out = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                 lambda m: (f'<img src="{html.escape(m.group(2))}" '
                            f'alt="{m.group(1)}">'), out)
    # Inline code first, so ** inside code is not treated as bold.
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", out)
    return out


def split_row(line: str) -> list:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md: str) -> str:
    lines = md.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # fenced code
        m = re.match(r"^```(\w*)\s*$", line)
        if m:
            lang = m.group(1)
            i += 1
            body = []
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1  # closing fence
            code = html.escape("\n".join(body), quote=False)
            cls = f' class="language-{lang}"' if lang else ""
            blocks.append(f"<pre><code{cls}>{code}</code></pre>")
            continue

        # table: a header row followed by a | --- | separator row
        if line.startswith("|") and i + 1 < len(lines) and re.match(
                r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            header = split_row(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in header)
            trs = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                for r in rows)
            blocks.append(f"<table><thead><tr>{th}</tr></thead>"
                          f"<tbody>{trs}</tbody></table>")
            continue

        # headings
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            blocks.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # block quote
        if line.startswith(">"):
            body = []
            while i < len(lines) and lines[i].startswith(">"):
                body.append(lines[i].lstrip(">").strip())
                i += 1
            blocks.append(
                "<blockquote><p>"
                + "<br>".join(inline(x) for x in body)
                + "</p></blockquote>")
            continue

        # ordered / unordered list
        m = re.match(r"^(?:(\d+)\.|-)\s+(.*)$", line)
        if m:
            tag = "ol" if m.group(1) else "ul"
            items = []
            while i < len(lines):
                mm = re.match(r"^(?:(\d+)\.|-)\s+(.*)$", lines[i])
                if not mm:
                    # allow an indented continuation line of the last item
                    if lines[i].startswith("  ") and items and lines[i].strip():
                        items[-1] += " " + lines[i].strip()
                        i += 1
                        continue
                    break
                items.append(mm.group(2))
                i += 1
            lis = "".join(f"<li>{inline(x)}</li>" for x in items)
            blocks.append(f"<{tag}>{lis}</{tag}>")
            continue

        # blank line
        if not line.strip():
            i += 1
            continue

        # paragraph
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|```|\||>|\d+\.\s|-\s)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        if para:
            blocks.append(f"<p>{inline(' '.join(para))}</p>")

    title = "ICS Lab 3 缓冲区溢出实验报告"
    return (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            f"<title>{title}</title><style>{CSS}</style></head><body>"
            + "\n".join(blocks) + "</body></html>")


def find_edge() -> str:
    for p in EDGE_CANDIDATES:
        if Path(p).is_file():
            return p
    found = shutil.which("msedge") or shutil.which("chrome")
    if found:
        return found
    sys.exit("Could not find Microsoft Edge. Install it or print the HTML manually.")


def main() -> None:
    if not SRC.is_file():
        sys.exit(f"missing source: {SRC}")
    doc = convert(SRC.read_text(encoding="utf-8"))

    build_dir = ROOT / ".build"
    build_dir.mkdir(exist_ok=True)
    html_path = build_dir / "report.html"
    html_path.write_text(doc, encoding="utf-8")

    profile = build_dir / "edge-profile"
    cmd = [
        find_edge(),
        "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--user-data-dir={profile}",
        "--no-pdf-header-footer",
        f"--print-to-pdf={OUT}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not OUT.is_file():
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:])
        sys.exit("Edge did not produce a PDF")

    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.name}  ({kb:.1f} KiB)")
    missing = re.findall(r"缺少截图文件：screenshot/([^　]+)", doc)
    if missing:
        print(f"{len(missing)} image(s) still missing:")
        for name in missing:
            print("  -", name)


if __name__ == "__main__":
    main()
