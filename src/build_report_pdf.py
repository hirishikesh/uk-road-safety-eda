"""Render reports/REPORT.md to reports/UK_Road_Safety_Report.pdf via headless Edge/Chrome.

Usage:
    python -m src.build_report_pdf
"""
import shutil
import subprocess
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge", "google-chrome", "chromium", "chrome",
]

CSS = """
@page { size: A4; margin: 16mm 15mm; }
body { font-family: "Segoe UI", system-ui, sans-serif; color: #0b0b0b; font-size: 10.5pt; line-height: 1.5; }
h1 { font-size: 21pt; margin: 0 0 4px; }
h2 { font-size: 14pt; margin-top: 22px; border-bottom: 1px solid #e1e0d9; padding-bottom: 3px; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
a { color: #256abf; text-decoration: none; }
hr { border: 0; border-top: 1px solid #e1e0d9; margin: 16px 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9pt; break-inside: avoid; }
th, td { border-bottom: 1px solid #e1e0d9; padding: 4px 6px; text-align: left; vertical-align: top; }
th { color: #52514e; font-weight: 600; }
td:not(:first-child) { font-variant-numeric: tabular-nums; }
img { max-width: 100%; max-height: 160mm; display: block; margin: 8px auto 2px; break-inside: avoid; }
p:has(> img) { break-inside: avoid; break-after: avoid; }
em { color: #52514e; }
code { font-size: 9pt; background: #f0efec; padding: 0 3px; border-radius: 3px; }
"""


def main() -> None:
    md_text = (REPORTS / "REPORT.md").read_text(encoding="utf-8")
    body = markdown.markdown(md_text, extensions=["tables"])
    html_path = REPORTS / "report.html"
    html_path.write_text(
        f'<!doctype html><html><head><meta charset="utf-8"><title>UK Road Safety Report</title>'
        f"<style>{CSS}</style></head><body>{body}</body></html>", encoding="utf-8")

    browser = next((b for b in BROWSERS if Path(b).exists() or shutil.which(b)), None)
    if browser is None:
        raise SystemExit(f"No Edge/Chrome found; open {html_path} and print to PDF manually.")
    pdf_path = REPORTS / "UK_Road_Safety_Report.pdf"
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", html_path.as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    html_path.unlink()
    print(f"wrote {pdf_path}")


if __name__ == "__main__":
    main()
