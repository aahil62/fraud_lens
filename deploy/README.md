# Deploy

The live demo, https://fraud-lens-r3t0.onrender.com, is a free **Render** web service built from the root
`Dockerfile`. Render redeploys on every push to `main`. The container runs `scripts/serve.py`: the bank
simulator and API on 127.0.0.1, the Next.js console on `$PORT`, and demo data that resets on every boot.

Render sits behind Cloudflare, so the Dockerfile sets `FRAUDLENS_CLIENT_IP_HEADER=cf-connecting-ip` and
the rate limits key on the visitor's address. uvicorn runs with `--no-proxy-headers`, and Next
compression is off so `/ops/events` streams.

## Hugging Face Space (optional, needs a paid plan)

Docker Spaces now need a paid Hugging Face plan, so this path is kept but unused.

- `hf-space/README.md` is the Space's front matter (`sdk: docker`, `app_port: 7860`).
- `scripts/deploy_hf.sh <user>/<space>` uploads the committed `HEAD` (without `docs/`) to an existing
  Docker Space, using that README. You create the Space and run `hf auth login` yourself first.
