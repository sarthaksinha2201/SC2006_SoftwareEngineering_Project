# Deliverable generator

Rebuilds `lab4_deliverable_FR_NFR.docx` (FR, NFR, Data Dictionary,
use case diagram, UC-1 to UC-13) from `DECISIONS.md` and the code.

```bash
npm install docx
python3 gen_usecase.py
qlmanage -t -s 1860 -o . use_case_diagram.svg && mv use_case_diagram.svg.png use_case_diagram.png
node build_doc.js
```

- `gen_usecase.py` draws the use case diagram (SVG; the PNG is what the document embeds).
- `use_cases.js` holds the thirteen use case descriptions.
- `build_doc.js` holds the FR, NFR and Data Dictionary, and assembles the document.
