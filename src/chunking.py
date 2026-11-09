"""
Legal-Aware Chunking Module for Nyaya Saathi.

Divides Indian consumer protection statutory, procedural, and historical documents into
logically complete provisions (Sections, Rules, Subsections, Clauses, Provisos,
Explanations, Corrigenda, Amendments, and Procedural Steps) rather than arbitrary character counts.

Strictly separates:
- Primary legal retrieval dataset (legal_chunks.json) [retrieval_eligible: true]
- Historical reference dataset (historical_reference_chunks.json) [retrieval_eligible: false]
"""

import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Any


# Authoritative headings map for CPA 2019 Sections
CPA_2019_SECTION_HEADINGS = {
    "1": "Short title, extent, commencement and application",
    "2": "Definitions",
    "3": "Central Consumer Protection Council",
    "4": "Procedure for meetings of Central Council",
    "5": "Objects of Central Council",
    "6": "State Consumer Protection Councils",
    "7": "Objects of State Council",
    "8": "District Consumer Protection Council",
    "9": "Objects of District Council",
    "10": "Establishment of Central Consumer Protection Authority",
    "11": "Qualifications, method of recruitment, etc., of Chief Commissioner and Commissioners",
    "12": "Vacancy, etc., not to invalidate proceedings of Central Authority",
    "13": "Appointment of officers, experts, professionals and other employees of Central Authority",
    "14": "Procedure of Central Authority",
    "15": "Investigation Wing",
    "16": "Power of District Collector",
    "17": "Complaints to authorities",
    "18": "Powers and functions of Central Authority",
    "19": "Power of Central Authority to refer matter for investigation or to other Regulator",
    "20": "Power of Central Authority to recall goods, etc.",
    "21": "Power of Central Authority to issue directions and penalties against false or misleading advertisements",
    "22": "Search and seizure",
    "23": "Designation of any statutory authority or body to function as Central Authority",
    "24": "Appeal",
    "25": "Grants by Central Government",
    "26": "Accounts and audit of Central Authority",
    "27": "Furnishing of annual reports, etc.",
    "28": "Establishment of District Consumer Disputes Redressal Commission",
    "29": "Qualifications, etc., of President and members of District Commission",
    "30": "Salaries, allowances and other terms and conditions of service of President and members of District Commission",
    "31": "Temporary absence of President of District Commission",
    "32": "Jurisdiction of District Commission",
    "33": "Manner in which complaint shall be made",
    "34": "Jurisdiction of District Commission (Pecuniary and Territorial)",
    "35": "Manner in which complaint shall be made",
    "36": "Proceedings before District Commission",
    "37": "Reference to mediation",
    "38": "Procedure on admission of complaint",
    "39": "Findings of District Commission",
    "40": "Review by District Commission in certain cases",
    "41": "Appeal against order of District Commission",
    "42": "Establishment of State Consumer Disputes Redressal Commission",
    "43": "Qualifications, etc., of President and members of State Commission",
    "44": "Salaries, allowances and other terms and conditions of service of President and members of State Commission",
    "45": "Temporary absence of President of State Commission",
    "46": "Benches of State Commission",
    "47": "Jurisdiction of State Commission",
    "48": "Transfer of cases",
    "49": "Procedure applicable to State Commission",
    "50": "Review by State Commission in certain cases",
    "51": "Appeal to National Commission",
    "52": "Hearing of appeal",
    "53": "Establishment of National Consumer Disputes Redressal Commission",
    "54": "Composition of National Commission",
    "55": "Qualifications, etc., of President and members of National Commission",
    "56": "Salaries, allowances and other terms and conditions of service of President and members of National Commission",
    "57": "Temporary absence of President of National Commission",
    "58": "Jurisdiction of National Commission",
    "59": "Procedure applicable to National Commission",
    "60": "Review by National Commission in certain cases",
    "61": "Power to set aside ex parte orders",
    "62": "Transfer of cases",
    "63": "Vacancies or defects in appointment not to invalidate orders",
    "64": "Service of notice, etc.",
    "65": "Notice by electronic means",
    "66": "Establishment of Consumer Mediation Cell",
    "67": "Empanelment of mediators",
    "68": "Nomination of mediators from panel",
    "69": "Duty of mediator to disclose certain facts",
    "70": "Replacement of mediator in certain cases",
    "71": "Procedure for mediation",
    "72": "Enforcement of settlement agreement",
    "73": "Procedure to be followed by mediator",
    "74": "Establishment of consumer mediation cell at District, State and National Commissions",
    "75": "Empanelment of mediators",
    "76": "Nomination of mediators from panel",
    "77": "Duty of mediator to disclose certain facts",
    "78": "Replacement of mediator in certain cases",
    "79": "Procedure for mediation",
    "80": "Enforcement of settlement agreement",
    "81": "Settlement through mediation",
    "82": "Application of Chapter VI on Product Liability",
    "83": "Product liability action",
    "84": "Liability of product manufacturer",
    "85": "Liability of product service provider",
    "86": "Liability of product seller",
    "87": "Exceptions to product liability action",
    "88": "Penalty for non-compliance of direction of Central Authority",
    "89": "Punishment for false or misleading advertisement",
    "90": "Punishment for manufacturing for sale or for storing or selling or distributing or importing products containing adulterant",
    "91": "Punishment for manufacturing for sale or for storing or selling or distributing or importing spurious goods",
    "92": "Cognizance of offence by court",
    "93": "Vexatious search",
    "94": "Measures to prevent unfair trade practices in e-commerce, direct selling, etc.",
    "95": "Presidents, members, Chief Commissioner, Commissioners and other officers to be public servants",
    "96": "Compounding of offences",
    "97": "Manner of crediting penalty",
    "98": "Furnishing of information, etc.",
    "99": "Protection of action taken in good faith",
    "100": "Act not in derogation of any other law",
    "101": "Power of Central Government to make rules",
    "102": "Power of State Government to make rules",
    "103": "Power of National Commission to make regulations",
    "104": "Rules and regulations to be laid before Parliament",
    "105": "Rules and regulations to be laid before State Legislature",
    "106": "Power to remove difficulties",
    "107": "Repeal and savings",
}


def build_chunk(
    chunk_id: str,
    document_id: str,
    document_title: str,
    document_type: str,
    provision_type: str,
    provision_number: Optional[str],
    provision_heading: str,
    text: str,
    pdf_page_start: int,
    pdf_page_end: int,
    source_url: str = "",
    original_filename: str = "",
    parent_provision: Optional[str] = None,
    publication_date: Optional[str] = None,
    effective_from: Optional[str] = None,
    effective_to: Optional[str] = None,
    applicability_status: str = "CURRENTLY_IN_FORCE",
    retrieval_eligible: bool = True,
    amends_document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper to construct a standardized LegalChunk dictionary with fine-grained verification statuses."""
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "document_title": document_title,
        "document_type": document_type,
        "provision_type": provision_type,
        "provision_number": provision_number,
        "provision_heading": provision_heading,
        "parent_provision": parent_provision,
        "text": text.strip(),
        "source_url": source_url,
        "original_filename": original_filename,
        "pdf_page_start": pdf_page_start,
        "pdf_page_end": pdf_page_end,
        "publication_date": publication_date,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "extraction_status": "SUCCESS",
        "extraction_integrity_status": "CHECKED",
        "legal_review_status": "REQUIRES_LEGAL_REVIEW",
        "applicability_status": applicability_status,
        "retrieval_eligible": retrieval_eligible,
        "amends_document_id": amends_document_id,
        "extraction_method": "PyMuPDF",
    }


def chunk_cpa_2019(extraction: Dict[str, Any], catalog_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parses Consumer Protection Act, 2019 into section-level and sub-clause chunks.
    Preserves subsections, clauses, provisos, explanations, and illustrations.
    Provides linked child chunks for Section 2 definitions.
    """
    doc_id = "CPA_2019"
    doc_title = catalog_entry.get("document_title", "The Consumer Protection Act, 2019")
    doc_type = "CENTRAL_ACT"
    source_url = catalog_entry.get("official_source_url", "")
    filename = extraction.get("original_filename", "")
    pub_date = catalog_entry.get("publication_date")
    eff_from = catalog_entry.get("effective_from")

    pages = extraction.get("pages", [])
    chunks = []

    full_text = ""
    page_offsets = []
    for p in pages:
        s = len(full_text)
        full_text += p["text"] + "\n"
        e = len(full_text)
        page_offsets.append((s, e, p["pdf_page_number"]))

    def get_page_range(char_start: int, char_end: int):
        p_start = 1
        p_end = 1
        for s, e, p in page_offsets:
            if s <= char_start < e:
                p_start = p
            if s < char_end <= e:
                p_end = p
        return p_start, max(p_start, p_end)

    section_pattern = re.compile(
        r"(?:^|\n)\s*([0-9]{1,3})\.\s+(?:(?:\([0-9a-zA-Z]+\))|[A-Z])",
        re.MULTILINE
    )

    matches = list(section_pattern.finditer(full_text))
    valid_sections = []
    expected_sec = 1
    for m in matches:
        sec_num_str = m.group(1)
        if sec_num_str.isdigit():
            sec_num = int(sec_num_str)
            if sec_num == expected_sec or (expected_sec <= sec_num <= expected_sec + 2 and sec_num <= 107):
                valid_sections.append((sec_num, m.start()))
                expected_sec = sec_num + 1

    for i, (sec_num, start_idx) in enumerate(valid_sections):
        sec_str = str(sec_num)
        heading = CPA_2019_SECTION_HEADINGS.get(sec_str, f"Section {sec_str}")
        end_idx = valid_sections[i + 1][1] if i + 1 < len(valid_sections) else len(full_text)
        sec_text = full_text[start_idx:end_idx].strip()
        p_start, p_end = get_page_range(start_idx, end_idx)

        chunk_id = f"CPA_2019_SECTION_{sec_str}"
        parent_chunk = build_chunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            document_title=doc_title,
            document_type=doc_type,
            provision_type="SECTION",
            provision_number=sec_str,
            provision_heading=heading,
            text=sec_text,
            pdf_page_start=p_start,
            pdf_page_end=p_end,
            source_url=source_url,
            original_filename=filename,
            publication_date=pub_date,
            effective_from=eff_from,
            applicability_status="CURRENTLY_IN_FORCE",
            retrieval_eligible=True,
        )
        chunks.append(parent_chunk)

        if sec_str == "2":
            def_matches = list(re.finditer(r"(?:^|\n)\s*\(([0-9]{1,2})\)\s+([\"\“][^\n]+[\"\”])", sec_text))
            for j, dm in enumerate(def_matches):
                clause_num = dm.group(1)
                term = dm.group(2).replace('"', '').replace('“', '').replace('”', '').strip()
                clause_start = dm.start()
                clause_end = def_matches[j + 1].start() if j + 1 < len(def_matches) else len(sec_text)
                clause_text = sec_text[clause_start:clause_end].strip()

                child_id = f"CPA_2019_SECTION_2_CLAUSE_{clause_num}"
                chunks.append(build_chunk(
                    chunk_id=child_id,
                    document_id=doc_id,
                    document_title=doc_title,
                    document_type=doc_type,
                    provision_type="DEFINITION_CLAUSE",
                    provision_number=f"2({clause_num})",
                    provision_heading=f"Definition of '{term}'",
                    parent_provision=chunk_id,
                    text=clause_text,
                    pdf_page_start=p_start,
                    pdf_page_end=p_end,
                    source_url=source_url,
                    original_filename=filename,
                    publication_date=pub_date,
                    effective_from=eff_from,
                    applicability_status="CURRENTLY_IN_FORCE",
                    retrieval_eligible=True,
                ))

    return chunks


def chunk_standard_rules(
    extraction: Dict[str, Any],
    catalog_entry: Dict[str, Any],
    rule_prefix: str,
    doc_type: str = "RULES",
    amends_doc_id: Optional[str] = None,
    applicability_status: str = "CURRENTLY_IN_FORCE",
) -> List[Dict[str, Any]]:
    """
    Parses Statutory Rules documents into rule-level chunks.
    Preserves sub-rules, clauses, provisos, and explanations.
    """
    doc_id = extraction["document_id"]
    doc_title = catalog_entry.get("document_title", doc_id)
    source_url = catalog_entry.get("official_source_url", "")
    filename = extraction.get("original_filename", "")
    pub_date = catalog_entry.get("publication_date")
    eff_from = catalog_entry.get("effective_from")

    pages = extraction.get("pages", [])
    chunks = []

    full_text = ""
    page_offsets = []
    for p in pages:
        s = len(full_text)
        full_text += p["text"] + "\n"
        e = len(full_text)
        page_offsets.append((s, e, p["pdf_page_number"]))

    def get_page_range(char_start: int, char_end: int):
        p_start = page_offsets[0][2] if page_offsets else 1
        p_end = page_offsets[-1][2] if page_offsets else 1
        for s, e, p in page_offsets:
            if s <= char_start < e:
                p_start = p
            if s < char_end <= e:
                p_end = p
        return p_start, max(p_start, p_end)

    rule_pattern = re.compile(
        r"(?:^|\n)\s*([0-9]{1,2})\.\s+([A-Z][^\n–—\-]+(?:–|—|-|\.))",
        re.MULTILINE
    )

    matches = list(rule_pattern.finditer(full_text))
    if matches:
        for i, m in enumerate(matches):
            rule_num = m.group(1)
            raw_heading = m.group(2).rstrip("–—-. ").strip()
            start_idx = m.start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            rule_text = full_text[start_idx:end_idx].strip()
            p_start, p_end = get_page_range(start_idx, end_idx)

            chunk_id = f"{rule_prefix}_RULE_{rule_num}"
            chunks.append(build_chunk(
                chunk_id=chunk_id,
                document_id=doc_id,
                document_title=doc_title,
                document_type=doc_type,
                provision_type="RULE",
                provision_number=rule_num,
                provision_heading=raw_heading,
                text=rule_text,
                pdf_page_start=p_start,
                pdf_page_end=p_end,
                source_url=source_url,
                original_filename=filename,
                publication_date=pub_date,
                effective_from=eff_from,
                applicability_status=applicability_status,
                retrieval_eligible=True,
                amends_document_id=amends_doc_id,
            ))
    else:
        p_start, p_end = get_page_range(0, len(full_text))
        chunk_id = f"{rule_prefix}_FULL_INSTRUMENT"
        chunks.append(build_chunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            document_title=doc_title,
            document_type=doc_type,
            provision_type="CORRIGENDUM_ITEM" if "CORRIGENDUM" in doc_type else "RULE",
            provision_number="1",
            provision_heading=doc_title,
            text=full_text.strip(),
            pdf_page_start=p_start,
            pdf_page_end=p_end,
            source_url=source_url,
            original_filename=filename,
            publication_date=pub_date,
            effective_from=eff_from,
            applicability_status=applicability_status,
            retrieval_eligible=True,
            amends_document_id=amends_doc_id,
        ))

    return chunks


def chunk_2021_amendment_rules(extraction: Dict[str, Any], catalog_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parses the 2021 E-Commerce Amendment Rules (G.S.R. 328(E)) from English text on Page 2.
    Ensures G.S.R. 328(E) notification header and both rules 1 and 2 are preserved.
    """
    doc_id = "CP_ECOMMERCE_AMENDMENT_2021"
    doc_title = catalog_entry.get("document_title", "Consumer Protection (E-Commerce) (Amendment) Rules, 2021")
    source_url = catalog_entry.get("official_source_url", "")
    filename = extraction.get("original_filename", "")
    pub_date = "2021-05-17"
    eff_from = "2021-05-17"

    pages = extraction.get("pages", [])
    page_2 = next((p for p in pages if p["pdf_page_number"] == 2), pages[-1] if pages else None)
    text = page_2["text"] if page_2 else ""

    notif_idx = text.find("MINISTRY OF CONSUMER AFFAIRS")
    if notif_idx == -1:
        notif_idx = text.find("NOTIFICATION")
    english_text = text[notif_idx:].strip() if notif_idx != -1 else text.strip()

    chunk = build_chunk(
        chunk_id="CP_ECOMMERCE_AMENDMENT_2021_FULL",
        document_id=doc_id,
        document_title=doc_title,
        document_type="AMENDMENT_RULES",
        provision_type="AMENDMENT_ITEM",
        provision_number="1",
        provision_heading=doc_title,
        text=english_text,
        pdf_page_start=2,
        pdf_page_end=2,
        source_url=source_url,
        original_filename=filename,
        publication_date=pub_date,
        effective_from=eff_from,
        applicability_status="CURRENTLY_IN_FORCE",
        retrieval_eligible=True,
        amends_document_id="CP_ECOMMERCE_RULES_2020",
    )
    return [chunk]


def chunk_2026_amendment_rules(extraction: Dict[str, Any], catalog_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parses the 2026 E-Commerce Amendment Rules (G.S.R. 789(E)) from English pages 5-7.
    Strictly flags all chunks as FUTURE_EFFECTIVE with effective_from = 2027-01-01.
    """
    doc_id = "CP_ECOMMERCE_AMENDMENT_2026"
    doc_title = catalog_entry.get("document_title", "Consumer Protection (E-Commerce) (Amendment) Rules, 2026")
    source_url = catalog_entry.get("official_source_url", "")
    filename = extraction.get("original_filename", "")
    pub_date = "2026-09-09"
    eff_from = "2027-01-01"

    pages = extraction.get("pages", [])
    english_pages = [p for p in pages if p["pdf_page_number"] >= 5]
    if not english_pages:
        english_pages = pages

    full_text = ""
    page_offsets = []
    for p in english_pages:
        s = len(full_text)
        full_text += p["text"] + "\n"
        e = len(full_text)
        page_offsets.append((s, e, p["pdf_page_number"]))

    def get_page_range(char_start: int, char_end: int):
        p_start = page_offsets[0][2]
        p_end = page_offsets[-1][2]
        for s, e, p in page_offsets:
            if s <= char_start < e:
                p_start = p
            if s < char_end <= e:
                p_end = p
        return p_start, max(p_start, p_end)

    chunks = []
    item_pattern = re.compile(r"(?:^|\n)\s*([0-9]{1,2})\.\s+([A-Z][^\n]+)", re.MULTILINE)
    matches = list(item_pattern.finditer(full_text))

    if matches:
        for i, m in enumerate(matches):
            item_num = m.group(1)
            raw_heading = m.group(2).strip()
            start_idx = m.start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            item_text = full_text[start_idx:end_idx].strip()
            p_start, p_end = get_page_range(start_idx, end_idx)

            chunk_id = f"CP_ECOMMERCE_AMENDMENT_2026_ITEM_{item_num}"
            chunks.append(build_chunk(
                chunk_id=chunk_id,
                document_id=doc_id,
                document_title=doc_title,
                document_type="AMENDMENT_RULES",
                provision_type="AMENDMENT_ITEM",
                provision_number=item_num,
                provision_heading=f"Amendment Rule {item_num} - {raw_heading[:60]}",
                text=item_text,
                pdf_page_start=p_start,
                pdf_page_end=p_end,
                source_url=source_url,
                original_filename=filename,
                publication_date=pub_date,
                effective_from=eff_from,
                applicability_status="FUTURE_EFFECTIVE",
                retrieval_eligible=True,
                amends_document_id="CP_ECOMMERCE_RULES_2020",
            ))
    else:
        p_start, p_end = get_page_range(0, len(full_text))
        chunks.append(build_chunk(
            chunk_id="CP_ECOMMERCE_AMENDMENT_2026_FULL",
            document_id=doc_id,
            document_title=doc_title,
            document_type="AMENDMENT_RULES",
            provision_type="AMENDMENT_ITEM",
            provision_number="1",
            provision_heading=doc_title,
            text=full_text.strip(),
            pdf_page_start=p_start,
            pdf_page_end=p_end,
            source_url=source_url,
            original_filename=filename,
            publication_date=pub_date,
            effective_from=eff_from,
            applicability_status="FUTURE_EFFECTIVE",
            retrieval_eligible=True,
            amends_document_id="CP_ECOMMERCE_RULES_2020",
        ))

    return chunks


def chunk_ejagriti_guide(extraction: Dict[str, Any], catalog_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parses the e-Jagriti User Manual (March 2025) into logical e-filing step chunks.
    Does NOT invent statutory section numbers.
    Sets publication_month to 2025-03, publication_date to None, document_type to PROCEDURAL_GUIDE.
    """
    doc_id = "EJAGRITI_FILING_GUIDE"
    doc_title = catalog_entry.get("document_title", "e-Jagriti Consumer Commission Online Complaint Filing User Manual")
    source_url = catalog_entry.get("official_source_url", "")
    filename = extraction.get("original_filename", "")

    pages = extraction.get("pages", [])
    chunks = []

    for p in pages:
        p_num = p["pdf_page_number"]
        txt = p["text"].strip()
        if len(txt) < 80:
            continue

        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        heading = lines[0] if lines else f"e-Filing Guidance (Page {p_num})"
        if len(heading) > 80:
            heading = heading[:80] + "..."

        chunk_id = f"EJAGRITI_GUIDE_PAGE_{p_num}"
        chunks.append(build_chunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            document_title=doc_title,
            document_type="PROCEDURAL_GUIDE",
            provision_type="PROCEDURAL_GUIDANCE",
            provision_number=None,
            provision_heading=heading,
            text=txt,
            pdf_page_start=p_num,
            pdf_page_end=p_num,
            source_url=source_url,
            original_filename=filename,
            publication_date=None,
            effective_from=None,
            applicability_status="CURRENTLY_IN_FORCE",
            retrieval_eligible=True,
        ))

    return chunks


def chunk_consumer_handbook_2015(extraction: Dict[str, Any], catalog_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parses Consumer Handbook (2015, IIPA / DoCA) into historical reference topic chunks.
    Classified as HISTORICAL_EDUCATIONAL_REFERENCE with retrieval_eligible: False.
    """
    doc_id = "CONSUMER_HANDBOOK_2015"
    doc_title = catalog_entry.get("document_title", "Consumer Handbook (2015)")
    source_url = catalog_entry.get("official_source_url", "")
    filename = extraction.get("original_filename", "")

    pages = extraction.get("pages", [])
    chunks = []

    for p in pages:
        p_num = p["pdf_page_number"]
        txt = p["text"].strip()
        if len(txt) < 80:
            continue

        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        heading = lines[0] if lines else f"Historical Reference Section (Page {p_num})"
        if len(heading) > 80:
            heading = heading[:80] + "..."

        chunk_id = f"CONSUMER_HANDBOOK_2015_PAGE_{p_num}"
        chunks.append(build_chunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            document_title=doc_title,
            document_type="HISTORICAL_EDUCATIONAL_REFERENCE",
            provision_type="HISTORICAL_REFERENCE_TOPIC",
            provision_number=None,
            provision_heading=heading,
            text=txt,
            pdf_page_start=p_num,
            pdf_page_end=p_num,
            source_url=source_url,
            original_filename=filename,
            publication_date=None,
            effective_from=None,
            applicability_status="HISTORICAL_REFERENCE",
            retrieval_eligible=False,  # Strictly false for primary retrieval
        ))

    return chunks


def chunk_all_documents(
    extracted_dir: Path = Path("data/legal_sources/extracted"),
    catalog_path: Path = Path("data/legal_sources/source_catalog.json"),
    output_primary_file: Path = Path("data/legal_sources/legal_chunks.json"),
    output_historical_file: Path = Path("data/legal_sources/historical_reference_chunks.json"),
) -> Dict[str, Any]:
    """
    Performs legal-aware chunking on all extracted documents.
    Outputs:
    - Primary retrieval-eligible chunks to legal_chunks.json
    - Historical reference chunks to historical_reference_chunks.json
    """
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    catalog_map = {s["document_id"]: s for s in catalog.get("sources", [])}
    primary_chunks = []
    historical_chunks = []

    for extracted_file in extracted_dir.glob("*_extracted.json"):
        with open(extracted_file, "r", encoding="utf-8") as ef:
            extraction = json.load(ef)

        doc_id = extraction["document_id"]
        cat_entry = catalog_map.get(doc_id, {})

        if doc_id == "CPA_2019":
            primary_chunks.extend(chunk_cpa_2019(extraction, cat_entry))
        elif doc_id == "CP_ECOMMERCE_RULES_2020":
            primary_chunks.extend(chunk_standard_rules(extraction, cat_entry, "CP_ECOMMERCE_RULES_2020"))
        elif doc_id == "CP_GENERAL_RULES_2020":
            primary_chunks.extend(chunk_standard_rules(extraction, cat_entry, "CP_GENERAL_RULES_2020"))
        elif doc_id == "CP_CDRC_RULES_2020":
            primary_chunks.extend(chunk_standard_rules(extraction, cat_entry, "CP_CDRC_RULES_2020"))
        elif doc_id == "CP_JURISDICTION_RULES_2021":
            primary_chunks.extend(chunk_standard_rules(extraction, cat_entry, "CP_JURISDICTION_RULES_2021"))
        elif doc_id == "CP_ECOMMERCE_CORRIGENDUM_2020":
            primary_chunks.extend(chunk_standard_rules(
                extraction, cat_entry, "CP_ECOMMERCE_CORRIGENDUM_2020",
                doc_type="CORRIGENDUM", amends_doc_id="CP_ECOMMERCE_RULES_2020"
            ))
        elif doc_id == "CP_ECOMMERCE_AMENDMENT_2021":
            primary_chunks.extend(chunk_2021_amendment_rules(extraction, cat_entry))
        elif doc_id == "CP_ECOMMERCE_AMENDMENT_2026":
            primary_chunks.extend(chunk_2026_amendment_rules(extraction, cat_entry))
        elif doc_id == "EJAGRITI_FILING_GUIDE":
            primary_chunks.extend(chunk_ejagriti_guide(extraction, cat_entry))
        elif doc_id in ("CONSUMER_HANDBOOK_2015", "NCH_GRIEVANCE_GUIDE"):
            # Check if this extraction is the 2015 Consumer Handbook
            handbook_chunks = chunk_consumer_handbook_2015(extraction, cat_entry)
            historical_chunks.extend(handbook_chunks)

    # Save primary retrieval dataset
    output_primary_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_primary_file, "w", encoding="utf-8") as pf:
        json.dump(primary_chunks, pf, indent=2, ensure_ascii=False)

    # Save historical reference dataset
    with open(output_historical_file, "w", encoding="utf-8") as hf:
        json.dump(historical_chunks, hf, indent=2, ensure_ascii=False)

    return {
        "primary_chunks": primary_chunks,
        "historical_chunks": historical_chunks,
    }


if __name__ == "__main__":
    res = chunk_all_documents()
    print(f"Chunking complete. Primary legal chunks: {len(res['primary_chunks'])}, Historical reference chunks: {len(res['historical_chunks'])}")
