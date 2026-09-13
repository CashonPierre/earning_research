"""Render docs/report.md to docs/report.html (figures embedded) and, if Google Chrome is present, docs/report.pdf."""
import base64, pathlib, re, shutil, subprocess
import markdown
ROOT = pathlib.Path(__file__).resolve().parents[1]; DOCS = ROOT / "docs"
md = (DOCS / "report.md").read_text()
def embed(m):
    p = (DOCS / m.group(2)).resolve(); b64 = base64.b64encode(p.read_bytes()).decode()
    return f'<figure><img src="data:image/png;base64,{b64}" alt="{m.group(1)}"></figure>'
body = markdown.markdown(re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", embed, md), extensions=["tables"])
css = """body{font-family:Georgia,serif;max-width:880px;margin:30px auto;padding:0 20px;font-size:11pt;line-height:1.45;color:#111}
h1{font-size:19pt} h2{font-size:14pt;margin-top:1.4em;border-bottom:1px solid #ccc} h3{font-size:12pt} table{border-collapse:collapse;font-size:8.5pt;margin:8px 0;display:block;overflow-x:auto}
th,td{border:1px solid #bbb;padding:3px 6px;vertical-align:top} th{background:#f0f0f0} img{max-width:100%;page-break-inside:avoid} figure{margin:12px 0;text-align:center} code{font-size:9.5pt} @page{margin:16mm}"""
(DOCS / "report.html").write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>PEAD breakout timing report</title><style>{css}</style></head><body>{body}</body></html>")
print("docs/report.html written")
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if pathlib.Path(chrome).exists() or shutil.which("google-chrome"):
    exe = chrome if pathlib.Path(chrome).exists() else shutil.which("google-chrome")
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={DOCS / 'report.pdf'}", f"file://{DOCS / 'report.html'}"], capture_output=True, timeout=120)
    print("docs/report.pdf written" if (DOCS / "report.pdf").exists() else "pdf failed")
else:
    print("Chrome not found; PDF not regenerated")
