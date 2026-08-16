# Agent Evaluation

## Evaluation scope

Offline FunctionModel evaluation over 20 cases: 15 existing RAG development questions and 5 specialised routing/abstention cases.
Development sources: S001, S002, S003, S004, S006. Real smoke performed: no.

## Aggregate metrics

| Metric | Result |
| --- | ---: |
| Task success | 18/20 (0.9000) |
| Citation validity | 16/16 (1.0000) |
| Appropriate abstention | 2/2 (1.0000) |
| Acceptable tool selection | 20/20 (1.0000) |
| Unnecessary tool calls | 0/22 (0.0000) |
| Average tool calls per task | 1.1000 |

## Routing/abstention results

| Case | Category | Status | Tools | Success |
| --- | --- | --- | --- | --- |
| AGENT-ROUTE-001 | direct_retrieval | answered | retrieve_evidence | yes |
| AGENT-ROUTE-002 | structured_fact_search | answered | search_project_facts → read_evidence_block | yes |
| AGENT-ROUTE-003 | evidence_inspection | answered | search_project_facts → read_evidence_block | yes |
| AGENT-ROUTE-004 | insufficient_retrieval | insufficient_evidence | retrieve_evidence | yes |
| AGENT-ROUTE-005 | no_match_fact_search | insufficient_evidence | search_project_facts | yes |

## Known failures

RAG-DEV-003, RAG-DEV-010

## Interpretation

This offline FunctionModel evaluation measures deterministic orchestration, grounding, routing contracts and labelled evidence availability. It does not measure autonomous GPT-5.4-mini tool-selection quality.

## Limitations

No semantic answer grading, hosted-model decision-quality measurement, real latency, real model usage, or real cost measurement was performed.
