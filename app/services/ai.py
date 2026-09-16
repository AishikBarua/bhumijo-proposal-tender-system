"""All Claude API calls, kept separable from the web layer (app/main.py, app/pipeline.py)
so a future port to another stack only has to translate this file's logic, not rediscover
it. Every public function returns (result, usage_dict) - callers are responsible for
persisting usage (see models.UsageLog); this module has no DB dependency.

Model tiers are deliberately split (see README for the cost rationale): the two
highest-volume calls (is_tender_email, is_relevant_listing) use a cheap model, the two
calls that require real judgement (extract_tender_fields, evaluate_tender /
score_preliminary_fit) use a capable model. Both are overridable via env vars.
"""
import json
import logging
import anthropic

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL_CHEAP as MODEL_CHEAP,
    ANTHROPIC_MODEL_CAPABLE as MODEL_CAPABLE,
    RAW_TEXT_CAP,
    CLASSIFICATION_SNIPPET_CAP,
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
logger = logging.getLogger("tender_agent")

_JSON_RETRY_INSTRUCTION = "\n\nReturn only raw JSON, no prose, no markdown fences."


class ClaudeResponseError(RuntimeError):
    """Raised when Claude's response still isn't valid JSON after one retry - see
    _call_claude. The message alone (model, call type, response snippet) is meant to be
    enough to diagnose from the server log without re-running anything."""


def _call_claude_once(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    usage = {
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return text, usage


def _call_claude(system_prompt: str, user_prompt: str, model: str, max_tokens: int = 1500,
                  call_label: str = "unknown"):
    """Call Claude and parse a strict-JSON response. Returns (parsed_dict, usage_dict).

    Retries once on malformed JSON, appending a short corrective instruction to the user
    prompt - a single malformed response otherwise costs the rest of a whole digest (see
    pipeline._process_email, which now isolates listing failures but still has to give up
    on a listing if this raises). If the retry also fails, raises ClaudeResponseError with
    enough context to identify the cause from the log. Network/API errors are not retried
    here - that's a separate concern from malformed output.

    usage_dict reflects BOTH calls' tokens when a retry happened, so UsageLog-based cost
    tracking doesn't silently undercount the retry."""
    text, usage = _call_claude_once(system_prompt, user_prompt, model, max_tokens)
    try:
        return json.loads(text), usage
    except json.JSONDecodeError:
        pass

    text2, usage2 = _call_claude_once(system_prompt, user_prompt + _JSON_RETRY_INSTRUCTION, model, max_tokens)
    combined_usage = {
        "model": model,
        "input_tokens": usage["input_tokens"] + usage2["input_tokens"],
        "output_tokens": usage["output_tokens"] + usage2["output_tokens"],
    }
    try:
        return json.loads(text2), combined_usage
    except json.JSONDecodeError:
        raise ClaudeResponseError(
            f"Claude returned unparseable JSON after retry (model={model}, call={call_label}): "
            f"{text2[:200]!r}"
        )


def is_tender_email(subject: str, body_snippet: str, keyword_hints: str = None):
    """Stage 1: cheap classification of whether an email is a tender/procurement notice
    or digest at all. Sends subject + at most the first 1000 chars of the body - never
    the whole email. Bilingual (English/Bengali). Returns (bool, usage_dict)."""
    hint_clause = f" Common keywords in real tender emails include: {keyword_hints}." if keyword_hints else ""
    system_prompt = (
        "You classify whether an email is a tender, procurement, RFP, EOI, or quotation "
        "notice or digest (in English or Bengali), as opposed to unrelated mail "
        "(newsletters, receipts, personal correspondence, etc.)." + hint_clause +
        " Respond with ONLY a raw JSON object, no preamble, no markdown fences: "
        '{"is_tender_email": true or false}.'
    )
    body_snippet = (body_snippet or "")[:CLASSIFICATION_SNIPPET_CAP]
    user_prompt = f"Subject: {subject or ''}\n\nBody (may be truncated):\n{body_snippet}"
    parsed, usage = _call_claude(system_prompt, user_prompt, model=MODEL_CHEAP, max_tokens=50,
                                  call_label="is_tender_email")
    return bool(parsed.get("is_tender_email")), usage


_TENDER_TYPES = ("EOI", "RFQ", "RFP", "Proposal", "Enlistment", "Other")

# Bhumijo's four business entities - WHAT KIND OF WORK a tender is, as opposed
# to _TENDER_TYPES above, which is the procurement FORMAT. These are the same
# codes the Proposal Tracker uses, so a tender keeps its label if it moves
# between the two systems.
_ENTITIES = ("P&D", "FM", "WASH", "Tech", "Other")

_ENTITY_GUIDE = (
    'P&D = planning, architecture, urban/landscape design, master plans, '
    'feasibility studies, building design and construction supervision. '
    'FM = facility management: cleaning, janitorial, manpower supply, '
    'outsourcing, security, maintenance of premises. '
    'WASH = toilets, sanitation, sewerage, drainage, water supply, hygiene, '
    'waste management. '
    'Tech = IT, software, monitoring or automation systems. '
    'Other = none of these.'
)


def is_relevant_listing(title: str, organization: str, district: str, company_summary: str = None):
    """Stage 3: cheap relevance screen for one digest listing against the company's
    sector. Sends only title/organization/district plus a short (~100-word)
    company_summary - deliberately minimal input, since this runs ~1,000 times/month.
    company_summary should come from app.company_profile.build_relevance_summary(); if
    not supplied (or the profile is empty), falls back to the hardcoded sector text
    below so Stage 3 still works before a profile has been filled in.
    Biased toward yes when uncertain: a false positive costs a fraction of a taka at the
    next stage; a false negative is a tender missed entirely.

    Also classifies tender_type from the title in this same call (titles almost always
    state it, e.g. "Request for Expression of Interest (EOI) for...") rather than
    spending a separate AI call on it - adds only ~10 output tokens/listing. Falls back
    to "Other" when the type isn't stated.

    And classifies `entity` - which of Bhumijo's four businesses the work belongs to
    (P&D/FM/WASH/Tech). Same reasoning as tender_type: it rides along in this call for
    roughly ten more output tokens rather than costing a call of its own. Note these
    are different questions - a toilet construction tender is entity=WASH but
    tender_type=Other - so neither column substitutes for the other.

    Returns (relevant: bool, tender_type: str, entity: str, usage_dict)."""
    profile_clause = (
        f" The company's profile: {company_summary}" if company_summary else
        " You screen tender listing titles for relevance to a WASH (water, sanitation, "
        "hygiene) and urban planning / architecture consultancy company."
    )
    system_prompt = (
        "You screen tender listing titles for sector relevance to a company." + profile_clause +
        " Could this work plausibly involve the company's sectors/capabilities above (or, "
        "if none given, WASH, sanitation, toilets, water supply, drainage, waste "
        "management, urban planning, architecture, construction/renovation/operation of "
        "public facilities, or related consultancy, EOI, or feasibility work)? Titles may "
        "be in English or Bengali and are often generic (e.g. a bare 'Selection of "
        "Consultant/Consulting Firm' EOI with no sector keyword can still be a genuine "
        "opportunity - judge plausibility, not keyword presence). "
        "When uncertain, answer true: a missed relevant tender is far more costly than "
        "one extra listing scored at the next stage. "
        "Also classify the tender's type from the title - one of: "
        f"{', '.join(_TENDER_TYPES)}. Use \"Other\" if the title doesn't state a type. "
        "Separately, classify which business the WORK belongs to - one of: "
        f"{', '.join(_ENTITIES)}. {_ENTITY_GUIDE} "
        "These two are independent: a toilet construction notice is type Other but "
        "entity WASH. "
        "Respond with ONLY a raw JSON object, no preamble, no markdown fences: "
        '{"relevant": true or false, "tender_type": "EOI/RFQ/RFP/Proposal/Enlistment/Other", '
        '"entity": "P&D/FM/WASH/Tech/Other"}.'
    )
    user_prompt = json.dumps({
        "title": title,
        "organization": organization,
        "district": district,
    }, ensure_ascii=False)
    parsed, usage = _call_claude(system_prompt, user_prompt, model=MODEL_CHEAP, max_tokens=90,
                                  call_label="is_relevant_listing")
    tender_type = parsed.get("tender_type") or "Other"
    if tender_type not in _TENDER_TYPES:
        tender_type = "Other"
    entity = parsed.get("entity") or "Other"
    if entity not in _ENTITIES:
        entity = "Other"
    return bool(parsed.get("relevant", True)), tender_type, entity, usage


def extract_tender_fields(raw_text: str):
    """Full structured extraction from one tender notice's raw text - used for manual
    paste/PDF upload (Stage 5), and as the fallback path when digest parsing finds zero
    listings in an email Stage 1 classified as a tender email. Returns
    (extracted_dict, usage_dict)."""
    if len(raw_text) > RAW_TEXT_CAP:
        logger.warning("raw_text capped from %d to %d chars", len(raw_text), RAW_TEXT_CAP)
        raw_text = raw_text[:RAW_TEXT_CAP]
    system_prompt = (
        "You extract structured data from tender/procurement notices, which may be in "
        "English, Bengali, or mixed. Respond with ONLY a raw JSON object, no preamble, "
        "no markdown fences. If a field is not present in the text, use null. "
        "Fields: title (string), deadline (string, keep original date format), "
        "location (string), estimated_value (string, include currency if given), "
        "scope_summary (string, 2-3 sentences in English regardless of source language), "
        "eligibility_requirements (string, bullet-style summary of who can bid), "
        "required_documents (string, bullet-style list of documents/certificates needed "
        "to submit a bid), "
        "instructions (string, bullet-style submission instructions - how/where/in what "
        "form to submit the bid), "
        "financial_requirement (string, any financial requirement stated - e.g. earnest "
        "money, bid security, minimum turnover, or similar), "
        f"tender_type (string, one of: {', '.join(_TENDER_TYPES)} - almost always stated "
        "in the title, e.g. \"Request for Expression of Interest (EOI)\"; use \"Other\" "
        "if not stated)."
    )
    return _call_claude(system_prompt, raw_text, model=MODEL_CAPABLE, max_tokens=1800,
                         call_label="extract_tender_fields")


def evaluate_tender(extracted: dict, company_profile: dict):
    """Stage 5: full eligibility (hard filter) + fit score against the company's real
    profile. Only call this when eligibility_requirements text is actually available
    (manual paste/PDF/fallback path) - for digest-derived listings with no eligibility
    text, use score_preliminary_fit instead. Returns (evaluation_dict, usage_dict)."""
    system_prompt = (
        "You are an eligibility and fit evaluator for a company deciding whether to bid on "
        "a tender. You will be given the tender's extracted details and the company's real "
        "profile (sectors, certifications, past contracts). "
        "Respond with ONLY a raw JSON object, no preamble, no markdown fences, with fields: "
        "hard_filter_pass (boolean - true only if the company meets explicit hard eligibility "
        "requirements like required licenses/certifications/registration classes that are "
        "clearly stated in the tender; if the tender doesn't state a hard requirement the "
        "company clearly fails, default to true), "
        "hard_filter_reason (string, 1-2 sentences explaining the hard filter decision), "
        "fit_score (integer 0-100, how good a fit this is considering sector match, similar "
        "past experience, scale, and location), "
        "fit_reasons (string, 2-3 sentences explaining the score, mentioning specific past "
        "contracts or certifications where relevant)."
    )
    user_prompt = json.dumps({
        "tender": extracted,
        "company_profile": company_profile,
    }, ensure_ascii=False)
    return _call_claude(system_prompt, user_prompt, model=MODEL_CAPABLE, max_tokens=800,
                         call_label="evaluate_tender")


def score_preliminary_fit(listing: dict, company_profile: dict):
    """Stage 4: fit score ONLY, for digest-derived listings that passed the Stage 3
    relevance screen but have no eligibility text (it's behind the notice link, not in
    the digest). Deliberately never asked to judge eligibility - the caller is
    responsible for setting hard_filter_pass to None ("needs review") in code rather than
    letting the model guess at eligibility it cannot see. Returns (dict, usage_dict) where
    dict has fit_score and fit_reasons."""
    system_prompt = (
        "You score how good a fit a tender listing is for a company, based only on sector "
        "alignment, similarity to the company's past project scale, and location "
        "practicality. You do NOT have eligibility requirements for this listing (they are "
        "not available yet, only behind a link you cannot see) - do not judge eligibility, "
        "only fit. "
        "Respond with ONLY a raw JSON object, no preamble, no markdown fences: "
        '{"fit_score": integer 0-100, "fit_reasons": "2-3 sentences, mentioning specific '
        'past contracts or certifications where relevant"}.'
    )
    user_prompt = json.dumps({
        "listing": listing,
        "company_profile": company_profile,
    }, ensure_ascii=False)
    return _call_claude(system_prompt, user_prompt, model=MODEL_CAPABLE, max_tokens=500,
                         call_label="score_preliminary_fit")
