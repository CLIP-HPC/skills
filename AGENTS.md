# Repository maintenance

These instructions apply when modifying this repository. Cluster-use workflows
belong in the relevant `plugins/cbe/skills/<skill>/SKILL.md`; keep maintenance
instructions out of the installed plugin and skills.

## Sources of truth

- `plugins/cbe/plugin.json`: portable Agent Plugins manifest and release version.
- `marketplace.json`: source marketplace catalog.
- `plugins/cbe/skills/*/SKILL.md`: shared instructions, discovery descriptions,
  and neutral picker metadata.

Edit these sources rather than their generated host adapters:

- `.claude-plugin/marketplace.json`
- `.agents/plugins/marketplace.json`
- `plugins/cbe/.claude-plugin/plugin.json`
- `plugins/cbe/skills/*/agents/openai.yaml`

After changing a source, regenerate and validate:

```bash
uv run --locked python scripts/bundle.py
uv run --locked python scripts/validate.py
```

Include the generated files in the same commit or proposed change as their
sources. Users install directly from Git; installation does not run the
generator. Do not leave regeneration for consumers or deployment.

## Checks and releases

For changes to generation, validation, or installation helpers, also run:

```bash
uv run --locked python -m unittest discover -s tests -v
```

For description or workflow changes, run the Claude Code eval suite in
`plugins/cbe/evals/` as described in the README, and keep at least one case where
no CBE skill should load. Eval cases contain prompts and graders only; they are
installed with the plugin but never loaded as instructions.

For packaging or compatibility changes, run `scripts/smoke-test.py` with the
CLI versions listed in the README. It uses temporary client state and requires
no credentials. For skill workflow changes, review `tests/scenarios.md`; do not
submit real cluster jobs merely to validate packaging.

Bump the version in the portable manifest when preparing a release and regenerate
the adapters. Keep one shared skill tree. Do not introduce per-host copies or
consumer-side build hooks.
Generate identical plugin membership and sources for every host from the common
catalog. Host adapters may change metadata format, not which plugins are available.

This repository is public and supports regular CBE / CLIP users. Keep internal
staff instructions out of the public skills and documentation. Private repository
pointers belong only in technically necessary marketplace entries, labelled for
internal staff and as unnecessary for regular use. Until the CBE.next release,
the authoritative documentation source is `newdocs` branch `review/final-state`;
see the README.
