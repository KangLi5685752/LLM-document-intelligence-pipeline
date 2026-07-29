# Stage 3B v0.3 quality diagnosis

This development-only diagnosis explains the frozen v0.2 strict-match failure without changing matching protocol 0.1.

No held-out semantic annotation model was deserialized; no S005 or S007 ParsedDocument was opened or executed; held-out raw JSONL bytes and row metadata may be scanned by the guarded loader for integrity verification and split routing.

## Aggregate diagnosis

- Development gold facts: 25
- Facts with a v0.2 candidate in the exact evidence block: 12
- Facts requiring new predicate coverage: 8
- Facts primarily blocked by subject/value/qualifier representation: 12
- Primary failure categories: {"evidence_segmentation": 5, "missed_numbered_recommendation": 4, "missing_predicate_coverage": 4, "subject_text_resolution": 12}
- Frozen v0.2 predicate counts: {"action_status": 1, "commitment": 193, "decision": 3, "metric": 84, "requirement": 34, "risk": 6}
- Frozen v0.2 rule counts: {"V02-RULE-ACTION-001": 1, "V02-RULE-COM-EXPLICIT-001": 1, "V02-RULE-COM-WEAK-002": 192, "V02-RULE-DEC-001": 3, "V02-RULE-METRIC-001": 84, "V02-RULE-REQ-001": 34, "V02-RULE-RISK-001": 6}

## Per-fact diagnosis

| Annotation | Source | Predicate | Evidence block | Same-block candidates | Primary category | Closest candidates | Mismatching fields |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| PG-V01-S001-001 | S001 | recommendation | DOC-S001-B0009 | 0 | missed_numbered_recommendation | none | no comparable candidate |
| PG-V01-S001-002 | S001 | recommendation | DOC-S001-B0010 | 0 | missed_numbered_recommendation | none | no comparable candidate |
| PG-V01-S001-003 | S001 | metric | DOC-S001-B0012 | 0 | missing_predicate_coverage | none | no comparable candidate |
| PG-V01-S001-004 | S001 | recommendation | DOC-S001-B0015 | 0 | missed_numbered_recommendation | none | no comparable candidate |
| PG-V01-S001-005 | S001 | recommendation | DOC-S001-B0020 | 0 | missed_numbered_recommendation | none | no comparable candidate |
| PG-V01-S002-001 | S002 | commitment | DOC-S002-B0006 | 7 | subject_text_resolution | V02-CAND-19D7708836E648DD451DC275A7CDE15C72C1B1C5FF84F5A11775862E1A335E5D, V02-CAND-6E1EBF34E2B7CBC183E0F3FB094576C0BA1C3E45E11849FF6C759BF7BA107970, V02-CAND-844A087D210C9DA1F8FAF1F2398DEC47E605F14A4A1FFEED76B1768D9EE001E5 | normalized_value, raw_value_non_strict, subject_text |
| PG-V01-S002-002 | S002 | commitment | DOC-S002-B0006 | 7 | subject_text_resolution | V02-CAND-19D7708836E648DD451DC275A7CDE15C72C1B1C5FF84F5A11775862E1A335E5D, V02-CAND-6E1EBF34E2B7CBC183E0F3FB094576C0BA1C3E45E11849FF6C759BF7BA107970, V02-CAND-844A087D210C9DA1F8FAF1F2398DEC47E605F14A4A1FFEED76B1768D9EE001E5 | normalized_value, raw_value_non_strict, subject_text |
| PG-V01-S002-003 | S002 | commitment | DOC-S002-B0006 | 7 | subject_text_resolution | V02-CAND-19D7708836E648DD451DC275A7CDE15C72C1B1C5FF84F5A11775862E1A335E5D, V02-CAND-6E1EBF34E2B7CBC183E0F3FB094576C0BA1C3E45E11849FF6C759BF7BA107970, V02-CAND-844A087D210C9DA1F8FAF1F2398DEC47E605F14A4A1FFEED76B1768D9EE001E5 | normalized_value, raw_value_non_strict, subject_text |
| PG-V01-S002-004 | S002 | commitment | DOC-S002-B0006 | 7 | subject_text_resolution | V02-CAND-19D7708836E648DD451DC275A7CDE15C72C1B1C5FF84F5A11775862E1A335E5D, V02-CAND-6E1EBF34E2B7CBC183E0F3FB094576C0BA1C3E45E11849FF6C759BF7BA107970, V02-CAND-844A087D210C9DA1F8FAF1F2398DEC47E605F14A4A1FFEED76B1768D9EE001E5 | normalized_value, raw_value_non_strict, subject_text |
| PG-V01-S002-005 | S002 | commitment | DOC-S002-B0008 | 9 | subject_text_resolution | V02-CAND-28054BC7B8A0CBC94A79C3D354B179B4D68CEEB79CEC2E4500F88E6D6C6F70EB, V02-CAND-5EDB3AC33B16A883131B873C6CA07C8A75CB82AE690CA82C6DC2ACA3DBBEF414, V02-CAND-699F719394A8F62A2276A3CACDAE8D5759F78E95CE0CC6E1BBE9E88327F39B6B | normalized_value, raw_value_non_strict, subject_text |
| PG-V01-S003-001 | S003 | action_status | DOC-S003-B0008 | 0 | evidence_segmentation | V02-CAND-C3A40D6813FDEB0B5ECAB4B84D2E9E8553A966B0BFBCB1C589676FB8795BB98E | normalized_value, raw_value_non_strict, subject_text, subject_type |
| PG-V01-S003-002 | S003 | budget | DOC-S003-B0010 | 0 | missing_predicate_coverage | none | no comparable candidate |
| PG-V01-S003-003 | S003 | budget | DOC-S003-B0011 | 0 | missing_predicate_coverage | none | no comparable candidate |
| PG-V01-S003-004 | S003 | metric | DOC-S003-B0013 | 0 | missing_predicate_coverage | none | no comparable candidate |
| PG-V01-S004-001 | S004 | requirement | DOC-S004-B0028 | 0 | evidence_segmentation | V02-CAND-00D7E056BC3C5242239257E538EC9B6C6F5A519328B65B79497B219B5ED8641A, V02-CAND-A95E90D851277FBC026505642C501A335B9D8CD806ACF768CDAC3CD6C40FE8DC, V02-CAND-4F5D96A0E6697FCB0704B1D8CFF299414F9F77B4BFDD9C49F68AF08F7C4052C3 | normalized_value, raw_value_non_strict, subject_text, subject_type |
| PG-V01-S004-002 | S004 | requirement | DOC-S004-B0047 | 1 | subject_text_resolution | V02-CAND-622E8DA1F50893B97C7C2A79202A6B4F3D7D491126E0FDFEFBAB1A6A131FFB6A, V02-CAND-00D7E056BC3C5242239257E538EC9B6C6F5A519328B65B79497B219B5ED8641A, V02-CAND-A95E90D851277FBC026505642C501A335B9D8CD806ACF768CDAC3CD6C40FE8DC | normalized_value, raw_value_non_strict, subject_text, subject_type |
| PG-V01-S004-003 | S004 | requirement | DOC-S004-B0058 | 1 | subject_text_resolution | V02-CAND-FA9089FBCB81B4329EAAEF24C5A2DD020A1787765630278EA51F53310B6BA4A2, V02-CAND-00D7E056BC3C5242239257E538EC9B6C6F5A519328B65B79497B219B5ED8641A, V02-CAND-A95E90D851277FBC026505642C501A335B9D8CD806ACF768CDAC3CD6C40FE8DC | normalized_value, raw_value_non_strict, subject_text, subject_type |
| PG-V01-S004-004 | S004 | requirement | DOC-S004-B0074 | 1 | subject_text_resolution | V02-CAND-00D7E056BC3C5242239257E538EC9B6C6F5A519328B65B79497B219B5ED8641A, V02-CAND-A95E90D851277FBC026505642C501A335B9D8CD806ACF768CDAC3CD6C40FE8DC, V02-CAND-4F5D96A0E6697FCB0704B1D8CFF299414F9F77B4BFDD9C49F68AF08F7C4052C3 | normalized_value, raw_value_non_strict, subject_text, subject_type |
| PG-V01-S004-005 | S004 | risk | DOC-S004-B0089 | 0 | evidence_segmentation | V02-CAND-0B7B89FD846C123B5D0CD237A7AFDCD0B2792B3171FA318BF4EAC5A2E20E48D1, V02-CAND-42620B366BD6F79C0EE02B3C979A2EF4FCDEFD9D5685A6E54F0F94015C3D4474, V02-CAND-7984959E15BA59435ADC6E6FCCB257F448BAE6B7AE7C82B9AB50CB331ACD1606 | normalized_value, raw_value_non_strict, subject_text, subject_type |
| PG-V01-S004-006 | S004 | decision | DOC-S004-B0110 | 0 | evidence_segmentation | V02-CAND-3D34DA160DF9D8672545FA569830A68D35796DD114A35CE03ACBA879433AAF82, V02-CAND-D936BE96E8670AE989DCA4CB6B96D738B60DA1EDFDA82399E7A65D2F0135EAA1 | normalized_value, raw_value_non_strict, subject_text, subject_type |
| PG-V01-S006-001 | S006 | metric | DOC-S006-B0013 | 6 | subject_text_resolution | V02-CAND-001619AD8EF442DF3C56467E4ED3CA22A1DAB22CB89421CA1007691214C37F09, V02-CAND-3FEE20D5D5233FFFE629DC1AEEB0F08B6460350C4D1F53F7688F8856C35A868A, V02-CAND-54965C74D9D5AD727299011D4B1D14672119B9B00D4DFAFE71848997A95E7AED | normalized_value, qualifier_missing:period, qualifier_missing:population, qualifier_value:metric_name, raw_value_non_strict, subject_text |
| PG-V01-S006-002 | S006 | metric | DOC-S006-B0022 | 0 | evidence_segmentation | V02-CAND-001619AD8EF442DF3C56467E4ED3CA22A1DAB22CB89421CA1007691214C37F09, V02-CAND-01CE97DABDEAFFFEB310856588E6E8DCFB666AD9975A0908ED33E9C4660214FE, V02-CAND-051386E7ED0D5C93896A419DCEDCF2999AC6038D7DA8E0D09C5C3586D150D954 | normalized_value, qualifier_missing:period, qualifier_missing:population, qualifier_value:metric_name, raw_value_non_strict, subject_text |
| PG-V01-S006-003 | S006 | metric | DOC-S006-B0035 | 5 | subject_text_resolution | V02-CAND-0DBB43E98182D4B0F80E21E1D0B91BB1F6B2397E392912EFB8CD58BE5FD0AB01, V02-CAND-31C8B387E407EC492456AFEE353F33192D6640CFB138B7D108B5C9E6232A0F6A, V02-CAND-CF15D65A2D523AA3B85CA615A7DBF407E87315E59E261DA79EAFAEDBBAC639C9 | normalized_value, qualifier_missing:period, qualifier_missing:population, qualifier_value:metric_name, raw_value_non_strict, subject_text |
| PG-V01-S006-004 | S006 | metric | DOC-S006-B0042 | 2 | subject_text_resolution | V02-CAND-A3699A477FD51D0DB8704CD4C74AF8E08FD53C12D5988C4B067F22877E23C3BE, V02-CAND-90FA2957531C11D77CC50971C7356757C3F0FD13D9B35C839A9BE22F31456F85, V02-CAND-61CEED39FC55D4C1EA03AB4BDA13C62E18C365B4BAE7B16912CD05CCC588C8C5 | normalized_value, qualifier_missing:period, qualifier_missing:population, qualifier_value:metric_name, raw_value_non_strict, subject_text |
| PG-V01-S006-005 | S006 | metric | DOC-S006-B0043 | 2 | subject_text_resolution | V02-CAND-75C3F019D05535261940E5572BAFC8576F851A50EAD921C4CA1419EBC0900C04, V02-CAND-82F05C05DD15ED294E8E1F72266F923DDF4E0E8B2BE8D1EDFFC261C3B1D18F4B, V02-CAND-001619AD8EF442DF3C56467E4ED3CA22A1DAB22CB89421CA1007691214C37F09 | normalized_value, qualifier_missing:period, qualifier_missing:population, qualifier_value:metric_name, raw_value_non_strict, subject_text |

## Sparse-gold limitation

The 25 owner-verified development facts are selected records, not a proven exhaustive annotation of all valid facts in the five documents. An unmatched candidate is therefore a strict unmatched candidate; this report does not relabel it as a manually confirmed false fact unless separate owner review establishes that conclusion.
