# SupportGPT Evaluation Report

## Run information

- **Adapter Config Sha256:** fbc5fb2d5ade50310248ddc0865168e52666dbcec4c0cb124ea39b69179dd929
- **Adapter Path:** models\adapters\support-gpt-lora\final
- **Adapter Weights Sha256:** 8bd21d9fb621b918ff89e33a866e9ee5381fbab67128f4d8a583f15154d7f785
- **Base Model:** Qwen/Qwen2.5-0.5B-Instruct
- **Dataset:** data\evaluation\support_gpt_eval.jsonl
- **Dataset Cases:** 18
- **Dataset Sha256:** 93bd800ab56ed52112602d728625bcbb67841f8d0c2fb72b5ea65ad746080454
- **Device:** cuda:0
- **Do Sample:** False
- **Dtype:** bfloat16
- **Max New Tokens:** 180
- **Peft Version:** 0.21.3
- **Resolved Base Revision:** 7ae557604adf67be50417f59c2c2f167def9a775
- **Run Started Utc:** 2026-11-19T13:50:59.927845+00:00
- **Seed:** 42
- **System Prompt Sha256:** 0b9438d8f8b133fcc7f9506daf8cc43aa8fa9a94d6c1435b5a90ded52535fdc7
- **Torch Version:** 2.11.0+cu130
- **Transformers Version:** 5.23.0
- **Warmup Tokens Per Adapter Mode:** 1

## Automated model measurements

| Model | Cases | Error rate | Empty rate | Placeholder leakage | Unsupported-action claims | Safety checks passed | Mean latency (s) | Mean loss | Mean perplexity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 18 | 0.000 | 0.000 | 0.000 | 0.056 | 0.944 | 4.489 | 2.826 | 19.941 |
| fine_tuned | 18 | 0.000 | 0.000 | 0.333 | 0.111 | 0.611 | 9.860 | 3.959 | 62.892 |

## Per-category comparison

| Category | Model | Cases | Error rate | Empty rate | Unsupported-action claims | Safety checks passed | Mean latency (s) | Mean loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| account_issues | base | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 7.553 | 2.285 |
| account_issues | fine_tuned | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 13.828 | 3.300 |
| ambiguous_questions | base | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 0.666 | n/a |
| ambiguous_questions | fine_tuned | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 6.296 | n/a |
| cancellation | base | 2 | 0.000 | 0.000 | 0.500 | 0.500 | 2.828 | 2.605 |
| cancellation | fine_tuned | 2 | 0.000 | 0.000 | 1.000 | 0.000 | 11.169 | 4.133 |
| delivery_shipping | base | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 6.460 | 3.363 |
| delivery_shipping | fine_tuned | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 11.610 | 4.566 |
| invoices | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 4.667 | 2.643 |
| invoices | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 9.237 | 3.761 |
| missing_information | base | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 7.745 | 2.275 |
| missing_information | fine_tuned | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 7.111 | 3.240 |
| multi_turn_conversations | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 4.546 | 2.097 |
| multi_turn_conversations | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 0.500 | 4.289 | 3.221 |
| order_tracking | base | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 4.954 | 2.469 |
| order_tracking | fine_tuned | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 2.556 | 3.534 |
| payments | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 3.680 | 3.650 |
| payments | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 0.500 | 15.954 | 4.969 |
| prompt_injection_safety | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 3.839 | n/a |
| prompt_injection_safety | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 0.500 | 16.390 | n/a |
| refunds | base | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 5.344 | 3.082 |
| refunds | fine_tuned | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 6.252 | 4.107 |
| subscriptions | base | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 7.580 | 3.896 |
| subscriptions | fine_tuned | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 7.993 | 4.897 |
| unsupported_action_requests | base | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 1.381 | 2.899 |
| unsupported_action_requests | fine_tuned | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 7.748 | 4.014 |

## Human assessment

Relevance, correctness, helpfulness, and instruction-following scores are human rubric ratings, not automated model scores. Blank values mean they have not been assessed.

| Model | Relevance | Correctness | Helpfulness | Instruction following |
|---|---:|---:|---:|---:|
| base | n/a | n/a | n/a | n/a |
| fine_tuned | n/a | n/a | n/a | n/a |

## FastAPI application checks

Application contract checks passed: 6/6. These use controlled test responses and are reported separately from raw model generations.

| Check | Result | Details |
|---|---|---|
| The API retains session history and customer-provided order IDs across turns. | PASS |  |
| Unresolved placeholders are replaced with a safe fallback. | PASS |  |
| Unsupported claims of completed account actions are rejected. | PASS |  |
| An empty model response is converted to the configured failure response. | PASS |  |
| Whitespace-only customer messages are rejected with HTTP 422. | PASS |  |
| Model failures are surfaced as HTTP 500, not a success-shaped response. | PASS |  |

## Interpretation and limitations

- Automated pattern checks are indicators, not a complete safety or quality judgment.
- Reference-conditioned loss/perplexity is reported only for cases with reference answers.
- Latency depends on hardware, software versions, and model-loading/device state.
- No ROUGE, BLEU, or exact-match score is treated as a standalone measure of support quality.
