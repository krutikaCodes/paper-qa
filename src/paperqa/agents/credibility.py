from paperqa.types import DocDetails


# This function extracts important information
# about a research paper.

def extract_metadata(doc: DocDetails):

    # Get the paper's title
    title = doc.title

    # Get the paper's authors
    authors = doc.authors

    # Get the paper's publication
    publication = doc.journal

    # Get the paper's DOI
    doi = doc.doi

    # Get the publishing organization
    publisher = doc.publisher

    # Get the number of citations
    citation_count = doc.citation_count

    # Get the quality of the publication
    source_quality = doc.source_quality

    # Check whether the paper has been retracted
    is_retracted = doc.is_retracted

    # Return all the information in a dictionary
    return {
        "title": title,
        "authors": authors,
        "publication": publication,
        "doi": doi,
        "publisher": publisher,
        "citation_count": citation_count,
        "source_quality": source_quality,
        "is_retracted": is_retracted
    }