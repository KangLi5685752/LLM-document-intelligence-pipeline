# Synthetic Data Policy

## Purpose

The synthetic files in this repository were created specifically for this portfolio project. They provide controlled PPTX and email-style challenge cases that can be redistributed, regenerated, inspected, and tested without relying on private records.

## Fictional content

All names, organisations, email addresses, dates, budgets, projects, events, and scenarios in the synthetic corpus are fictional. Email addresses use only the reserved `example.com` domain. Any accidental resemblance to a real person, project, or organisation is coincidental.

The fixtures must never be presented as authentic public-sector records. Their visual language is intentionally generic and does not reproduce real government branding.

## Assets and generation

- No external images, logos, templates, downloaded material, or third-party assets are used.
- PPTX visuals use only text, tables, lines, connectors, and vector shapes.
- EML messages contain no real email addresses or attachments.
- Generation uses fixed project-authored data without network calls, LLM calls, or randomness.
- The synthetic files are intentionally committed for reproducible tests and demonstrations.

Redistribution of these project-created fixtures is allowed. This project policy is not legal advice.

## Ground truth and leakage controls

Synthetic ground truth is stored separately from the source documents. Future parsers must process only the source fixture and must not receive the ground-truth record as input.

All sources in a synthetic family must remain in one evaluation split. Once the split is frozen, held-out families must not be inspected by extraction prompts or used to tune extraction rules. Changes prompted by held-out content would invalidate the intended generalisation check.
