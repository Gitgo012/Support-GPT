# SupportGPT Evaluation Report

## Run information

- **Dataset:** data\evaluation\support_gpt_holdout.jsonl
- **Dataset Sha256:** c7753e989be2b48c69e0231d895bc56ba9b89f40ba7d99c4c0bb5d2e41dba333
- **Dataset Cases:** 26
- **System Prompt Sha256:** 0b9438d8f8b133fcc7f9506daf8cc43aa8fa9a94d6c1435b5a90ded52535fdc7
- **Base Model:** Qwen/Qwen2.5-0.5B-Instruct
- **Resolved Base Revision:** None
- **Adapter Path:** models\adapters\support-gpt-lora-candidate\final
- **Adapter Weights Sha256:** 5f967cfc24e4c1ca3178d4259b00a8d3c90a144c20d1b6dd67547945795c0233
- **Adapter Config Sha256:** 31a89ee077c9cae2be6f27638498c91ca60a752a748bc75d98db8ab099dacda6
- **Seed:** 42
- **Max New Tokens:** 180
- **Do Sample:** False
- **Warmup Tokens Per Adapter Mode:** 1
- **Dtype:** bfloat16
- **Device:** cuda:0
- **Torch Version:** 2.11.0+cu130
- **Transformers Version:** 5.23.0
- **Peft Version:** 0.21.3
- **Run Started Utc:** 2026-11-20T09:40:59.354936+00:00

## Automated model measurements

| Model | Cases | Error rate | Empty rate | Placeholder leakage | Unsupported-action claims | Safety checks passed | Mean latency (s) | Mean loss | Mean perplexity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 26 | 0.000 | 0.000 | 0.000 | 0.038 | 0.962 | 2.799 | n/a | n/a |
| fine_tuned | 26 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.828 | n/a | n/a |

## Per-category comparison

| Category | Model | Cases | Error rate | Empty rate | Unsupported-action claims | Safety checks passed | Mean latency (s) | Mean loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| account_issues | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 3.017 | n/a |
| account_issues | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 1.290 | n/a |
| ambiguous_questions | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 0.784 | n/a |
| ambiguous_questions | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.922 | n/a |
| cancellation | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.451 | n/a |
| cancellation | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.534 | n/a |
| delivery_shipping | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 3.992 | n/a |
| delivery_shipping | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 1.556 | n/a |
| invoices | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.866 | n/a |
| invoices | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 1.601 | n/a |
| missing_information | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 3.808 | n/a |
| missing_information | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 1.035 | n/a |
| multi_turn_conversations | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.921 | n/a |
| multi_turn_conversations | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.670 | n/a |
| order_tracking | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.533 | n/a |
| order_tracking | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 1.586 | n/a |
| payments | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.445 | n/a |
| payments | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 1.320 | n/a |
| prompt_injection_safety | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.699 | n/a |
| prompt_injection_safety | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.378 | n/a |
| refunds | base | 2 | 0.000 | 0.000 | 0.500 | 0.500 | 3.957 | n/a |
| refunds | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 1.538 | n/a |
| subscriptions | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 3.942 | n/a |
| subscriptions | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 1.163 | n/a |
| unsupported_action_requests | base | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 0.966 | n/a |
| unsupported_action_requests | fine_tuned | 2 | 0.000 | 0.000 | 0.000 | 1.000 | 2.175 | n/a |

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
