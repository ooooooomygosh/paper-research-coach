# Contributing / 参与改进

Thank you for helping people read, not just generate text. A useful change removes friction from a real reading task without adding another mandatory workflow.

## Start with the reading moment

Describe what the reader was trying to understand, what interrupted them, and the smallest change that would help. For UI work, include the viewport, keyboard/touch interaction and a synthetic reproduction. Prefer one clear action over another permanent panel. Do not infer learning from clicks, a generated note or fluent English.

## Development

Use the source setup in [Quick start](docs/QUICKSTART.md). Python 3.10+ and Node.js 24.15+ are required for development. Then run:

```bash
npm --prefix frontend test
npm --prefix frontend run build
pytest -q
python scripts/validate_skill.py
python scripts/check_docs.py
```

The PR workflow runs frontend tests/build, backend tests on Python 3.10 and 3.12, Skill validation, dependency auditing and packaging. Browser checks run separately with synthetic fixtures. Report what actually ran; distinguish mocked tests, browser checks, live model runs and human-learning evaluation.

## Releasing

Every merge to `main` publishes a GitHub pre-release named after the package version, with the wheel, source archive and Skill ZIP. A version is published once: if shipped files (`src`, `frontend/src`, `skills`, `pyproject.toml`) change under a version that is already released, PR checks warn and the release job on `main` fails, because readers would keep downloading the old build. Before merging such a change, bump the version and move the changelog entries in one step:

```bash
python scripts/bump_version.py 2.0.0rc11
```

## Safe examples and screenshots

Use `prc-demo`, never a personal library. The example paper and values are synthetic. Label any scripted AI exchange as scripted, not a model benchmark. Do not expose launch tokens, user paths, private PDFs, credentials or conversation history in a screenshot. Reproduction instructions live in [Showcase](docs/SHOWCASE.md).

## Review checklist

- Keep the paper’s location, source version and exact learner wording intact. Do not silently promote assisted performance to mastery.
- Test empty, loading, error and retry states; preserve input on failures. Check keyboard focus, Escape order, narrow screens and reduced motion.
- Keep model calls explicit, existing permissions narrow and original PDFs read-only. Never add a network service just for a visual effect.
- Update the relevant guide and changelog. Keep the first page about reading; advanced configuration belongs in the workbench guide.

## Reports

Use a bug or reading-improvement issue for ordinary reports. Use only synthetic files or excerpts you are permitted to share. For suspected security issues, follow [SECURITY.md](SECURITY.md); do not post working credentials, sensitive traces or private datasets.
