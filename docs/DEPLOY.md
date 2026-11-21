# Deploying the rival service

The rival service (`worker/`) runs on Cloudflare and calls Gemini on Vertex AI with the course credits (decision D6). The game never holds a credential. The Worker holds one secret: a Google service account key.

Every step below is done by Adit or with Adit's explicit go-ahead (AGENTS.md):
- Deploying is publishing.
- Creating the key is credential creation.
- The smoke test makes paid calls.

## Before you start
- A Cloudflare account. In `worker/`, run `npx wrangler login` once. It opens a browser.
- `gcloud` signed in to your course Google Cloud project with the Vertex AI API enabled (the same project the midterm used).
- Your project ID, used below as `P`.

## 1. Create the service account and key
```sh
P=your-course-project-id
gcloud iam service-accounts create overload-rival --project="$P" \
  --display-name="Overload rival service"
gcloud projects add-iam-policy-binding "$P" \
  --member="serviceAccount:overload-rival@$P.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
gcloud iam service-accounts keys create ~/overload-rival-key.json \
  --iam-account="overload-rival@$P.iam.gserviceaccount.com"
```
The role only allows calling Vertex AI. If the last command fails because the project blocks key creation, stop there and ask the instructor which credential path to use.

## 2. Deploy and store the key
```sh
cd worker
npx wrangler deploy --var PROVIDER:vertex --var MODEL:gemini-3.5-flash-lite \
  --var GOOGLE_CLOUD_PROJECT:"$P" --var GOOGLE_CLOUD_LOCATION:global --var THINKING_BUDGET:0
npx wrangler secret put GCP_SERVICE_ACCOUNT_JSON < ~/overload-rival-key.json
rm ~/overload-rival-key.json
```
Deploy prints the service URL, `https://overload-rival.<your-subdomain>.workers.dev`. Keep it out of the repository: set it in your shell as `OVERLOAD_RIVAL_URL` and pass it to tools from there, so the public repo does not advertise a spend-capped endpoint. If Vertex rejects `THINKING_BUDGET:0` for this model, deploy again with `--var THINKING_BUDGET:""`. Until then the game falls back to the neutral tactic.

The Worker enforces these limits itself:
- 2 attempts per session
- 1,000 input tokens
- 512 output tokens
- a 4.5 s deadline
- a daily reservation cap of $1.00 (`DAILY_BUDGET_USD`)

## 3. Smoke test (3 paid calls, under $0.01)
```sh
cd ..
uv run python tools/rival/smoke.py https://overload-rival.<your-subdomain>.workers.dev
uv run python tools/rival/smoke.py https://overload-rival.<your-subdomain>.workers.dev \
  --expect-timeout --deadline 0.05
```
The first run checks:
- two isolated sessions get their own answers
- every answer passes validation
- a third request is refused

The second run forces the game's deadline below the service's reply time, so the game must start the fight on the neutral tactic. Together they are the November 23 checkpoint evidence. Save both outputs with the date, the deployed version ID and the model the replies report.

## After an evidence or tactics config change
The Worker reads `config/evidence.json` and `config/tactics.json` at build time, so a new evidence version (version 4 on Nov 19: power uses by family) or updated tactic guidance (`config/tactics.json` version 3 on Nov 21) needs a redeploy from `main` before live play. Until then a client on a newer evidence version sends kinds the deployed Worker rejects (falling back to the neutral tactic, labelled fallback in the trace), and an outdated Worker serves older tactic guidance. After the redeploy, run the smoke test above and save its output as new checkpoint evidence.

## Turning it off
- `npx wrangler delete` removes the Worker.
- Deleting the key in Google Cloud revokes access immediately.
- The game keeps working with live mode off, using the neutral tactic.
