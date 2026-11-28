# SupportGPT

A fine-tuned customer support AI assistant built using **Qwen2.5-0.5B-Instruct**, **BF16 LoRA**, and **Hugging Face Transformers**. The project focuses on training a lightweight language model to answer common customer support questions and deploying it through a web-based chat application.

## Project goals

- Build a customer support assistant using an open-source pretrained language model.
- Fine-tune the model on customer support instruction-response data.
- Fine-tune the base model with LoRA in BF16.
- Evaluate the fine-tuned model against the original base model.
- Build a web interface for interacting with the model.
- Deploy the application for public access.

## Technology stack

| Component | Technology |
|---|---|
| Base model | Qwen2.5-0.5B-Instruct |
| Deep learning | PyTorch |
| Model framework | Hugging Face Transformers |
| Dataset processing | Hugging Face Datasets |
| Fine-tuning | PEFT, TRL |
| Training precision | BF16 |
| Training method | LoRA (PEFT) |
| Backend | FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Environment and packages | Python 3.12, uv |

## Dataset

**Bitext Customer Support LLM Chatbot Training Dataset**

https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset

The dataset contains customer questions, expected responses, categories and intents covering common customer support scenarios.

## Training method and configuration

The trained model is a LoRA adapter on top of the unchanged
`Qwen/Qwen2.5-0.5B-Instruct` base model. Training examples come from the
Bitext customer-support dataset after policy-aware cleaning, plus the
training-only examples in `data/curated/support_supplemental.jsonl`. The
preparation pipeline removes unsafe or unsupported targets, groups duplicate
prompts to avoid split leakage, creates a category-stratified validation split,
and uses deterministic square-root oversampling to reduce category imbalance.

The adapter is trained with BF16 supervised fine-tuning using TRL's
`SFTTrainer` and completion-only loss. The key settings are:

| Setting | Value |
|---|---:|
| LoRA rank / alpha / dropout | 16 / 32 / 0.05 |
| LoRA target modules | q/k/v/o projections; gate/up/down projections |
| Epochs | 2 |
| Learning rate | 0.0002 |
| Per-device batch / gradient accumulation | 4 / 2 |
| Effective batch size | 8 on one GPU |
| Maximum sequence length | 768 tokens |
| Warmup / weight decay | 3% / 0.01 |
| Optimizer / scheduler | AdamW / cosine |
| Precision / seed | BF16 / 42 |

The best checkpoint is selected by validation loss and saved as an adapter;
the base-model weights are not fine-tuned or merged. See
[training_config.py](configs/training_config.py) and
[train.py](src/support_gpt/training/train.py) for the full configuration and
training implementation.

## Hardware

Development hardware: NVIDIA GeForce RTX 5060 Laptop GPU with 8 GB VRAM.

The model will initially be trained and tested locally. Deployment will use a suitable cloud hosting environment.

## Preparing policy-clean training data

Before training a candidate adapter, prepare a separate cleaned dataset:

```powershell
uv run python -m support_gpt.data.prepare_dataset
```

The preparation step reuses the inference support policy, rewrites only
recognized generic contact/resource placeholders into general official-channel
guidance, and drops examples with customer-specific placeholders, unsupported
action promises, first-party company claims, unqualified account or website
features, and hard-coded policy or contact details. These conservative checks
reduce known risks but do not replace semantic review. The preparation step
also excludes templated user prompts, keeps identical user prompts in the same
split, checks for overlap with the fixed evaluation cases, and validates every
target before training. The validation split is stratified by category while
keeping duplicate normalized user prompts together. The training split uses
deterministic square-root oversampling for smaller categories; all original
training rows remain, while added repetitions are recorded in the quality
report. This reduces category skew without forcing every category to repeat
up to the largest category's count. The supplemental examples in
`data/curated/support_supplemental.jsonl` are training-only.

Outputs go to `data/processed/support_gpt_safe/`; the existing processed files
are left unchanged. A row-count and category audit is written to
`data/processed/support_gpt_safe/data_quality_report.json`. The next training
run writes to `models/adapters/support-gpt-lora-candidate/`, leaving the current
`models/adapters/support-gpt-lora/final` adapter intact. Review the audit and
candidate data before starting training.

After review, start training explicitly with:

```powershell
uv run python -m support_gpt.training.train
```

## Model evaluation

The fixed, hand-written evaluation cases are in
`data/evaluation/support_gpt_eval.jsonl`. They are maintained separately from
the Bitext training and validation files. Run the paired base-model/LoRA
evaluation from the repository root with:

```powershell
uv run python -m support_gpt.evaluation.evaluate
```

The runner uses greedy generation with a fixed seed and token limit, evaluates
each case against both model variants, and records the resolved model revision,
software versions, run configuration, and SHA-256 hashes of the test set and
adapter files. To pin the base model to a specific Hugging Face revision, pass
its revision identifier:

```powershell
uv run python -m support_gpt.evaluation.evaluate --base-revision "commit-hash"
```

To evaluate a candidate adapter without replacing the current adapter, specify
its directory:

```powershell
uv run python -m support_gpt.evaluation.evaluate --adapter-path "models/adapters/support-gpt-lora-candidate/final" --output-dir "reports/candidate"
```

The run writes `reports/evaluation_results.csv`,
`reports/evaluation_report.json`, and `reports/evaluation_report.md`. The CSV
includes response text, per-case latency and errors, and blank human-review
columns. To enter human ratings and regenerate the summaries, fill those
columns in the CSV and run:

```powershell
uv run python -m support_gpt.evaluation.compare_models
```

Human ratings use a 1–5 scale: 1 = poor, 3 = partially meets the criterion,
and 5 = fully meets it. Rate relevance to the request, factual correctness
against the case criteria, practical helpfulness, and compliance with the
requested behavior separately. These ratings are not generated automatically;
the reports keep them distinct from automated checks. Automated checks cover
generation failures/empty responses, latency, reference-conditioned
loss/perplexity where a reference answer is provided, unresolved placeholders,
known patterns for unsupported action claims, and a narrow prompt-injection
disclosure check. They are indicators, not a complete safety or answer-quality
judgment. The FastAPI contract checks use controlled fake model responses and
are reported separately; they test request validation, response validation,
and session/order-ID retention, not model answer quality. ROUGE, BLEU, and
exact match are not used as standalone measures of customer-support quality.
The current fixed evaluation cases have already been inspected and should be
treated as a development set. A separate 26-case holdout is available at
`data/evaluation/support_gpt_holdout.jsonl`; it was authored after training and
checked for normalized prompt overlap with training and the earlier evaluation
set. Run it separately to preserve the distinction:

```powershell
uv run python -m support_gpt.evaluation.evaluate --dataset data/evaluation/support_gpt_holdout.jsonl --output-dir reports/fresh-holdout
```

### Recorded base-versus-adapter results

The following results are from the checked-in evaluation reports. Both runs
use greedy decoding; latency is hardware- and software-dependent. Error,
empty-response, and placeholder-leakage rates were 0% for both models in both
runs. “Unsupported-action claims” are pattern-based automated flags, not a
complete semantic safety measure.

| Dataset | Model | Cases | Safety checks passed | Unsupported-action claims | Mean latency | Mean loss | Mean perplexity |
|---|---|---:|---:|---:|---:|---:|---:|
| Earlier evaluation (development) | Base | 18 | 94.4% | 5.6% | 2.593 s | 2.826 | 19.941 |
| Earlier evaluation (development) | Fine-tuned adapter | 18 | 100% | 0% | 2.977 s | 2.468 | 19.430 |
| Fresh holdout | Base | 26 | 96.2% | 3.8% | 2.799 s | n/a | n/a |
| Fresh holdout | Fine-tuned adapter | 26 | 100% | 0% | 1.828 s | n/a | n/a |

Loss and perplexity are unavailable for the fresh holdout report. The automated
application contract checks are reported separately and use controlled fake
model responses; they are not measures of language-model answer quality.

An exploratory AI-assisted rubric review also rated relevance, correctness,
helpfulness, and instruction-following from 1 (poor) to 5 (fully meets):

| Dataset | Model | Relevance | Correctness | Helpfulness | Instruction following |
|---|---|---:|---:|---:|---:|
| Earlier evaluation (development) | Base | 3.611 | 2.333 | 2.667 | 2.444 |
| Earlier evaluation (development) | Fine-tuned adapter | 3.167 | 2.278 | 2.278 | 2.278 |
| Fresh holdout | Base | 3.615 | 2.038 | 2.269 | 2.115 |
| Fresh holdout | Fine-tuned adapter | 3.462 | 3.115 | 2.808 | 3.308 |

These rubric scores are exploratory assistant-generated reviews, **not human
ratings or independent judge results**. The fresh holdout contains only two
cases per category, so its scores are diagnostic rather than statistically
conclusive. Reviewers found serious answer-quality and safety failures in both
models that automated checks did not catch. The evidence is mixed: the adapter
improved several fresh-holdout rubric dimensions and reduced automated
unsupported-action flags, but it did not improve every dimension or pass every
case. Do not treat these results as proof that the fine-tuned model is
universally better.

See the detailed
[development evaluation report](reports/candidate-balanced/evaluation_report.md),
[fresh-holdout report](reports/fresh-holdout/evaluation_report.md), and their
separate [development review](reports/candidate-balanced/ai_assisted_review_summary.md)
and [holdout review](reports/fresh-holdout/ai_assisted_review_summary.md).

## NovaMart demo application

The FastAPI application is a fictional NovaMart storefront with a product
catalogue, demo customer profiles, simulated orders and invoices, and an
integrated SupportGPT experience. SQLite is initialized and seeded on startup.
The sample account is `alex.morgan@example.com` (choose **Use the sample
account** on the account page); it includes order `NM-20481`.

The default app mode does not load model weights, so it starts quickly and can
answer order questions from verified SQLite records. For general support it
provides a short demo guidance response. To load the fine-tuned model on a
machine that has the model files, required ML packages, and sufficient memory,
install the ML dependencies with `uv sync --extra ml` and set
`SUPPORTGPT_LOAD_MODEL=1`. The model is given selected, ownership-checked
order context, and order status remains simulated.

Run locally from the repository root:

```powershell
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Set `SUPPORTGPT_DATABASE_PATH` to choose another
SQLite file. All product, customer, order, invoice, ticket, and customer-scoped
conversation records are stored in that database. No real payment, refund,
cancellation, shipping, or live human-agent workflow is connected. Customer
conversations and selected-order context persist in SQLite and are reloaded for
follow-up messages. Tracking replies use ownership-checked order records;
refunds and cancellations are guidance-only. The chat can create a demo ticket
when a customer explicitly asks for a person, and it offers a ticket form for
refund, cancellation, or order-issue requests. Tickets go only to a sample
queue; no support staff are notified.

### What to commit to GitHub

The root `.gitignore` excludes local virtual environments, secrets (while
keeping `.env.example`), SQLite files, downloaded/raw and generated/processed
datasets, model weights/checkpoints, and training logs. The small curated and
evaluation datasets, application source, tests, configuration, lockfile, and
evaluation reports remain eligible for commit. Fine-tuned weights are not in
the GitHub repository; obtain or train the adapter separately before enabling
`SUPPORTGPT_LOAD_MODEL=1`. The default demo mode does not need those weights.

### Deployment choices

| Option | Suitable for | Notes |
|---|---|---|
| Render Web Service + persistent disk | Simplest single-instance demo | Mount a persistent disk and point `SUPPORTGPT_DATABASE_PATH` at it. SQLite must not live on the ephemeral app filesystem. |
| Railway service + volume | Quick demo and preview deployments | Attach a volume at the database path and run a single app replica while using SQLite. |
| Fly.io app + volume | More control over the app VM | Volumes are local to a machine/region; keep one writer and plan backups. |
| VPS/container host + Docker volume | Full deployment control | Persist the SQLite file in a mounted volume and handle TLS, updates, monitoring, and backups. |
| Managed PostgreSQL (Neon, Supabase, Render, Railway) | Multiple replicas or production growth | Replace the SQLite repository with PostgreSQL and use migrations before scaling horizontally. |

For model inference, keep the web app and GPU inference service separate if the
chosen app host has no GPU. A GPU VM or managed inference endpoint can host the
fine-tuned model; alternatively, use a hosted LLM API behind the FastAPI
backend. Store provider credentials as server-side environment secrets, never
in browser JavaScript. The non-model demo mode is the least expensive option
for an initial UI deployment.

### Example: deploy on Render with SQLite

1. Push the repository to a Git provider and create a **Web Service** from it.
2. Select a Python runtime compatible with the project's Python requirement.
3. Configure the build command as `pip install uv && uv sync --frozen`.
4. Configure the start command as
   `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
5. Add a persistent disk mounted at `/var/data`.
6. Set `SUPPORTGPT_DATABASE_PATH=/var/data/supportgpt.sqlite3` and
   `SUPPORTGPT_LOAD_MODEL=0` in the service environment.
7. Deploy, then check `/api/health` and visit the service URL. Startup creates
   the schema and sample records automatically.
8. Back up the SQLite file on a schedule. Test restore procedures and avoid
   running multiple replicas against the same SQLite file.
9. To enable the fine-tuned model, provision sufficient memory (preferably a
   GPU), change the build command to include `--extra ml`, make the model and adapter artifacts
   available to the service, and set `SUPPORTGPT_LOAD_MODEL=1`. Check model
   startup logs and `/api/health` before directing traffic to it.

For any real customers, replace the email-only demo profile with proper
authentication and authorization, add CSRF/rate-limit/privacy controls, and
use a production database. Email entry here is not authentication: the demo
contains no sensitive customer data, and ownership checks are for safe
simulation rather than a security boundary. Refunds, cancellations, invoices,
orders, delivery updates, and support tickets are simulated records only.

## AWS EC2 deployment

The Docker deployment runs the FastAPI storefront and CPU-only SupportGPT
model on one x86_64 Ubuntu EC2 instance, with Caddy handling HTTPS. The model
loads once at startup. The Hugging Face base model is cached under `/data`;
the LoRA adapter is downloaded from `SUPPORTGPT_ADAPTER_REPO` (or loaded from
`SUPPORTGPT_ADAPTER_PATH`, which takes priority). If model initialization
fails, the web app stays available in demo mode. CPU inference can be slow,
and 4 GB RAM is tight for Python, PyTorch, and the float32 model; monitor
memory and consider an 8 GB instance if startup is killed or inference swaps.

1. Launch an x86_64 Ubuntu EC2 instance. Attach persistent EBS storage with
   enough room for the Docker image, base model cache, adapter, and SQLite DB.
2. In the EC2 security group, allow SSH (`22`) only from your IP and HTTP/HTTPS
   (`80`, `443`) from the intended audience. Point your domain's DNS `A` record
   at the instance's stable public/Elastic IP; Caddy needs public access to
   ports 80 and 443 to provision certificates.
3. Install Docker and Compose, then clone the repository:

   ```bash
   sudo apt update
   sudo apt install -y git docker.io docker-compose-v2
   sudo systemctl enable --now docker
   git clone <your-github-repository-url>
   cd Support-GPT
   ```

4. Create the private runtime environment file:

   ```bash
   cp .env.example .env
   nano .env
   ```

   Set `DOMAIN` to the DNS name pointed at this EC2 instance. To run the
   fine-tuned model, set `SUPPORTGPT_LOAD_MODEL=1` and
   `SUPPORTGPT_ADAPTER_REPO=your-huggingface-user/your-adapter-repo`.
   Set `HF_TOKEN` to a read token if the adapter repository is private; public
   adapters do not require a token. Leave `SUPPORTGPT_ADAPTER_PATH` empty
   unless the adapter has been placed on the mounted `/data` volume. Keep `.env`
   private and never commit it.
5. Build and start both containers:

   ```bash
   sudo docker compose up --build -d
   sudo docker compose logs -f app caddy
   ```

   The app listens only on the Docker network at port 8000. Caddy is the only
   service publishing ports 80 and 443. The database defaults to
   `/data/supportgpt.sqlite3`, and `HF_HOME` is `/data/hf-cache`; both survive
   container restarts through the Compose volume.
6. Confirm `https://your-domain.example/api/health` reports
   `"model_loaded": true`, the expected device, and adapter source. If model
   download/loading fails, inspect `sudo docker compose logs app`; health
   remains available and chat uses demo responses. Do not send an HF token in
   a browser request or expose port 8000 publicly.

The adapter repository must contain the PEFT adapter files produced by the
project's training workflow. The `models/` folder is intentionally excluded
from Git and the Docker build context, so the adapter must be available from
Hugging Face or be placed on `/data` separately. The production image installs
the Linux CPU PyTorch wheel from the lockfile; it does not install CUDA
libraries. The application rate-limits chat to 10 requests per IP per minute.

### Files added or changed for EC2/Docker deployment

- [Dockerfile](Dockerfile): x86_64 Python 3.12 image, CPU PyTorch extra,
  non-root app user, and Uvicorn startup.
- [docker-compose.yml](docker-compose.yml): persistent app data volume and
  Caddy reverse proxy.
- [Caddyfile](Caddyfile): HTTPS reverse proxy using the `DOMAIN` variable.
- [.dockerignore](.dockerignore): keeps local environments, secrets, data,
  model weights, reports, and logs out of Docker build context.
- [.env.example](.env.example): deployment variables and no real secrets.
- [pyproject.toml](pyproject.toml): CPU/Linux PyTorch source, test extra,
  pytest configuration.
- [uv.lock](uv.lock): frozen dependencies including CPU and test wheels.
- [app/main.py](app/main.py): lifespan model startup, proxy rate limiting,
  database initialization, and FastAPI app setup.
- [app/api/routes/chat.py](app/api/routes/chat.py): health metadata and chat API.
- [app/services/chat_service.py](app/services/chat_service.py): one-time model
  state and adapter/device metadata.
- [app/services/rate_limiter.py](app/services/rate_limiter.py): in-memory chat
  throttling.
- [src/support_gpt/inference/model.py](src/support_gpt/inference/model.py):
  float32 CPU/BF16 GPU model loading and configurable adapter source.
- [tests/test_deployment_smoke.py](tests/test_deployment_smoke.py): `/`,
  `/api/health`, and simulated order chat checks.
- [README.md](README.md): this AWS deployment guide.

## Project status

**In development — NovaMart demo storefront and SQLite-backed support flow.**