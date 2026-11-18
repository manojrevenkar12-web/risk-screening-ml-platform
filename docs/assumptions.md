# Assumptions

| What | Value | Where |
|---|---|---|
| Documents per day | 2.5 million, 30 languages, English 36%, the smallest 0.4% | world |
| Incidents | 7% of documents; 12% of harmless documents use risk words in a harmless sense | world |
| Syndicated copies | 30% of documents | world |
| Analyst labels | 2% label noise | world |
| Scorer | a 4-vCPU pod runs the in-house transformer at 40 documents per second (the ONNX stand-in here runs about 34,000 per second); €0.19 per pod-hour | config |
| LLM tagging | pay-as-you-go €0.0004 per 1,000 tokens; a provisioned unit €0.45 per hour for 25,000 tokens per minute; 650–1,400 tokens per document; quota 45 M tokens per hour per region | config |
| Throttling | 18% of pay-as-you-go calls answered 429 in the primary region's business hours, 2% otherwise; the second region is busy at other hours | world |
| LLM versions | current: 93% tagging accuracy; successor: 95%, but 81% of answers parse under prompt v1 (99.4% under v2) | world |
| LLM on everything | assumed to find every incident, which flatters that design on recall | evals |
| Reviewers and analysts | their labels are as good as the label noise; their time is not costed beyond the label budget | |

The relevance model is TF-IDF with logistic regression, standing in for a fine-tuned multilingual transformer. The
platform around it does not depend on which model sits inside: label allocation, thresholds, gate, export, registry,
serving and capacity planning. The synthetic languages share vocabulary within families, as related languages do.
