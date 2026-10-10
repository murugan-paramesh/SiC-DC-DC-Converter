#!/usr/bin/env python3
"""
Build the combined textbook "Understanding the 6.6 kW SiC Dual Active Bridge Converter - From
Electrical Fundamentals to Advanced 2026 Power Electronics Research" from the chapter files.
Outputs (in textbook/): the combined Markdown, HTML and DOCX (pandoc) and, when a headless Chromium
is available (Playwright browser path), a PDF printed from the HTML.  Never fails the Markdown build
because of a missing converter: it reports what it could not produce.
"""
import os, glob, re, shutil, subprocess, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "textbook"); os.makedirs(OUT, exist_ok=True)
TITLE = "Understanding the 6.6 kW SiC Dual Active Bridge Converter - From Electrical Fundamentals to Advanced 2026 Power Electronics Research"
chapters = sorted(glob.glob(os.path.join(HERE, "[0-2][0-9]_*.md")))
parts = [f"% {TITLE}\n% Project learning notes (generated from 21_Human_Friendly_Learning_Notes)\n% {datetime.date.today().isoformat()}\n\n",
         "# Preface\n\nThis textbook is generated from the chapter files of `21_Human_Friendly_Learning_Notes/`. "
         "Every chapter is written on three levels (beginner, engineering, research) and every statement about the "
         "project carries a status tag; nothing in the project has been built or measured - all numbers are calculated "
         "or simulated. Rebuild with `python3 build_textbook.py`.\n\n"]
for ch in chapters:
    txt = open(ch, encoding="utf-8").read()
    # image paths relative to the notes folder -> relative to textbook/
    txt = re.sub(r"\]\((?!http)([^)]+\.(?:png|svg|jpg))\)", lambda m: "](../" + m.group(1) + ")", txt)
    parts.append(txt.rstrip() + "\n\n\\newpage\n\n")
md = os.path.join(OUT, "Understanding_the_6k6_SiC_DAB.md"); open(md, "w", encoding="utf-8").write("".join(parts))
print("markdown:", md, len("".join(parts).split()), "words,", len(chapters), "chapters")
report = {"markdown": True}
if shutil.which("pandoc"):
    html = md[:-3] + ".html"; docx = md[:-3] + ".docx"
    r = subprocess.run(["pandoc", md, "-s", "--toc", "--toc-depth=2", "--metadata", f"title={TITLE}", "-o", html,
                        "--embed-resources", "--standalone"], capture_output=True, text=True, cwd=OUT)
    if r.returncode != 0:   # older pandoc without --embed-resources
        r = subprocess.run(["pandoc", md, "-s", "--toc", "--toc-depth=2", "--self-contained", "-o", html], capture_output=True, text=True, cwd=OUT)
    report["html"] = r.returncode == 0; print("html:", r.returncode == 0, r.stderr[-300:] if r.returncode else "")
    r = subprocess.run(["pandoc", md, "--toc", "-o", docx], capture_output=True, text=True, cwd=OUT)
    report["docx"] = r.returncode == 0; print("docx:", r.returncode == 0, r.stderr[-300:] if r.returncode else "")
    chrome = None
    for c in ("chromium", "chromium-browser", "google-chrome"):
        if shutil.which(c): chrome = shutil.which(c); break
    if chrome is None:
        pw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        for cand in sorted(glob.glob(os.path.join(pw, "chromium*", "chrome-linux*", "chrome")) + glob.glob(os.path.join(pw, "chromium*", "chrome-linux*", "headless_shell"))):
            chrome = cand; break
    if chrome and report.get("html"):
        pdf = md[:-3] + ".pdf"
        r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--print-to-pdf={pdf}", "--no-pdf-header-footer", "file://" + html],
                           capture_output=True, text=True, timeout=600)
        report["pdf"] = os.path.exists(pdf) and os.path.getsize(pdf) > 1000; print("pdf:", report["pdf"], r.stderr[-200:] if not report["pdf"] else "")
    else:
        report["pdf"] = False; print("pdf: no headless Chromium found - not produced")
else:
    print("pandoc not found: only Markdown produced")
open(os.path.join(OUT, "BUILD_STATUS.txt"), "w").write("\n".join(f"{k}: {'produced' if v else 'NOT produced'}" for k, v in report.items()) + "\n")
