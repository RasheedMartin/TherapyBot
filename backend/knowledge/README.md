# TherapyBot knowledge base

Each Markdown file here is indexed for retrieval (`python manage.py build_index`).

Guidelines for adding content:

- One topic per file, with `##` sections. Sections become retrieval chunks, so keep each one self-contained.
- Start each file with a front-matter style block:
  `title:`, `audience:` (client / caregiver / clinician), `reviewed_by:` and `reviewed_on:`.
- Write in plain language. Only include content you have the right to use: original writing,
  public-domain material (e.g. NIMH, SAMHSA), or material licensed for reuse. Note the source.
- **Every file must be reviewed by a licensed clinician before it is used in production.**
  Files with `reviewed_by: PENDING` are drafts.

This README is excluded from the index.
