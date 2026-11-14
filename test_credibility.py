import asyncio

from paperqa.docs import Docs
from paperqa.types import DocDetails, PQASession
from paperqa.agents.tools import (
    EvaluateSourceCredibility,
    EnvironmentState
)


async def main():

    # Step 1: Create a sample research paper
    paper = DocDetails(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        journal="NeurIPS",
        year=2017,
        doi="10.48550/arXiv.1706.03762"
    )

    # Step 2: Create a collection of documents
    docs = Docs()

    # Step 3: Add our sample paper to the collection
    docs.docs[paper.dockey] = paper

    # Step 4: Create a PaperQA session
    session = PQASession(
        question="Is this research paper credible?"
    )

    # Step 5: Create the environment state
    state = EnvironmentState(
        docs=docs,
        session=session
    )

    # Step 6: Create our credibility tool
    tool = EvaluateSourceCredibility()

    # Step 7: Call our credibility tool
    result = await tool.evaluate_source_credibility(
        title="Attention Is All You Need",
        state=state
    )

    # Step 8: Display the result
    print(result)


# Run our test
asyncio.run(main())