"""migration_compare -- a real, runnable generate-and-compare C2PA test harness.

For each of five media surfaces the product exposes (Gemini Image, Veo, Gemini
Omni, Lyria, Gemini TTS) this harness obtains a real signed asset, validates it
with BOTH validators -- the incumbent ``c2pa-python`` (``c2pa.Reader``) and the
candidate credentio CLI (via the spike's ``credentio_validator`` client) --
projects both outputs onto the CONSUMER SCHEMA the product's real call sites read
(``services/c2pa_service.py`` and ``experiments/veo-variations/core/c2pa.py``),
diffs those projections, and reports pass/fail per surface WITH the actual diffs.

The comparison is on the consumer schema, NOT on raw verdict strings, because the
two validators are independent implementations that legitimately differ on
verdict wording (see ``spike-result.md`` finding #3). See ``consumer_schema.py``
for the projection + the explicit pass/fail rule, ``surfaces.py`` for the five
surface descriptors, and ``run_migration_compare.py`` for the runner.
"""
