# Synthetic Challenge Corpus

This directory contains project-created fixtures that are intentionally committed for reproducible tests and demonstrations. All content is fictional, and the files are not authentic public-sector records.

## Directory structure

- `pptx/` contains two vector-only presentation fixtures.
- `email/` contains two three-message email-thread fixtures.
- `../manifests/synthetic_ground_truth.jsonl` contains family-level evaluation ground truth.

The PPTX files contain no external assets. The EML files contain no real email addresses and use only `example.com`.

## Generation

From the repository root:

~~~powershell
python scripts/generate_synthetic_corpus.py --output-root data/synthetic --force
~~~

The generator uses fixed project-authored data and produces deterministic files. Omit `--force` when generating into a new empty directory.

## Evaluation controls

Future parsers must not access the ground-truth manifest while parsing source documents. Development and held-out families must remain separate, and all members of an email family must remain in the same split.
