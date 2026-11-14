from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

THE_WORLD_UNIVERSITY_RANKINGS_YEAR = 2027
THE_WORLD_UNIVERSITY_RANKINGS_URL = (
    "https://www.timeshighereducation.com/world-university-rankings/latest/world-ranking"
)

THE_WORLD_UNIVERSITY_RANKINGS_TOP_100: tuple[tuple[int, str], ...] = (
    (1, "University of Oxford"),
    (2, "Massachusetts Institute of Technology"),
    (3, "Princeton University"),
    (3, "Stanford University"),
    (5, "University of Cambridge"),
    (6, "Harvard University"),
    (7, "California Institute of Technology"),
    (8, "Imperial College London"),
    (9, "University of California, Berkeley"),
    (9, "Yale University"),
    (11, "Tsinghua University"),
    (12, "ETH Zurich"),
    (13, "Peking University"),
    (14, "University of Pennsylvania"),
    (15, "National University of Singapore"),
    (16, "The University of Chicago"),
    (17, "Johns Hopkins University"),
    (17, "UCL"),
    (19, "Columbia University"),
    (20, "University of California, Los Angeles"),
    (21, "Cornell University"),
    (22, "University of Toronto"),
    (23, "University of Michigan-Ann Arbor"),
    (24, "Carnegie Mellon University"),
    (25, "Technical University of Munich"),
    (26, "University of Washington"),
    (27, "The University of Tokyo"),
    (28, "Nanyang Technological University, Singapore"),
    (29, "New York University (NYU)"),
    (29, "Northwestern University"),
    (29, "University of Edinburgh"),
    (32, "Duke University"),
    (33, "University of Hong Kong"),
    (34, "University of Melbourne"),
    (34, "Zhejiang University"),
    (36, "École Polytechnique Fédérale de Lausanne"),
    (37, "University of California, San Diego"),
    (38, "Fudan University"),
    (39, "Shanghai Jiao Tong University"),
    (40, "King’s College London"),
    (41, "LMU Munich"),
    (42, "The Chinese University of Hong Kong"),
    (43, "McGill University"),
    (44, "University of British Columbia"),
    (45, "KU Leuven"),
    (45, "Universität Heidelberg"),
    (47, "London School of Economics and Political Science"),
    (48, "University of Illinois at Urbana-Champaign"),
    (49, "Georgia Institute of Technology"),
    (50, "Delft University of Technology"),
    (51, "The University of Sydney"),
    (51, "University of Science and Technology of China"),
    (53, "University of Texas at Austin"),
    (53, "University of Wisconsin-Madison"),
    (55, "Karolinska Institute"),
    (56, "Seoul National University"),
    (57, "Paris Sciences et Lettres – PSL Research University Paris"),
    (58, "The Hong Kong University of Science and Technology"),
    (59, "Nanjing University"),
    (60, "University of Manchester"),
    (61, "Monash University"),
    (62, "Kyoto University"),
    (62, "University of Amsterdam"),
    (64, "Korea Advanced Institute of Science and Technology (KAIST)"),
    (65, "University of California, Davis"),
    (66, "Wageningen University & Research"),
    (66, "Washington University in St Louis"),
    (68, "Sungkyunkwan University (SKKU)"),
    (69, "Leiden University"),
    (70, "City University of Hong Kong"),
    (71, "University of California, Santa Barbara"),
    (71, "University of Southern California"),
    (73, "Brown University"),
    (73, "The University of Queensland"),
    (75, "Institut Polytechnique de Paris"),
    (75, "UNSW Sydney"),
    (77, "Australian National University"),
    (78, "Université Paris-Saclay"),
    (79, "The Hong Kong Polytechnic University"),
    (80, "Yonsei University (Seoul campus)"),
    (81, "University of Copenhagen"),
    (82, "University of Bristol"),
    (83, "University of Glasgow"),
    (84, "Purdue University West Lafayette"),
    (85, "University of North Carolina at Chapel Hill"),
    (86, "Boston University"),
    (87, "University of Groningen"),
    (88, "University of Minnesota"),
    (89, "University of Bonn"),
    (90, "RWTH Aachen University"),
    (91, "Humboldt University of Berlin"),
    (92, "Vanderbilt University"),
    (93, "Michigan State University"),
    (94, "Charité – Universitätsmedizin Berlin"),
    (95, "University of Vienna"),
    (96, "Harbin Institute of Technology"),
    (97, "Aarhus University"),
    (97, "Ohio State University (Main campus)"),
    (97, "University of Birmingham"),
    (97, "University of California, Irvine"),
)

_ALIASES: dict[str, str] = {
    "MIT": "Massachusetts Institute of Technology",
    "Caltech": "California Institute of Technology",
    "UC Berkeley": "University of California, Berkeley",
    "UCLA": "University of California, Los Angeles",
    "UC San Diego": "University of California, San Diego",
    "UC Davis": "University of California, Davis",
    "UC Santa Barbara": "University of California, Santa Barbara",
    "UC Irvine": "University of California, Irvine",
    "EPFL": "École Polytechnique Fédérale de Lausanne",
    "ETH": "ETH Zurich",
    "University College London": "UCL",
    "Ludwig Maximilian University of Munich": "LMU Munich",
    "Heidelberg University": "Universität Heidelberg",
    "LSE": "London School of Economics and Political Science",
    "UIUC": "University of Illinois at Urbana-Champaign",
    "Georgia Tech": "Georgia Institute of Technology",
    "TU Delft": "Delft University of Technology",
    "UT Austin": "University of Texas at Austin",
    "UW-Madison": "University of Wisconsin-Madison",
    "HKUST": "The Hong Kong University of Science and Technology",
    "KAIST": "Korea Advanced Institute of Science and Technology (KAIST)",
    "UNSW": "UNSW Sydney",
    "ANU": "Australian National University",
    "The Ohio State University": "Ohio State University (Main campus)",
}


def _normalize_institution_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.removeprefix("the ")


_RANK_BY_NAME = {
    _normalize_institution_name(name): rank
    for rank, name in THE_WORLD_UNIVERSITY_RANKINGS_TOP_100
}
_CANONICAL_BY_NAME = {
    _normalize_institution_name(name): name
    for _, name in THE_WORLD_UNIVERSITY_RANKINGS_TOP_100
}
for _alias, _canonical in _ALIASES.items():
    _normalized_alias = _normalize_institution_name(_alias)
    _normalized_canonical = _normalize_institution_name(_canonical)
    _RANK_BY_NAME[_normalized_alias] = _RANK_BY_NAME[_normalized_canonical]
    _CANONICAL_BY_NAME[_normalized_alias] = _canonical


def top_university_matches(
    institutions: str | Iterable[str] | None,
) -> list[tuple[str, int]]:
    """Return canonical THE top-100 matches with their published ranks."""
    if institutions is None:
        return []
    names = [institutions] if isinstance(institutions, str) else institutions

    matches: dict[str, int] = {}
    for name in names:
        if not isinstance(name, str):
            continue
        normalized = _normalize_institution_name(name)
        if rank := _RANK_BY_NAME.get(normalized):
            canonical = _CANONICAL_BY_NAME[normalized]
            matches[canonical] = min(rank, matches.get(canonical, rank))

    return sorted(matches.items(), key=lambda match: (match[1], match[0]))


__all__ = [
    "THE_WORLD_UNIVERSITY_RANKINGS_TOP_100",
    "THE_WORLD_UNIVERSITY_RANKINGS_URL",
    "THE_WORLD_UNIVERSITY_RANKINGS_YEAR",
    "top_university_matches",
]
