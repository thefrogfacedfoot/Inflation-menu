# Phase 1c — parser validation

Random 5 samples per target, in-window. No DB writes — pure parser exercise.

| Target | Hits | Mean items/page | Best sample (items) | Failure modes |
|---|---:|---:|---:|---|
| Singapore: grabfood-sg | 4/5 | 0.8 | 1 |  |
| Mexico: tripadvisor-mx | 0/5 | 0.0 | 0 | 0 items / page (parser found no prices) |
| United States: menupages | 4/5 | 201.4 | 544 |  |
| India: zomato-ncr | 1/5 | 0.2 | 1 |  |
| Indonesia: zomato-jakarta | 2/5 | 0.4 | 1 |  |
