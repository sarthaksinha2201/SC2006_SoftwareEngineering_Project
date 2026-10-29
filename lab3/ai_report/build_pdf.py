"""Builds report.pdf from report.md, inserting the two AI responses verbatim where it says
{{RESPONSE_A}} and {{RESPONSE_B}}.

    python3 build_pdf.py

Converts the small Markdown subset these files use (headings, tables, lists, block
quotes, code blocks, bold, inline code) to HTML, then prints it with headless Chrome.
"""
import html
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CITES = re.compile(r"((?: (?:GoWhere_requirements_and_use_ca…|class_diagram_mermaid))+)(?=\s*$)")


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*]+?)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", t)
    return t


def convert(md, cites=False):
    out, lines, i = [], md.splitlines(), 0
    lists = []                                   # stack of (tag, indent)

    def close_lists(indent=-1):
        while lists and lists[-1][1] > indent:
            out.append(f"</{lists.pop()[0]}>")

    while i < len(lines):
        line = lines[i]
        if cites:
            line = CITES.sub(lambda m: ' <span class="cite">[cites: '
                             + ", ".join(m.group(1).split()) + "]</span>", line)
        s = line.strip()
        if s.startswith("```"):
            close_lists()
            block = []
            i += 1
            while not lines[i].strip().startswith("```"):
                block.append(lines[i]); i += 1
            out.append("<pre>" + html.escape("\n".join(block)) + "</pre>")
        elif s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|$", lines[i + 1].strip()):
            close_lists()
            row = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in row(s)) + "</tr>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row(lines[i])) + "</tr>")
                i += 1
            out.append("</table>")
            continue
        elif m := re.match(r"^(#{1,4}) (.*)", s):
            close_lists()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif s == "---":
            close_lists(); out.append("<hr>")
        elif s.startswith(">"):
            close_lists()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip()); i += 1
            paras = "\n".join(quote).split("\n\n")
            out.append("<blockquote>" + "".join(f"<p>{'<br>'.join(inline(x) for x in p.splitlines())}</p>"
                                                for p in paras) + "</blockquote>")
            continue
        elif m := re.match(r"^(\s*)([-*]|\d+\.) (.*)", line):
            indent, tag = len(m.group(1)), "ul" if m.group(2) in "-*" else "ol"
            close_lists(indent)
            if not lists or lists[-1][1] < indent:
                out.append(f"<{tag}>"); lists.append((tag, indent))
            out.append(f"<li>{inline(m.group(3))}</li>")
        elif not s:
            close_lists()
        else:
            close_lists()
            out.append(f"<p>{inline(s)}</p>")
        i += 1
    close_lists()
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 18mm 17mm; }
body { font-family: "Times New Roman", Times, serif; font-size: 11pt; line-height: 1.38; color: #000; }
h1 { font-size: 17pt; text-align: center; margin: 0 0 6pt; }
h2 { font-size: 13.5pt; margin: 16pt 0 6pt; border-bottom: 1px solid #000; padding-bottom: 2pt; }
h3 { font-size: 12pt; margin: 12pt 0 4pt; }
h4 { font-size: 11pt; margin: 10pt 0 3pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9.8pt; page-break-inside: auto; }
th, td { border: 1px solid #000; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #e8e8e8; }
tr { page-break-inside: avoid; }
code { font-family: Menlo, Consolas, monospace; font-size: 9pt; }
pre { font-family: Menlo, Consolas, monospace; font-size: 8.4pt; line-height: 1.25; border: 1px solid #999;
      padding: 6pt; white-space: pre-wrap; page-break-inside: avoid; }
blockquote { margin: 6pt 0 10pt; padding: 4pt 10pt; border-left: 3px solid #555; background: #f4f4f4; }
blockquote p { margin: 3pt 0; }
hr { border: 0; border-top: 1px solid #bbb; margin: 12pt 0; }
li { margin: 2pt 0; }
.appendix { page-break-before: always; }
.appendix-note { font-style: italic; font-size: 10pt; }
.response { border: 1px solid #000; padding: 4pt 12pt 8pt; }
.response h1 { font-size: 13pt; text-align: left; }
.response h2 { font-size: 12pt; border: 0; }
.response h3 { font-size: 11pt; }
.cite { font-size: 8.5pt; color: #555; }
"""

NOTE = ('<p class="cite">ChatGPT\'s file-citation markers are shown as [cites: …]: '
        '<code>GoWhere_requirements_and_use_ca…</code> is the requirements document, '
        '<code>class_diagram_mermaid</code> the class diagram.</p>')
body = convert((HERE / "report.md").read_text())
for key, name in [("{{RESPONSE_A}}", "response_A_tech_stack.md"), ("{{RESPONSE_B}}", "response_B_skeleton.md")]:
    body = body.replace(f"<p>{key}</p>",
                        f'<div class="response">{convert((HERE / name).read_text(), cites=True)}</div>' + NOTE)

page = f'<!doctype html><html><head><meta charset="utf-8"><title>SC2006 Lab 3 AI report</title><style>{CSS}</style></head><body>{body}</body></html>'
(HERE / "report.html").write_text(page)
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={HERE / 'report.pdf'}", (HERE / "report.html").as_uri()],
               check=True, capture_output=True)
(HERE / "report.html").unlink()
print("wrote", HERE / "report.pdf")
