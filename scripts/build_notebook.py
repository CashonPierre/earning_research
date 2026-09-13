"""Build the report in two forms from ONE source of text: notebooks/report.ipynb (executed, outputs saved)
and docs/report.md (same text, tables rendered from the committed CSVs, figures linked).
Runs from the committed outputs/ folder only; no licensed data needed."""
from __future__ import annotations
import pathlib, sys, textwrap
import nbformat
from nbclient import NotebookClient
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from report_content import SECTIONS, TITLE, SETUP_CODE  # noqa: E402

def build_notebook():
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    cells = [nbformat.v4.new_markdown_cell(f"# {TITLE}"), nbformat.v4.new_code_cell(SETUP_CODE)]
    for s in SECTIONS:
        if s.get("md"):
            cells.append(nbformat.v4.new_markdown_cell(textwrap.dedent(s["md"]).strip()))
        if s.get("code"):
            cells.append(nbformat.v4.new_code_cell(textwrap.dedent(s["code"]).strip()))
    nb.cells = cells
    out = ROOT / "notebooks" / "report.ipynb"
    client = NotebookClient(nb, timeout=300, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}})
    client.execute()
    nbformat.write(nb, out)
    return out

def md_table(csv_path, cols=None, fmt=None, index=False, max_rows=40, query=None, rename=None):
    import pandas as pd
    df = pd.read_csv(ROOT / csv_path)
    if query: df = df.query(query)
    if cols: df = df[cols]
    if rename: df = df.rename(columns=rename)
    df = df.head(max_rows)
    if fmt:
        for c, f in fmt.items():
            if c in df: df[c] = df[c].map(lambda v: f.format(v) if pd.notna(v) else "")
    return df.to_markdown(index=index)

def build_markdown():
    parts = [f"# {TITLE}\n"]
    for s in SECTIONS:
        if s.get("md"): parts.append(textwrap.dedent(s["md"]).strip() + "\n")
        for t in s.get("tables", []): parts.append(md_table(**t) + "\n")
        for f in s.get("figs", []): parts.append(f"![{f[1]}](../{f[0]})\n*{f[1]}*\n")
    (ROOT / "docs" / "report.md").write_text("\n".join(parts))

if __name__ == "__main__":
    build_markdown(); print("docs/report.md written")
    if "--no-exec" not in sys.argv:
        print("notebook executed and saved:", build_notebook())
