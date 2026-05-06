"""
Generates a personalized cover letter PDF for a specific job using Claude API.
Reads cover_letter_template.md, fills in the placeholders, and writes a PDF.

Usage:
  python tools/generate_cover_letter.py \
    --job_id "indeed_abc123" \
    --title "Personal Injury Paralegal" \
    --company "Smith & Associates" \
    --description "We are seeking a detail-oriented paralegal..."
"""

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)
load_dotenv(ROOT / ".env")

TEMPLATE_PATH = ROOT / "cover_letter_template.md"


def load_template():
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: {TEMPLATE_PATH} not found.")
        sys.exit(1)
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text.strip()


def generate_personalized_paragraph(company, title, description):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    system = """You write one short paragraph (3-4 sentences) for a cover letter.
Your goal is to connect the applicant's legal support background to this specific firm and role.
Rules you must follow without exception:
- Never use em dashes (the — character). Use commas or periods instead.
- Write naturally, like a real person. Vary sentence length.
- Do not use corporate buzzwords like "synergy", "leverage", "dynamic", "passionate", "impactful".
- Do not start every sentence the same way.
- Sound genuine, not like a template.
- Keep it to 3-4 sentences maximum.
Output only the paragraph text, nothing else."""

    user = f"""Write a cover letter paragraph for this job:
Company: {company}
Position: {title}
Job description excerpt: {description[:800] if description else 'Not provided'}

Connect the applicant's background in legal support and client advocacy to what this firm needs."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    text = message.content[0].text.strip()
    if "—" in text or " -- " in text:
        text = text.replace("—", ",").replace(" -- ", ", ")

    return text


def fill_template(template, company, title, personalized_paragraph):
    user_name = os.getenv("USER_FULL_NAME", "")
    user_email = os.getenv("USER_EMAIL", "")
    user_phone = os.getenv("USER_PHONE", "")
    user_linkedin = os.getenv("USER_LINKEDIN_URL", "")
    today = date.today().strftime("%B %d, %Y")

    filled = template
    filled = filled.replace("{user_full_name}", user_name)
    filled = filled.replace("{user_email}", user_email)
    filled = filled.replace("{user_phone}", user_phone)
    filled = filled.replace("{user_linkedin_url}", user_linkedin)
    filled = filled.replace("{today_date}", today)
    filled = filled.replace("{company_name}", company)
    filled = filled.replace("{job_title}", title)
    filled = filled.replace("{personalized_paragraph}", personalized_paragraph)

    return filled


def markdown_to_pdf(text, output_path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=12,
    )
    header = ParagraphStyle(
        "header",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=4,
    )

    story = []
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if story and isinstance(story[-1], Spacer):
            story.append(Paragraph(safe, header))
        else:
            story.append(Paragraph(safe, normal))

    doc.build(story)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--description", default="")
    args = parser.parse_args()

    print(f"Generating cover letter for {args.company} | {args.title}...")

    template = load_template()
    personalized = generate_personalized_paragraph(args.company, args.title, args.description)
    filled = fill_template(template, args.company, args.title, personalized)

    output_path = TMP / f"cover_letter_{args.job_id}.pdf"
    markdown_to_pdf(filled, output_path)

    print(f"Cover letter saved to {output_path}")
    print(f"Personalized paragraph: {personalized[:120]}...")

    return str(output_path)


if __name__ == "__main__":
    main()
