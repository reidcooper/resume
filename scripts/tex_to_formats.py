#!/usr/bin/env python3
"""
tex_to_formats.py

Converts reid_cooper_resume.tex to reid_cooper_resume.md and reid_cooper_resume.txt.

Parses the custom LaTeX resume commands used in this repo and maps them to
structured Markdown. Plain text is derived from the Markdown output by
stripping all Markdown syntax.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEX_FILE = REPO_ROOT / "reid_cooper_resume.tex"
MD_FILE = REPO_ROOT / "reid_cooper_resume.md"
TXT_FILE = REPO_ROOT / "reid_cooper_resume.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def md_inline(text: str) -> str:
    r"""Translate LaTeX inline markup to Markdown equivalents."""
    # \href{url}{text} -> [text](url)
    text = re.sub(r"\\href\{([^}]*)\}\{([^}]*)\}", r"[\2](\1)", text)

    # \textbf{...} -> **...**
    text = re.sub(r"\\textbf\{([^}]*)\}", r"**\1**", text)

    # \textit{...} / \emph{...} -> *...*
    text = re.sub(r"\\(?:textit|emph)\{([^}]*)\}", r"*\1*", text)

    # \small{...} and size commands -> keep content
    text = re.sub(r"\\(?:small|large|Large|LARGE|huge|Huge)\{([^}]*)\}", r"\1", text)

    # Escaped characters
    text = text.replace(r"\%", "%")
    text = text.replace(r"\&", "&")
    text = text.replace(r"\_", "_")
    text = text.replace(r"\#", "#")
    text = text.replace(r"\$", "$")
    text = text.replace(r"~", " ")

    # Remove remaining macros with no args
    text = re.sub(r"\\(?:vspace|hspace)\{[^}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?\s*", "", text)

    # Strip stray braces
    text = text.replace("{", "").replace("}", "")

    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_braced_arg(s: str, start: int) -> tuple[str, int]:
    r"""
    Extract the content of the next {arg} beginning at or after `start`.
    Returns (content, index_after_closing_brace). Handles nested braces.
    """
    i = s.find("{", start)
    if i == -1:
        return ("", start)
    depth = 0
    buf = []
    for j in range(i, len(s)):
        ch = s[j]
        if ch == "{":
            depth += 1
            if depth > 1:
                buf.append(ch)
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return ("".join(buf), j + 1)
            else:
                buf.append(ch)
        else:
            buf.append(ch)
    return ("".join(buf), len(s))


def extract_n_args(s: str, start: int, n: int) -> tuple[list[str], int]:
    """Extract n consecutive {arg} arguments starting at `start`."""
    args = []
    pos = start
    for _ in range(n):
        arg, pos = extract_braced_arg(s, pos)
        args.append(arg)
    return args, pos


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_tex(source: str) -> list[dict]:
    r"""
    Walk through the LaTeX source and emit a list of structured events.

    Event types:
        heading       -- name, email, phone, website
        section       -- title
        subheading    -- company, location, title, dates
        subsubheading -- title, dates
        item          -- title, description
        subitem       -- title, description
        summary       -- text
        plain_item    -- text (for skill lines)
    """
    events = []
    src = source

    # -----------------------------------------------------------------------
    # Header -- parse fields individually for reliability
    # -----------------------------------------------------------------------
    name_m = re.search(r"\\Large\s+([^}\\]+)\}", src)
    email_m = re.search(r"mailto:([^}]+)\}", src)
    phone_m = re.search(r"\\href\{tel:[^}]*\}\{([^}]*)\}", src)
    website_m = re.search(r"\\href\{(https://[^}]*)\}\{https://", src)

    if name_m and email_m:
        events.append({
            "type": "heading",
            "name": name_m.group(1).strip(),
            "email": email_m.group(1).strip(),
            "phone": phone_m.group(1).strip() if phone_m else "",
            "website": website_m.group(1).strip() if website_m else "",
        })

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    summary_m = re.search(
        r"\\section\{Summary\}\s*\n\\small\{(.*?)\}",
        src, re.DOTALL
    )
    if summary_m:
        events.append({"type": "summary", "text": summary_m.group(1).strip()})

    # -----------------------------------------------------------------------
    # All other sections
    # -----------------------------------------------------------------------
    section_re = re.compile(r"\\section\{([^}]+)\}")
    sections = list(section_re.finditer(src))

    for idx, sec_m in enumerate(sections):
        sec_title = sec_m.group(1).strip()
        if sec_title == "Summary":
            continue

        sec_start = sec_m.end()
        sec_end = sections[idx + 1].start() if idx + 1 < len(sections) else len(src)
        sec_body = src[sec_start:sec_end]

        events.append({"type": "section", "title": sec_title})

        if sec_title == "Education":
            _parse_education(sec_body, events)
        elif sec_title == "Experience":
            _parse_experience(sec_body, events)
        elif sec_title in ("Apps", "Projects"):
            _parse_subitems(sec_body, events)
        elif sec_title == "Technical Skills":
            _parse_skills(sec_body, events)

    return events


def _parse_education(body: str, events: list) -> None:
    r"""Parse \resumeSubheading blocks in the Education section."""
    # Use negative lookahead so we don't match \resumeSubSubheading
    pattern = re.compile(r"\\resumeSubheading(?!Sub)\s*")
    for m in pattern.finditer(body):
        args, _ = extract_n_args(body, m.end(), 4)
        events.append({
            "type": "subheading",
            "company": args[0],
            "location": args[1],
            "title": args[2],
            "dates": args[3],
        })


def _parse_experience(body: str, events: list) -> None:
    r"""
    Parse the experience section using a linear token-stream approach.

    Regex alternation with \resumeSubSubheading listed first ensures the longer
    string wins over the \resumeSubheading prefix.
    """
    token_re = re.compile(
        r"\\resumeSubSubheading\s*"
        r"|\\resumeSubheading(?!Sub)\s*"
        r"|\\resumeItem(?!List)\s*"
    )

    for tok in token_re.finditer(body):
        name = tok.group().strip()
        pos = tok.end()

        if name == r"\resumeSubSubheading":
            args, _ = extract_n_args(body, pos, 2)
            events.append({
                "type": "subsubheading",
                "title": args[0],
                "dates": args[1],
            })
        elif name == r"\resumeSubheading":
            args, _ = extract_n_args(body, pos, 4)
            events.append({
                "type": "subheading",
                "company": args[0],
                "location": args[1],
                "title": args[2],
                "dates": args[3],
            })
        elif name == r"\resumeItem":
            args, _ = extract_n_args(body, pos, 2)
            events.append({
                "type": "item",
                "title": args[0],
                "description": args[1],
            })


def _parse_subitems(body: str, events: list) -> None:
    r"""Parse \resumeSubItem{title}{desc} entries."""
    pattern = re.compile(r"\\resumeSubItem\s*")
    for m in pattern.finditer(body):
        args, _ = extract_n_args(body, m.end(), 2)
        events.append({"type": "subitem", "title": args[0], "description": args[1]})


def _parse_skills(body: str, events: list) -> None:
    r"""Parse \item{\textbf{Category}{: values}} entries in the skills section."""
    pattern = re.compile(
        r"\\item\{(.*?)\}(?=\s*(?:\\item|\\resumeSubHeadingListEnd|$))",
        re.DOTALL
    )
    for m in pattern.finditer(body):
        content = m.group(1).strip()
        events.append({"type": "plain_item", "text": content})


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def render_markdown(events: list) -> str:
    lines = []
    last_type = None

    for ev in events:
        t = ev["type"]

        if t == "heading":
            lines.append(f"# {md_inline(ev['name'])}")
            lines.append("")
            parts = []
            if ev["email"]:
                parts.append(f"[{ev['email']}](mailto:{ev['email']})")
            if ev["phone"]:
                parts.append(ev["phone"])
            if ev["website"]:
                parts.append(f"[{ev['website']}]({ev['website']})")
            lines.append(" | ".join(parts))
            lines.append("")

        elif t == "summary":
            lines.append("## Summary")
            lines.append("")
            lines.append(md_inline(ev["text"]))
            lines.append("")

        elif t == "section":
            if last_type not in (None, "heading", "summary"):
                lines.append("")
            lines.append(f"## {ev['title']}")
            lines.append("")

        elif t == "subheading":
            if last_type not in (None, "section"):
                lines.append("")
            company = md_inline(ev["company"])
            location = md_inline(ev["location"])
            title = md_inline(ev["title"])
            dates = md_inline(ev["dates"])
            lines.append(f"### {company} -- {location}")
            lines.append(f"**{title}** | {dates}")
            lines.append("")

        elif t == "subsubheading":
            lines.append("")
            title = md_inline(ev["title"])
            dates = md_inline(ev["dates"])
            lines.append(f"**{title}** | {dates}")
            lines.append("")

        elif t == "item":
            title = md_inline(ev["title"])
            desc = md_inline(ev["description"])
            lines.append(f"- **{title}**: {desc}")

        elif t == "subitem":
            title = md_inline(ev["title"])
            desc = md_inline(ev["description"])
            lines.append(f"- **{title}**: {desc}")

        elif t == "plain_item":
            lines.append(f"- {md_inline(ev['text'])}")

        last_type = t

    return "\n".join(lines) + "\n"


def md_to_plain(md: str) -> str:
    """Convert Markdown to plain text by stripping all syntax."""
    text = md

    # Headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Bold/italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)

    # Links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # List bullets
    text = re.sub(r"^[-*+] ", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip() + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not TEX_FILE.exists():
        print(f"ERROR: {TEX_FILE} not found", file=sys.stderr)
        sys.exit(1)

    source = TEX_FILE.read_text(encoding="utf-8")
    events = parse_tex(source)

    md = render_markdown(events)
    txt = md_to_plain(md)

    MD_FILE.write_text(md, encoding="utf-8")
    TXT_FILE.write_text(txt, encoding="utf-8")

    print(f"Written: {MD_FILE}")
    print(f"Written: {TXT_FILE}")


if __name__ == "__main__":
    main()
