# Blinkit Category-Exploration Discovery Engine

AI-powered review/feedback analysis pipeline that mines public user feedback
about Blinkit (App Store, Play Store, Reddit, YouTube, complaint forums) to
generate **hypotheses about why users don't explore new product categories** —
with evidence strength, source triangulation, and a validation layer.

> Output = candidate barriers/drivers with evidence strength, **not** settled
> truth. Hypotheses feed a downstream survey + user interviews.

## Layout

```
scrapers/        one module per source → data/raw_<source>.jsonl
llm_client.py    provider-agnostic LLM client (Groq primary, Gemini fallback)
data/            all pipeline inputs/outputs (committed so the deployed UI can read them)
```

Full pipeline docs, setup, and deploy instructions land here as the build
progresses (see `.env.example` for required keys).

## Setup (so far)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in real keys
```
