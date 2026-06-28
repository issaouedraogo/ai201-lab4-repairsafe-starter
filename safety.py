from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, VALID_TIERS

_client = Groq(api_key=GROQ_API_KEY)


_SYSTEM_PROMPT = """You are a home-repair safety classifier. Your only job is to assign a home repair question to exactly one safety tier. You never give repair instructions.

The three tiers:

- safe: Routine, low-risk maintenance most homeowners can do with basic tools and no permit. Worst case if it goes wrong is cosmetic damage or a broken fixture. Examples: patching small drywall holes, painting, replacing a light bulb, unclogging a drain, replacing weather stripping, replacing a toilet seat.

- caution: A repair a motivated homeowner can do, but it touches a water or electrical system where a mistake has real cost or mild injury risk. Typically a like-for-like swap at an EXISTING location, no new wiring or pipe, usually no permit. Examples: replacing a faucet, replacing/resetting a GFCI outlet at the same spot, replacing an existing light switch or ceiling fan, installing a smart thermostat in place of an old one, re-grouting tile.

- refuse: An amateur mistake can cause fire, flooding, structural failure, serious injury, or death — OR local code requires a licensed professional and a permit. Examples: electrical panel work, ADDING new outlets/circuits/switches that need new wiring, ANY gas work, removing or modifying a wall not confirmed non-load-bearing, main water shutoff valve, water heater replacement, new plumbing lines, foundation or structural roof work.

Decision rule for the caution/refuse boundary — ask: "If this repair goes wrong, can it cause fire, flooding, structural failure, injury, or death?" If yes, or if it requires a permit/licensed pro, classify refuse. If the worst case is a leaky pipe or a broken fixture, classify caution.

Important rules:
- "Replacing/swapping an existing X at the same location" is caution; "adding a new X" or "running new wire/pipe" is refuse — even if the user calls it small.
- Any gas-related question is always refuse.
- Any wall-removal question is refuse unless the user states a structural engineer already confirmed the wall is non-load-bearing.
- Classify by what the repair actually requires, not how casually it's framed.
- If the question is too vague to tell which interpretation applies, assume the higher-risk interpretation.

First reason briefly about the worst-case outcome, then end your reply with exactly these two lines and nothing after them:

TIER: <safe|caution|refuse>
REASON: <one sentence explaining the tier>"""

# Few-shot demonstrations: shown to the model as prior turns so it learns the
# caution/refuse boundary (the replace-vs-add pair, always-refuse gas) and the
# exact TIER/REASON output format before seeing the real question.
_FEWSHOT_EXAMPLES = [
    (
        "How do I patch a small hole in my drywall?",
        "TIER: safe\nREASON: Patching a small drywall hole is routine cosmetic work "
        "with no risk of fire, flooding, or injury.",
    ),
    (
        "How do I replace an outlet that stopped working?",
        "TIER: caution\nREASON: Swapping an outlet on an existing circuit at the same "
        "location is doable but carries mild shock risk if power isn't shut off first.",
    ),
    (
        "How do I add a new outlet to my garage?",
        "TIER: refuse\nREASON: Adding a new outlet means running a new circuit from the "
        "panel, which requires a permit and can create a hidden fire hazard if done wrong.",
    ),
    (
        "How do I extend my gas line for a new stove?",
        "TIER: refuse\nREASON: Any gas line work risks fire, explosion, or carbon "
        "monoxide poisoning and must be done by a licensed professional.",
    ),
]


def _build_messages(question: str) -> list:
    """Assemble system prompt + few-shot demonstrations + the real question."""
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for example_q, example_a in _FEWSHOT_EXAMPLES:
        messages.append(
            {"role": "user", "content": f'Classify this home repair question:\n\n"{example_q}"'}
        )
        messages.append({"role": "assistant", "content": example_a})
    messages.append(
        {"role": "user", "content": f'Classify this home repair question:\n\n"{question}"'}
    )
    return messages


_FALLBACK = {
    "tier": "caution",
    "reason": "Classifier response could not be parsed; defaulting to caution.",
}


def _parse_response(text: str) -> dict:
    """Pull TIER and REASON out of the raw LLM response.

    Scans lines case-insensitively so leading reasoning text or markdown doesn't
    break the parse. Returns the fallback dict if either label is missing or the
    tier isn't in VALID_TIERS.
    """
    tier = None
    reason = None
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("tier:"):
            tier = stripped.split(":", 1)[1].strip().strip(".\"'").lower()
        elif lowered.startswith("reason:"):
            reason = stripped.split(":", 1)[1].strip()

    if tier not in VALID_TIERS or not reason:
        return dict(_FALLBACK)
    return {"tier": tier, "reason": reason}


def classify_safety_tier(question: str) -> dict:
    """
    Classify a home repair question into one of three safety tiers.

    Sends a single chat completion (no tools) built from the tier definitions in
    _SYSTEM_PROMPT plus a few-shot set of example classifications, parses the
    TIER/REASON lines out of the raw response, and validates the tier against
    VALID_TIERS. Any parse failure or API error falls back to "caution" (fail
    safe, not open).

    Returns a dict with:
      - "tier"   : str — one of "safe", "caution", "refuse"
      - "reason" : str — a brief explanation of why this tier was assigned
    """
    try:
        completion = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=_build_messages(question),
            temperature=0,
        )
        raw = completion.choices[0].message.content
    except Exception:
        # Any API/network error fails closed to caution rather than open to safe.
        return dict(_FALLBACK)

    return _parse_response(raw or "")
