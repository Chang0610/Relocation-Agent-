# Publishing Checklist

This folder is a curated local release copy for a future public portfolio repository. It has not been pushed to GitHub or deployed.

Before publishing:

- Review the included runtime knowledge JSON, URLs, and screenshots for third-party redistribution rights and source attribution requirements.
- Keep `.env.local`, API keys, feedback logs, generated QA reports, and real user data out of Git.
- Run `git status --short` and inspect every staged file before the first commit.
- Run the Python and Node regression commands in `README.md` from this directory.
- Review provider privacy/logging settings before applying `render.yaml`; it is demo-only configuration, not production readiness.
- Do not publish until the owner explicitly chooses a GitHub repository and confirms the public audience.

The original Chinese project, source PRD/research documents, and development feedback remain outside this curated copy.

## Language scope

The interface, user-facing assistant instructions, portfolio docs, and English-edition source pack are English. Some runtime compatibility details intentionally remain bilingual: the existing calendar API uses Chinese machine-readable `date_basis` enum values, and some source records retain Chinese official names or attribution text alongside English names. These are not intended as user-facing copy. Do not change those API values as part of localization; validate rendered UI and assistant responses instead. This release is English-facing, not a zero-Chinese-character source tree.
