# 5. Migrate LLM versions before they retire, through a gate

## Context
Azure OpenAI retires model versions on announced dates and can upgrade a deployment automatically. The successor is
usually better at the task, but it can break an output format the pipeline parses.

## Decision
- Deployments use `NoAutoUpgrade`.
- 21 days before a retirement, the platform runs every prompt variant on the successor against the analysts' topic
  golden set.
- It migrates to the first variant whose answers parse 99% of the time and whose accuracy is no worse.
- If no variant passes, it escalates to a person with the date.

## Consequences
On dev, the successor under the old prompt parses only about 84% of answers; prompt v2 parses 99%. Letting the cloud
upgrade at retirement leaves about 6% of incidents untagged for every day afterwards.
