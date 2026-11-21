# AI-assisted review: fresh holdout

**Reviewer:** Assistant-generated exploratory ratings, not human ratings and not an independent LLM-judge result. Keep separate from all `human_*` report fields.

Scale: 1 = poor, 3 = partially meets, 5 = fully meets. There are two cases per category; these are diagnostic signals, not reliable category-level estimates.

| Model | Cases | Relevance | Correctness | Helpfulness | Instruction following |
|---|---:|---:|---:|---:|---:|
| base | 26 | 3.615 | 2.038 | 2.269 | 2.115 |
| fine_tuned | 26 | 3.462 | 3.115 | 2.808 | 3.308 |

## Key observations

Both models still produce serious reliability failures. The base makes unsupported or risky suggestions in refund, payment retry, locker access, cancellation, and injection cases. The candidate improves several cases (tracking-code limitation, refund guidance, invoice privacy, delivery locker, and unsupported redirect), but fails to retain a multi-turn order reference, gives a false instruction about an unexpected sign-in code, invents cancellation terms, and makes unsupported status/escalation claims.

The automated safety report flags one base response and zero candidate responses, yet the response review found additional unsupported claims that the pattern detector missed. Therefore the automated safety rate is not evidence that the candidate is safe.

The holdout was authored after training and has no exact normalized prompt overlap with training data or the earlier evaluation set. Because the reviewer knows the rubric and only two cases represent each category, this is a fresh diagnostic set?not a blinded human assessment or statistically conclusive benchmark.
