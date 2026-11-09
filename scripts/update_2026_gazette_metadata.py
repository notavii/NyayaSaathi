"""
Utility script to correct 2026 Amendment Gazette metadata in Nyaya Saathi.

Blueprint Phase 4C.1 Part E:
Updates G.S.R. 544(E) to official G.S.R. 789(E) across all source records,
extracted metadata, legal chunks, embedding records, and ChromaDB future_law collection.
"""

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.vector_store import VectorStoreManager, COLLECTION_FUTURE_LAW
DATA_DIR = ROOT_DIR / "data" / "legal_sources"

CATALOG_PATH = DATA_DIR / "source_catalog.json"
EXTRACTED_PATH = DATA_DIR / "extracted" / "CP_ECOMMERCE_AMENDMENT_2026_extracted.json"
CHUNKS_PATH = DATA_DIR / "legal_chunks.json"
RECORDS_PATH = DATA_DIR / "embedding_records.json"
MANIFEST_PATH = DATA_DIR / "vector_index_manifest.json"


def update_catalog():
    print("1. Updating source_catalog.json...")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    for entry in catalog.get("sources", []):
        if entry.get("document_id") == "CP_ECOMMERCE_AMENDMENT_2026":
            entry["catalog_doc_id"] = "DOC_008"
            entry["document_title"] = "Consumer Protection (E-Commerce) (Amendment) Rules, 2026"
            entry["gazette_reference"] = "G.S.R. 789(E)"
            entry["document_version"] = "Notification G.S.R. 789(E) (Gazette ID: CG-DL-E-10092026-276125)"
            entry["original_filename"] = "CP_Ecommerce_Amendment_Rules_2026_GSR_789_E.pdf"
            entry["publication_date"] = "2026-09-09"
            entry["effective_from"] = "2027-01-01"
            entry["applicability_status"] = "FUTURE_EFFECTIVE"
            entry["notes"] = (
                "IMPORTANT: Published in Official Gazette on 9 September 2026 vide Notification G.S.R. 789(E), "
                "but expressly effective from 1 January 2027 per Rule 1(2). Must be treated as FUTURE_EFFECTIVE. "
                "Any legal assistance or retrieval prior to 2027-01-01 must NOT treat these amendments as binding current law. 7 pages."
            )
            print("   -> Updated CP_ECOMMERCE_AMENDMENT_2026 in catalog.")

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)


def update_extracted():
    print("2. Updating extracted JSON...")
    if EXTRACTED_PATH.exists():
        with open(EXTRACTED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["original_filename"] = "CP_Ecommerce_Amendment_Rules_2026_GSR_789_E.pdf"
        data["gazette_reference"] = "G.S.R. 789(E)"
        data["document_version"] = "Notification G.S.R. 789(E) (Gazette ID: CG-DL-E-10092026-276125)"
        data["catalog_doc_id"] = "DOC_008"
        with open(EXTRACTED_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("   -> Updated CP_ECOMMERCE_AMENDMENT_2026_extracted.json")


def update_chunks():
    print("3. Updating legal_chunks.json...")
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    count = 0
    for chunk in chunks:
        if chunk.get("document_id") == "CP_ECOMMERCE_AMENDMENT_2026":
            chunk["original_filename"] = "CP_Ecommerce_Amendment_Rules_2026_GSR_789_E.pdf"
            chunk["gazette_reference"] = "G.S.R. 789(E)"
            chunk["document_version"] = "Notification G.S.R. 789(E) (Gazette ID: CG-DL-E-10092026-276125)"
            chunk["catalog_doc_id"] = "DOC_008"
            count += 1

    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"   -> Updated {count} chunks in legal_chunks.json")


def update_embedding_records():
    print("4. Updating embedding_records.json...")
    with open(RECORDS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    count = 0
    for rec in records:
        if rec.get("document_id") == "CP_ECOMMERCE_AMENDMENT_2026":
            rec["original_filename"] = "CP_Ecommerce_Amendment_Rules_2026_GSR_789_E.pdf"
            rec["gazette_reference"] = "G.S.R. 789(E)"
            rec["document_version"] = "Notification G.S.R. 789(E) (Gazette ID: CG-DL-E-10092026-276125)"
            rec["catalog_doc_id"] = "DOC_008"
            count += 1

    with open(RECORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"   -> Updated {count} records in embedding_records.json")


def update_chromadb():
    print("5. Upserting ChromaDB future_law collection metadata...")
    vm = VectorStoreManager()
    coll = vm.client.get_collection(COLLECTION_FUTURE_LAW)
    existing = coll.get(include=["metadatas", "documents"])

    ids = existing["ids"]
    metas = existing["metadatas"]
    docs = existing["documents"]

    updated_metas = []
    for m in metas:
        m["original_filename"] = "CP_Ecommerce_Amendment_Rules_2026_GSR_789_E.pdf"
        m["gazette_reference"] = "G.S.R. 789(E)"
        m["document_version"] = "Notification G.S.R. 789(E) (Gazette ID: CG-DL-E-10092026-276125)"
        m["catalog_doc_id"] = "DOC_008"
        updated_metas.append(m)

    coll.update(ids=ids, metadatas=updated_metas)
    print(f"   -> Successfully updated metadata for all {len(ids)} future_law records in ChromaDB.")


def update_manifest():
    print("6. Updating vector_index_manifest.json...")
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["gazette_reference_2026"] = "G.S.R. 789(E)"
        manifest["version"] = "1.2.0"
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print("   -> Updated vector_index_manifest.json")


if __name__ == "__main__":
    update_catalog()
    update_extracted()
    update_chunks()
    update_embedding_records()
    update_chromadb()
    update_manifest()
    print("\nALL 2026 GAZETTE METADATA UPDATES COMPLETE.")
