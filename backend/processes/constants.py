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

# Steps a case may finish without (UC-079, the office's decision on 2026-08-16). Not every
# allocation reaches the registration institutes, so step 4 must not hold a finished case open.
#
# **Deliberately does not change the step's own status**: a skipped step stays `in_progress`,
# because it genuinely is unfinished and calling it complete would put work on a signed export
# that nobody did. It is the *case* that may close over it — the compiled report reads the two
# together and prints "skipped" (§10.3).
SKIPPABLE_STEPS = frozenset({4})
