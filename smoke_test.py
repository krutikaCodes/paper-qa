"""Quick check that paper-qa is installed and working.

Usage:
    python smoke_test.py <file.pdf>                # offline: read and chunk the PDF
    python smoke_test.py <file.pdf> "question"     # also ask Claude a question about it

The question step needs ANTHROPIC_API_KEY set in the environment.
"""

import asyncio
import os
import sys

from paperqa import Docs, Settings
from paperqa.readers import read_doc
from paperqa.types import Doc
from paperqa_pypdf import parse_pdf_to_pages

# Claude settings that work with this version of paper-qa (see MY_SETUP_LOG.md)
CLAUDE_MODEL = "anthropic/claude-haiku-4-5"

# Windows terminals can't print some symbols in papers without this
sys.stdout.reconfigure(encoding="utf-8")


def offline_check(pdf: str) -> None:
    doc = Doc(docname="test", citation="test citation", dockey="test")
    chunks = asyncio.run(
        read_doc(pdf, doc, chunk_chars=3000, overlap=100, parse_pdf=parse_pdf_to_pages)
    )
    print("Docs object created:", type(Docs()).__name__)
    print("Default LLM:", Settings().llm)
    print("Chunks read from PDF:", len(chunks))
    print("First chunk preview:", chunks[0].text[:200].replace("\n", " "))


async def claude_question(pdf: str, question: str) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY to ask a question.")
    settings = Settings(
        llm=CLAUDE_MODEL,
        summary_llm=CLAUDE_MODEL,
        embedding="sparse",  # Anthropic has no embedding models
    )
    settings.agent.agent_llm = CLAUDE_MODEL
    settings.parsing.enrichment_llm = CLAUDE_MODEL
    settings.parsing.use_doc_details = False  # skip rate-limited metadata lookup

    docs = Docs()
    await docs.aadd(pdf, citation="Test paper", docname="paper", settings=settings)
    session = await docs.aquery(question, settings=settings)
    print("\nAnswer:\n" + session.formatted_answer)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    offline_check(sys.argv[1])
    if len(sys.argv) > 2:
        asyncio.run(claude_question(sys.argv[1], sys.argv[2]))
