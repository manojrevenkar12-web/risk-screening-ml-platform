# 4. Provisioned throughput for the base load, pay-as-you-go in two regions for the rest

## Context
Pay-as-you-go is throttled when the region is busy and is capped by the deployment's quota. That bites exactly
during news spikes, when clients need alerts. Provisioned throughput sized for the peak hour sits idle most of the
day.

## Decision
- Buy the number of provisioned units that minimises (unit price × hours) + (pay-as-you-go price × tokens that spill
  over) on the forecast.
- Spill over first to the primary region's pay-as-you-go deployment, then to a second region.

## Consequences
On dev this costs €0.075 per 1,000 documents, against €0.083 for pay-as-you-go alone and €0.223 for peak-sized provisioning, with no incidents tagged late; without the second region 1.3% are late.
The prices are assumptions in config; with your contract's prices the planner picks a different number.
