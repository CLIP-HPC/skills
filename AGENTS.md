# Repository maintenance

These instructions apply when modifying this repository. Cluster-use workflows
belong in the relevant `plugins/<plugin>/skills/<skill>/SKILL.md`; keep maintenance
instructions out of the installed plugin and skills.

## Sources of truth

- `plugins/<plugin>/plugin.json`: portable Agent Plugins manifest and release
  version of each plugin (`cbe`, `grid`).
- `marketplace.json`: source marketplace catalog.
- `plugins/*/skills/*/SKILL.md`: shared instructions, discovery descriptions,
  and neutral picker metadata.

Edit these sources rather than their generated host adapters:

- `.claude-plugin/marketplace.json`
- `.agents/plugins/marketplace.json`
- `plugins/*/.claude-plugin/plugin.json`
- `plugins/*/skills/*/agents/openai.yaml`

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
`plugins/<plugin>/evals/` as described in the README, and keep at least one case where
no CBE skill should load. Eval cases contain prompts and graders only; they are
installed with the plugin but never loaded as instructions.

For packaging or compatibility changes, run `scripts/smoke-test.py` with the
CLI versions listed in the README. It uses temporary client state and requires
no credentials. For skill workflow changes, review `tests/scenarios.md`; do not
submit real cluster jobs merely to validate packaging.

Keep one shared skill tree. Do not introduce per-host copies or
consumer-side build hooks.
Generate identical plugin membership and sources for every host from the common
catalog. Host adapters may change metadata format, not which plugins are available.

## Versions and releases

This is a plugin and marketplace repository: clients only pick up a change after
the version in that plugin's `plugin.json` changes. Every user-facing change
therefore needs a version bump, so use versions sparingly:

- Collect related changes on one feature branch. Bump the version once, in the
  last commit before the pull request, not per commit. Regenerate the adapters
  after the bump.
- Open the pull request when the branch is ready to release, not for each
  intermediate step.
- Each plugin has its own version. Bump only the plugins whose shipped files
  changed, and release each of them separately.
- After merging, release: tag the merge commit on `main` with an annotated tag
  `<plugin>-v<version>` (`git tag -a cbe-v0.6.1 -m cbe-v0.6.1`), push the tag,
  and create a GitHub release with notes from the commits since that plugin's
  previous tag (`gh release create cbe-v0.6.1 --verify-tag --generate-notes
  --notes-start-tag <previous tag>`). Tags `v<version>` from before
  `<plugin>-v<version>` are cbe releases. The release workflow then checks the
  tag against `plugins/<plugin>/plugin.json` and moves the tag `latest` forward
  to the release commit. Never move `latest` by hand.
- Use semantic versions: patch for fixes and corrected facts, minor for new
  skills or workflows, major for incompatible changes to installation or
  plugin layout.

Write commit messages and pull request titles as
[Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>):
<summary>`, with types such as `feat`, `fix`, `docs`, `ci`, `test`, `refactor`,
and `chore`, and the skill or area as the scope, for example
`fix(cbe-queue): show the full fair-share chain`. Put the ticket ID, such as
`COPS-239`, in the body as `Refs: COPS-239`. Use `chore(release): <version>`
for the version bump.

This repository is public and supports regular CBE / CLIP users. Keep internal
instructions, plugins, and repository references out of it. Until the CBE.next release,
the authoritative documentation source is `newdocs` branch `main`;
see the README.
