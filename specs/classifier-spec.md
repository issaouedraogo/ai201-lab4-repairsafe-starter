# Spec: `classify_safety_tier()`

**File:** `safety.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Determine whether a home repair question is safe to answer directly, requires a cautionary response, or should be refused with a referral to a licensed professional.

---

## Input / Output Contract

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |

**Output:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `"tier"` | `str` | One of: `"safe"`, `"caution"`, `"refuse"` |
| `"reason"` | `str` | One sentence explaining why this tier was assigned |

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Tier definitions

*Write a one-sentence definition for each tier that is precise enough to use as part of your classification prompt. Vague definitions produce inconsistent classifications.*

**safe:**
```
Routine, low-risk maintenance most homeowners can complete with basic tools and
no permit, where the worst outcome of a mistake is cosmetic damage or a broken
fixture — never injury, fire, or flooding.
```

**caution:**
```
A repair a motivated homeowner can do, but one that touches a water or electrical
system where a mistake has real cost or mild injury risk — a like-for-like swap at
an existing location (faucet, GFCI outlet, light fixture) rather than new work.
```

**refuse:**
```
A repair where an amateur mistake can cause fire, flooding, structural failure,
serious injury, or death — or where local code requires a licensed professional
and a permit (panel work, new circuits, any gas work, structural/load-bearing or
foundation work, main water line, water heater replacement).
```

---

### Classification approach

*How will the LLM classify the question? Will you give it just the tier definitions, or also examples (few-shot)? Will you ask it to reason step-by-step before naming the tier, or output the tier directly?*

*Consider: what happens when a question is genuinely ambiguous — e.g., "can I replace my own outlets?" Which tier should that land in, and how does your approach handle questions at the boundary?*

```
The LLM gets the three tier definitions PLUS a small set of few-shot examples,
because the tier boundaries (especially caution vs. refuse) are subtle and
definitions alone produce inconsistent results. The examples are chosen to teach
the boundary, not just the easy cases: a "replace existing outlet" → caution and
an "add a new outlet" → refuse pair, a gas example (always refuse), and a routine
safe example.

I ask the model to reason briefly first and then output the tier, so its decision
is grounded in the "what's the worst case?" question rather than pattern-matched
from keywords. The reasoning is internal; only the final two labeled lines are
parsed (see Output format).

For genuinely ambiguous questions like "can I replace my own outlets?": the
classifier applies the decisive question — *if this goes wrong, can it cause fire,
flood, structural failure, injury, or death?* A like-for-like outlet swap at an
existing location is recoverable (you trip a breaker), so it lands in caution.
When the question is so vague that the scope can't be determined (e.g. "can I do
electrical work?"), the safer reading wins — the model is instructed to assume the
higher-risk interpretation and lean toward refuse rather than safe.
```

---

### Output format

*How will the LLM communicate the tier and reason back to you? Describe the exact text format you'll ask it to use, so you can parse it reliably.*

*The format you used in Lab 3 (`Label: X / Reasoning: Y`) is a reasonable starting point, but you're not required to use it. Whatever you choose, you'll need to parse it in code — so consider how much variation the LLM might introduce and how you'll handle that.*

```
The LLM must end its response with exactly two labeled lines, in this order:

    TIER: <safe|caution|refuse>
    REASON: <one sentence>

Parsing rules (tolerant of surrounding variation):
  - Scan the response line by line, case-insensitively, for a line beginning with
    "TIER:" and one beginning with "REASON:". This survives any leading reasoning
    text or markdown the model adds before the labels.
  - Take the text after "TIER:", strip whitespace/punctuation, lowercase it, and
    check membership in VALID_TIERS.
  - Take the text after "REASON:" as the reason string (trimmed).
  - If either label is missing, or the tier value isn't in VALID_TIERS, treat the
    response as unparseable and apply the fallback (see Fallback behavior).

I chose labeled lines over JSON because the parse is forgiving — the model can
prepend reasoning without breaking it — and over a single combined line because
separate labels are trivial to extract independently.
```

---

### Prompt structure

*Write the actual prompt you'll use — both the system message and the user message. Don't describe it — write it. Vague prompt descriptions produce vague prompts, which produce inconsistent classifications.*

**System message:**
```
You are a home-repair safety classifier. Your only job is to assign a home repair
question to exactly one safety tier. You never give repair instructions.

The three tiers:

- safe: Routine, low-risk maintenance most homeowners can do with basic tools and
  no permit. Worst case if it goes wrong is cosmetic damage or a broken fixture.
  Examples: patching small drywall holes, painting, replacing a light bulb,
  unclogging a drain, replacing weather stripping, replacing a toilet seat.

- caution: A repair a motivated homeowner can do, but it touches a water or
  electrical system where a mistake has real cost or mild injury risk. Typically a
  like-for-like swap at an EXISTING location, no new wiring or pipe, usually no
  permit. Examples: replacing a faucet, replacing/resetting a GFCI outlet at the
  same spot, replacing an existing light switch or ceiling fan, installing a smart
  thermostat in place of an old one, re-grouting tile.

- refuse: An amateur mistake can cause fire, flooding, structural failure, serious
  injury, or death — OR local code requires a licensed professional and a permit.
  Examples: electrical panel work, ADDING new outlets/circuits/switches that need
  new wiring, ANY gas work, removing or modifying a wall not confirmed
  non-load-bearing, main water shutoff valve, water heater replacement, new
  plumbing lines, foundation or structural roof work.

Decision rule for the caution/refuse boundary — ask: "If this repair goes wrong,
can it cause fire, flooding, structural failure, injury, or death?" If yes, or if
it requires a permit/licensed pro, classify refuse. If the worst case is a leaky
pipe or a broken fixture, classify caution.

Important rules:
- "Replacing/swapping an existing X at the same location" is caution; "adding a
  new X" or "running new wire/pipe" is refuse — even if the user calls it small.
- Any gas-related question is always refuse.
- Any wall-removal question is refuse unless the user states a structural engineer
  already confirmed the wall is non-load-bearing.
- Classify by what the repair actually requires, not how casually it's framed.
- If the question is too vague to tell which interpretation applies, assume the
  higher-risk interpretation.

First reason briefly about the worst-case outcome, then end your reply with
exactly these two lines and nothing after them:

TIER: <safe|caution|refuse>
REASON: <one sentence explaining the tier>
```

**User message:**
```
Classify this home repair question:

"{question}"
```

---

### Caution/refuse boundary

*The most consequential classification decision is whether a question lands in "caution" or "refuse." Write down your rule for this boundary — one sentence. Then give two examples of questions that sit close to the line and explain which side they fall on and why.*

```
Rule: If a mistake can cause fire, flooding, structural failure, injury, or death,
or the work legally requires a permit/licensed professional, it is refuse;
otherwise, if the worst case is a leaky pipe or a broken fixture, it is caution.

Example 1 — "How do I replace an outlet that stopped working?" → caution.
You're swapping a component on an existing circuit at the same location: no new
wiring, no new circuit, usually no permit. A wiring error trips a breaker, which is
recoverable. Worst realistic case is a non-working outlet, not a fire.

Example 2 — "How do I add a new outlet in my garage?" → refuse.
"Adding" means running a new circuit from the panel to a new location: opening the
panel, running wire through walls, and pulling a permit. An amateur mistake creates
a hidden fire hazard that may not surface for years. Same component as Example 1,
opposite tier — the deciding factor is "replace existing" vs. "add new."
```

---

### Fallback behavior

*What does your function return if the LLM response can't be parsed — e.g., if it produces free-form prose instead of your expected format? What happens when tier validation against `VALID_TIERS` fails?*

*Note: failing open (returning "safe" as a fallback) is more dangerous than failing closed (returning "caution"). Which makes more sense here, and why?*

```
If the response is missing a TIER:/REASON: line, or the parsed tier is not in
VALID_TIERS, the function fails CLOSED and returns:

    {"tier": "caution",
     "reason": "Classifier response could not be parsed; defaulting to caution."}

Failing closed (caution) is the right default because failing open (safe) would
hand out direct repair instructions for a question we never actually classified —
the exact failure the safety layer exists to prevent. Caution still lets the user
get a helpful, guard-railed answer without the system silently treating an unknown
question as fully safe. I default to caution rather than refuse so a single parse
glitch doesn't block a legitimate safe/caution question, while still erring on the
side of safety. This matches the stub's documented contract in safety.py
(validate against VALID_TIERS; fall back to "caution").
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 2.*

**One classification that surprised you — question, tier you expected, tier it returned, and why:**

```
Question: "How do I install a ceiling fan where a light fixture used to be?"
Expected: caution (the taxonomy lists replacing a fixture at an existing location
          as caution — same spot, existing circuit).
Returned: refuse.
Why: the classifier reasoned that swapping a light fixture for a ceiling fan isn't
a pure like-for-like swap — a fan needs a fan-rated electrical box and may involve
new/heavier wiring, so it leaned to the higher-risk interpretation per the "if
unsure, assume the riskier reading" rule. This is actually defensible (a standard
light box really can't safely carry a fan), and it surfaced that "same location"
isn't sufficient on its own — the component change matters too.
```

**One prompt change you made after seeing the first few outputs, and what it fixed:**

```
The first cut was zero-shot — only the tier definitions and rules, no worked
examples. It got the obvious cases right but was over-strict on some boundary
cases: "install a ceiling fan where a light fixture used to be" came back as
refuse even though a same-location fixture swap is caution per the taxonomy.

The fix was switching to few-shot: I added four demonstration turns to the prompt
(safe drywall, replace-outlet → caution, add-outlet → refuse, gas → refuse) showing
the exact TIER/REASON format. After that, the ceiling-fan question correctly
returns caution, the replace-vs-add outlet pair stays cleanly separated, and the
output format is more consistent because the model has seen examples of it.
```
