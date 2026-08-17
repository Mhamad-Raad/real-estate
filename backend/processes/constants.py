"""How many steps a case has — declared once (§5).

The workflow is five steps today and the office has asked for seven (UC-043: a conclusion step,
then a papers-sent step). The It.7 review counted the assumption spelled out in **four** backend
places and two frontend ones, each of which would have to be found by hand. Nothing here changes
the count; it moves it to one line, so the change that does is a change to one line plus the two
new step *shapes* — which is the part that actually needs thought.

`LAST_STEP` is the roll-up step: it holds no data of its own and completes when its predecessors
do (§3.6), so "the last step" and "the summary step" are the same number by design, not by
accident. Anything ranging over the workflow uses `STEP_NUMBERS`; anything asking "is this the
final one" uses `LAST_STEP`.
"""

FIRST_STEP = 1
LAST_STEP = 5
STEP_NUMBERS = range(FIRST_STEP, LAST_STEP + 1)
# Every step before the roll-up — the ones that carry institutes, fields and papers.
WORKING_STEPS = range(FIRST_STEP, LAST_STEP)

# Steps whose **institutes** a case may finish without (UC-079, narrowed by UC-088).
#
# Not every allocation reaches the Step-4 registration bodies — the relevant authority and the
# land map — so those must not hold a finished case open. **The rest of the step still does**:
# the municipality form and the land number are the case's own paperwork, and the office's first
# reading of this rule let a case close without them (the office's correction, 2026-08-17).
#
# Optionality is therefore per *requirement*, not per step — `status.blocking_requirements` is
# where that is applied, and `complete_process`, the step-5 roll-up and the compiled report all
# ask it the same question so the three can never disagree.
#
# **Deliberately does not change the step's own status**: a step left short stays `in_progress`,
# because it genuinely is unfinished and calling it complete would put work on a signed export
# that nobody did. It is the *case* that may close over it — the compiled report reads the two
# together and prints "skipped" (§10.3).
OPTIONAL_INSTITUTE_STEPS = frozenset({4})
