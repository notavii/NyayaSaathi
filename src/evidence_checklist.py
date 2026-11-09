"""
Dynamic Document and Evidence Checklist Module for Nyaya Saathi.

Authoritative Specification: Blueprint Step 24 & Intelligent Legal Companion MVP.

Dynamically derives, categorizes, and tracks case-specific document and evidence requirements.
Strictly distinguishes:
1. REQUIRED_OFFICIAL_PROCEDURE: Compulsory under an identified official procedural guide (e.g. e-Jagriti manual).
2. CONDITIONALLY_REQUIRED: Required only under specific conditions (e.g. Vakalatnama only if represented by advocate; expert lab report only if defect requires chemical/technical testing under Sec 38(2)(c)).
3. RECOMMENDED_EVIDENCE: Supporting documents to substantiate material facts (invoices, photos, packaging, communications).
4. NOT_YET_ESTABLISHED: Where official procedural guidance does not clearly establish compulsory status.

Never calls an item legally mandatory merely because it is commonly used.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("evidence_checklist")

# Document Classification Constants
CLASS_REQUIRED_PROCEDURE = "REQUIRED_OFFICIAL_PROCEDURE"
CLASS_CONDITIONALLY_REQUIRED = "CONDITIONALLY_REQUIRED"
CLASS_RECOMMENDED_EVIDENCE = "RECOMMENDED_EVIDENCE"
CLASS_NOT_ESTABLISHED = "NOT_YET_ESTABLISHED"

VALID_CLASSIFICATIONS = {
    CLASS_REQUIRED_PROCEDURE,
    CLASS_CONDITIONALLY_REQUIRED,
    CLASS_RECOMMENDED_EVIDENCE,
    CLASS_NOT_ESTABLISHED,
}

# User Status Constants
STATUS_AVAILABLE = "Available"
STATUS_MISSING = "Missing"
STATUS_TO_COLLECT = "To be collected"
STATUS_NOT_APPLICABLE = "Not applicable"

VALID_STATUSES = {
    STATUS_AVAILABLE,
    STATUS_MISSING,
    STATUS_TO_COLLECT,
    STATUS_NOT_APPLICABLE,
}


def generate_case_evidence_checklist(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Dynamically generates a tailored document and evidence checklist based on active case facts:
    - Issue category (defective goods, wrong item, non-delivery, refund refusal, service deficiency, etc.)
    - Transaction context (e-commerce marketplace vs direct seller)
    - Parties involved (seller, marketplace platform)
    - Existing evidence already gathered
    - Procedural requirements (e-Jagriti online complaint filing)
    """
    category = (case.get("issue_category") or "").lower()
    platform = case.get("marketplace_or_platform") or case.get("seller_or_platform") or ""
    product = case.get("product_or_service") or ""
    user_evidence = case.get("evidence", [])
    ev_items_lower = [str(e.get("item", "")).lower() for e in user_evidence]

    checklist: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # A. REQUIRED BY AN IDENTIFIED OFFICIAL PROCEDURE (e-Jagriti Filing Manual)
    # -------------------------------------------------------------------------
    # 1. Complainant Identity and Address Proof
    checklist.append({
        "id": "doc_complainant_id_address",
        "name": "Complainant Identity & Address Proof",
        "classification": CLASS_REQUIRED_PROCEDURE,
        "classification_label": "Required by Official Procedure",
        "condition": "Mandatory for all e-Jagriti online consumer complaint registrations.",
        "relevance": "Establishes complainant legal standing, age eligibility, and residential jurisdiction under CPA 2019 Section 34 / Section 35.",
        "source": "e-Jagriti Online Complaint Filing User Manual (March 2025), Step 1 (Party Details)",
        "source_url": "https://e-jagriti.gov.in/",
        "status": STATUS_TO_COLLECT,
        "user_notes": "",
    })

    # 2. Formal Complaint Petition with Verification / Affidavit
    checklist.append({
        "id": "doc_complaint_affidavit",
        "name": "Formal Complaint Petition & Verification Affidavit",
        "classification": CLASS_REQUIRED_PROCEDURE,
        "classification_label": "Required by Official Procedure",
        "condition": "Mandatory for formal admission before District, State, or National Consumer Commission.",
        "relevance": "Sets forth the sworn statement of facts, timeline of grievance, defect/deficiency details, and relief claimed.",
        "source": "e-Jagriti Online Complaint Filing User Manual (March 2025), Step 3 (Complaint Details & Uploads)",
        "source_url": "https://e-jagriti.gov.in/",
        "status": STATUS_TO_COLLECT,
        "user_notes": "",
    })

    # -------------------------------------------------------------------------
    # B. CONDITIONALLY REQUIRED
    # -------------------------------------------------------------------------
    # 3. Vakalatnama
    checklist.append({
        "id": "doc_vakalatnama",
        "name": "Vakalatnama (Advocate Representation Authorisation)",
        "classification": CLASS_CONDITIONALLY_REQUIRED,
        "classification_label": "Conditionally Required",
        "condition": "Required ONLY if represented by an advocate/lawyer before the Commission. NOT required when the consumer files or appears in person (party-in-person).",
        "relevance": "Confers legal authority upon an advocate to appear, plead, and act on the complainant's behalf.",
        "source": "e-Jagriti Online Complaint Filing User Manual (March 2025), Document Upload Index",
        "source_url": "https://e-jagriti.gov.in/",
        "status": STATUS_NOT_APPLICABLE,
        "user_notes": "Not needed if filing in person without an advocate.",
    })

    # 4. Expert Technical / Laboratory Test Report (for defect disputes)
    if any(k in category for k in ["defect", "damage", "fault", "broken", "quality"]):
        checklist.append({
            "id": "doc_expert_lab_report",
            "name": "Expert Technical / Laboratory Analysis Report",
            "classification": CLASS_CONDITIONALLY_REQUIRED,
            "classification_label": "Conditionally Required",
            "condition": "Required under Section 38(2)(c) of CPA 2019 ONLY if the defect cannot be determined without technical, mechanical, or chemical testing.",
            "relevance": "Provides authoritative laboratory evidence that the goods suffer from an inherent manufacturing fault or fail statutory standards.",
            "source": "Consumer Protection Act, 2019, Section 38(2)(c)",
            "source_url": "https://consumeraffairs.nic.in/sites/default/files/CP%20Act%202019.pdf",
            "status": STATUS_NOT_APPLICABLE,
            "user_notes": "Usually ordered by Commission or obtained from accredited test laboratory if disputed by manufacturer.",
        })

    # 5. Pre-Litigation Legal Notice & Postal Proof of Delivery
    checklist.append({
        "id": "doc_legal_notice",
        "name": "Pre-Litigation Legal Notice & Postal Acknowledgment / Delivery Slip",
        "classification": CLASS_CONDITIONALLY_REQUIRED,
        "classification_label": "Conditionally Required",
        "condition": "Required only if a formal statutory demand notice was issued by an advocate prior to filing.",
        "relevance": "Proves the opposite party was afforded explicit notice and opportunity to cure before legal proceedings commenced.",
        "source": "Consumer Commission Procedural Practice",
        "source_url": "https://consumeraffairs.nic.in",
        "status": STATUS_NOT_APPLICABLE,
        "user_notes": "Optional pre-litigation step; not mandatory for e-Jagriti filing.",
    })

    # -------------------------------------------------------------------------
    # C. RECOMMENDED SUPPORTING EVIDENCE
    # -------------------------------------------------------------------------
    # 6. Tax Invoice / Retail Cash Memo
    has_invoice = any("invoice" in ev or "receipt" in ev or "bill" in ev for ev in ev_items_lower)
    checklist.append({
        "id": "doc_invoice_receipt",
        "name": "Tax Invoice / Retail Bill / Cash Memo",
        "classification": CLASS_RECOMMENDED_EVIDENCE,
        "classification_label": "Recommended Supporting Evidence",
        "condition": "Recommended for all transaction disputes.",
        "relevance": "Establishes purchase price paid, transaction date, serial/model number, and seller GSTIN/identity under CPA 2019 Section 2(7).",
        "source": "Consumer Protection Act, 2019, Section 2(7) & E-Commerce Rules, 2020, Rule 5(3)",
        "source_url": "https://consumeraffairs.nic.in",
        "status": STATUS_AVAILABLE if has_invoice else STATUS_TO_COLLECT,
        "user_notes": "Preserve original PDF invoice from app/email.",
    })

    # 7. Order Confirmation & E-Commerce Listing Details
    if platform or any(k in category for k in ["e-commerce", "wrong", "delivery", "order", "flipkart", "amazon", "myntra"]):
        checklist.append({
            "id": "doc_order_confirmation",
            "name": "Order Confirmation Email & Platform Order Summary Screenshot",
            "classification": CLASS_RECOMMENDED_EVIDENCE,
            "classification_label": "Recommended Supporting Evidence",
            "condition": "Applicable for orders placed on e-commerce platforms.",
            "relevance": "Proves the contractual description of goods ordered, delivery address, promised delivery date, and marketplace terms.",
            "source": "Consumer Protection (E-Commerce) Rules, 2020, Rule 5(3)(c)",
            "source_url": "https://consumeraffairs.nic.in/sites/default/files/E-commerce%20Rules.pdf",
            "status": STATUS_TO_COLLECT,
            "user_notes": "Take screenshot of order details page showing tracking and seller name.",
        })

    # 8. Payment Proof / Bank Statement / UPI Transaction Record
    checklist.append({
        "id": "doc_payment_proof",
        "name": "Payment Proof / Bank Statement / UPI Transaction ID",
        "classification": CLASS_RECOMMENDED_EVIDENCE,
        "classification_label": "Recommended Supporting Evidence",
        "condition": "Recommended for verifying payment debit.",
        "relevance": "Corroborates that valuable consideration was paid for the goods/services under CPA 2019 Section 2(7).",
        "source": "Consumer Protection Act, 2019, Section 2(7)",
        "source_url": "https://consumeraffairs.nic.in",
        "status": STATUS_TO_COLLECT,
        "user_notes": "Download bank statement page or payment gateway debit receipt.",
    })

    # 9. Photographs / Unboxing Video of Defective or Wrong Item
    if any(k in category for k in ["defect", "damage", "wrong", "incorrect", "broken", "mobile", "shoe", "laptop"]):
        has_photo = any("photo" in ev or "video" in ev or "picture" in ev or "image" in ev for ev in ev_items_lower)
        checklist.append({
            "id": "doc_photos_unboxing_video",
            "name": "Photographs & Unboxing Video of Delivered Item",
            "classification": CLASS_RECOMMENDED_EVIDENCE,
            "classification_label": "Recommended Supporting Evidence",
            "condition": "Recommended when goods are delivered damaged, cracked, broken, or incorrect.",
            "relevance": "Provides direct factual evidence of physical defect, damage, or discrepancy from the item ordered under Rule 6(3).",
            "source": "Consumer Protection (E-Commerce) Rules, 2020, Rule 6(3)",
            "source_url": "https://consumeraffairs.nic.in/sites/default/files/E-commerce%20Rules.pdf",
            "status": STATUS_AVAILABLE if has_photo else STATUS_TO_COLLECT,
            "user_notes": "Ensure high-resolution photos showing cracks, serial numbers, and physical condition.",
        })

    # 10. Courier Packaging & Outer Shipping Label
    if any(k in category for k in ["delivery", "wrong", "damage", "transit", "package"]):
        checklist.append({
            "id": "doc_courier_packaging_label",
            "name": "Courier Outer Box & Shipping Label / AWB Barcode",
            "classification": CLASS_RECOMMENDED_EVIDENCE,
            "classification_label": "Recommended Supporting Evidence",
            "condition": "Applicable for shipped items where delivery tampering or courier damage occurred.",
            "relevance": "Demonstrates Air Waybill (AWB) number, dispatch weight, delivery tracking barcode, and parcel condition.",
            "source": "Consumer Protection (E-Commerce) Rules, 2020, Rule 6(3)",
            "source_url": "https://consumeraffairs.nic.in/sites/default/files/E-commerce%20Rules.pdf",
            "status": STATUS_TO_COLLECT,
            "user_notes": "Keep the physical box and outer label intact until dispute resolution.",
        })

    # 11. Customer Support Communication Log / Helpdesk Transcripts
    checklist.append({
        "id": "doc_support_communication_log",
        "name": "Customer Support Chat Logs, Emails & Ticket Grievance Numbers",
        "classification": CLASS_RECOMMENDED_EVIDENCE,
        "classification_label": "Recommended Supporting Evidence",
        "condition": "Recommended for proving prior notice and refusal.",
        "relevance": "Proves the seller and platform were notified of the deficiency, and failed or refused to rectify it within statutory timelines.",
        "source": "Consumer Protection (E-Commerce) Rules, 2020, Rule 4(4) & Rule 5(3)(c)",
        "source_url": "https://consumeraffairs.nic.in/sites/default/files/E-commerce%20Rules.pdf",
        "status": STATUS_TO_COLLECT,
        "user_notes": "Export chat logs with customer support and save email confirmation threads.",
    })

    # 12. Warranty Card / Guarantee Terms (for warranty disputes)
    if any(k in category for k in ["warranty", "guarantee", "service center", "repair"]):
        checklist.append({
            "id": "doc_warranty_card",
            "name": "Manufacturer Warranty Card & Service Job Sheet",
            "classification": CLASS_RECOMMENDED_EVIDENCE,
            "classification_label": "Recommended Supporting Evidence",
            "condition": "Applicable when warranty claims are denied or repairs are refused.",
            "relevance": "Proves warranty duration, coverage terms, authorized service center inspection, and unjust refusal under CPA 2019 Section 2(10).",
            "source": "Consumer Protection Act, 2019, Section 2(10) & Section 39(1)",
            "source_url": "https://consumeraffairs.nic.in",
            "status": STATUS_TO_COLLECT,
            "user_notes": "Obtain service center job sheet stating diagnosis and denial reason.",
        })

    # 13. Service Agreement / Bill (for service deficiency disputes)
    if any(k in category for k in ["service", "broadband", "telecom", "flight", "airline", "hotel"]):
        checklist.append({
            "id": "doc_service_agreement_bill",
            "name": "Service Subscription Agreement / Monthly Bills / Booking PNR",
            "classification": CLASS_RECOMMENDED_EVIDENCE,
            "classification_label": "Recommended Supporting Evidence",
            "condition": "Applicable for service deficiency disputes (telecom, internet, travel, hospitality).",
            "relevance": "Proves terms of service, payment of tariff, and deficiency in standard of performance under CPA 2019 Section 2(11).",
            "source": "Consumer Protection Act, 2019, Section 2(11)",
            "source_url": "https://consumeraffairs.nic.in",
            "status": STATUS_TO_COLLECT,
            "user_notes": "Include booking confirmation PNR or broadband monthly statements showing downtime.",
        })

    # -------------------------------------------------------------------------
    # D. NOT YET ESTABLISHED (Disclose procedural uncertainty)
    # -------------------------------------------------------------------------
    # 14. Physical Stamp Paper Notary Seal
    checklist.append({
        "id": "doc_notary_seal",
        "name": "Physical Stamp Paper Notary Seal (Procedural Ambiguity)",
        "classification": CLASS_NOT_ESTABLISHED,
        "classification_label": "Not Yet Established",
        "condition": "Disclose procedural variation: e-Jagriti guidelines permit scanned electronic self-affidavits, while some District Commissions require physical non-judicial stamp paper attestation.",
        "relevance": "Verification formalities vary across local district consumer commissions.",
        "source": "e-Jagriti Filing Guidelines (Check local Commission practice on e-jagriti.gov.in)",
        "source_url": "https://e-jagriti.gov.in/",
        "status": STATUS_NOT_APPLICABLE,
        "user_notes": "Check specific notice on e-jagriti.gov.in for your District Consumer Commission.",
    })

    return checklist


def update_evidence_item_status(
    case: Dict[str, Any],
    item_id: str,
    new_status: str,
    notes: Optional[str] = None,
) -> bool:
    """
    Updates the availability status and notes of a specific checklist item.
    Records provenance in case correction history.
    """
    if "evidence_checklist" not in case:
        case["evidence_checklist"] = generate_case_evidence_checklist(case)

    if new_status not in VALID_STATUSES:
        logger.warning(f"Invalid status '{new_status}' provided for evidence item {item_id}.")
        return False

    now_iso = datetime.now().isoformat()
    updated = False

    for item in case["evidence_checklist"]:
        if item.get("id") == item_id:
            old_status = item.get("status")
            item["status"] = new_status
            if notes is not None:
                item["user_notes"] = notes
            item["updated_at"] = now_iso
            updated = True

            # Record in correction history
            case.setdefault("correction_history", []).append({
                "field": f"evidence_checklist.{item_id}",
                "old_value": old_status,
                "new_value": new_status,
                "timestamp": now_iso,
                "source_type": "USER_EVIDENCE_UPDATE",
                "notes": notes,
            })
            break

    if updated:
        case["updated_at"] = now_iso

    return updated
