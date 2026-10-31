# TherapyBot evaluations

`cases.json` is a set of realistic conversations with what a good reply looks like. Run them against the real
models after any change to prompts, models, or retrieval:

```bash
python manage.py run_evals            # all cases
python manage.py run_evals --only crisis,grief
```

Each case gets **hard checks** (risk level, crisis resources, length) and **rubric scores** from a judge model
(1-5 for empathy, conversational tone, helpfulness, safety, boundaries). Reports are written to `reports/`.

Clinicians: please add and edit cases freely. The `good_reply` field is what the judge compares against, so
describe the ideal response in your own words. Real user data must never be added here.
