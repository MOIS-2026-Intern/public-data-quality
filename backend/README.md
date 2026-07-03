# public-data-quality-be

Backend service for public data quality analysis and validation workflows.

## Structure

- `agents/`: domain-specific workflow and validation agents
- `core/`: shared core logic
- `data/`: local sample and reference datasets
- `graph.py`, `service.py`, `web.py`: application entry modules

## Notes

- `.env` files are ignored by Git.
- Python cache and common local artifacts are ignored via `.gitignore`.
- LLM integration uses the OpenAI Chat Completions API by default:
  `https://api.openai.com/v1/chat/completions`
- Enter the OpenAI API key in the web form before running analysis. The key is sent with the request and is not written to `.env` or included in the response.
- The default strategy uses `gpt-4o-mini` for fast routing, then uses `gpt-4o` for strong/precision validation.
- Optionally use `OPENAI_API_KEY` as a backend fallback for local development.
- Override models with `OPENAI_FAST_MODEL`/`OPENAI_STRONG_MODEL`, `OPENAI_MODEL`, or the web form's model values.
- Override the endpoint with `OPENAI_API_URL` if a compatible gateway is required.
