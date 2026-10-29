# Lab 3 §3.3 — prompts to run

Run these in ChatGPT, then paste each response back (the full text, plus the model name shown
in ChatGPT's model picker and the date). Don't edit the prompts: the report quotes them as sent.

---

## Part A — §3.3.1 tech-stack re-prompt

**New chat.** Upload both files in [`inputs/`](inputs/):

- `GoWhere_requirements_and_use_cases.docx` — current FR, NFR, Data Dictionary, use case model
- `class_diagram_mermaid.txt` — current design class diagram (Mermaid source)

Then send this, word for word. It is the exact Lab 2 prompt:

```
Based on the uploaded design materials, recommend a technology stack appropriate for an entry-level software engineering team
```

Ask nothing else in this chat. A follow-up would make the comparison with Lab 2 unfair.

---

## Part B — §3.3.3 AI-generated minimal skeleton

**Another new chat**, so Part A's answer doesn't steer it. Upload **only**
`class_diagram_mermaid.txt`. The manual says "using your class diagram as input". Then send:

```
The attached file is the design class diagram of a web application, written in Mermaid.

Generate a minimal skeleton template for this project in Python 3, using Flask.

Rules for the files:
1. Create a folder hierarchy containing all the files you think the project needs (source, templates, tests, configuration).
2. Every file must be empty except for TODO comments describing what will go in it.
3. Do not write any code at all. No imports, no class or function definitions, no method signatures, no variables, no configuration values, no HTML tags. Only comments.

Package the whole folder hierarchy as a single .zip file I can download.

After the zip, show the folder tree, and give one sentence per folder explaining why it exists.
```

If ChatGPT doesn't give you a downloadable zip, send this follow-up and keep a record that you
sent it, because the report has to list every prompt:

```
Please package the folder hierarchy as a downloadable .zip file.
```

Save the zip as `lab3/ai_report/ai_generated_skeleton.zip`. **Don't open it and fix anything
inside**: §3.3.4 asks us to critique what it actually produced.

---

## What to bring back

| Item | From |
|---|---|
| Model name (as shown in ChatGPT) and date | both chats |
| Part A response, full text | Part A |
| Part B response, full text, plus any follow-up prompt you had to send | Part B |
| `ai_generated_skeleton.zip` | Part B |
