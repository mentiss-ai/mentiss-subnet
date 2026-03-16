---
name: review-mentiss
description: Review Mentiss API alignment and validation docs accuracy
user-invocable: true
---

Run two checks in parallel and report findings:

## Check 1: API Schema Alignment

1. Fetch the live API schema: `curl -s https://api.mentiss.ai/api/_introspect.playRouter`
2. Read the API client code: `mentiss/api/client.py` and `mentiss/api/types.py`
3. Compare:
   - Are all endpoints in the schema implemented in the client?
   - Are all request/response fields in the client matching the schema?
   - Are there any new endpoints or fields in the schema not yet consumed?
   - Are there any fields the client uses that no longer exist in the schema?
4. Report mismatches as actionable items.

## Check 2: Validation Docs Accuracy

1. Read `docs/validation-logic.md`
2. Read the current implementation files:
   - `mentiss/validator/reward.py` (scoring functions)
   - `mentiss/validator/forward.py` (game loop, metric collection, reward updates)
   - `mentiss/game/state.py` (MinerGameStats fields and properties)
   - `mentiss/game/manager.py` (stat accumulation logic)
   - `mentiss/utils/config.py` (CLI args and defaults)
   - `mentiss/base/validator.py` (EMA update, weight setting)
3. Compare the docs against the code:
   - Are all formulas correct?
   - Are all default values accurate?
   - Are all config parameters listed with correct defaults?
   - Does the described flow match the actual code flow?
   - Are all files in the file reference table still accurate?
4. Report any drift between docs and code.

## Check 3: Self-Improvement

1. After completing the above checks, reflect on whether this skill itself could be improved:
   - Are there new files that should be added to the checklists?
   - Are there checks that are no longer relevant and should be removed?
   - Could the output format be clearer?
2. If improvements are found, directly edit `.claude/skills/review-mentiss/SKILL.md` to apply them.
3. Note what was changed in the output.

## Output Format

```
## API Schema Alignment

[OK / ISSUES FOUND]
- ...

## Validation Docs Accuracy

[OK / ISSUES FOUND]
- ...

## Skill Self-Update

[NO CHANGES / UPDATED]
- ...

## Recommended Actions

- ...
```
