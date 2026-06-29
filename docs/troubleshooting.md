# Troubleshooting

---

## Ollama not responding

```bash
ollama serve        # start the server
ollama list         # check the model is downloaded
curl -s http://localhost:11434/api/tags   # verify the API is reachable
```

---

## Model not found

```bash
ollama pull llama3.2    # download the model first
```

---

## Out of memory (OOM)

Use a smaller model:

```bash
prov-chat prov_output.json --model qwen2.5:3b    # 2 GB VRAM — works on 8 GB RAM
```

Avoid `llama3.3:70b` with large provenance documents — it causes OOM.

---

## Tool not calling correctly / wrong answers

`qwen2.5` handles structured tool calling better than `llama3.2` for some query types:

```bash
prov-chat prov_output.json --model qwen2.5
```

---

## GitHub rate limit hit

```
Error: 403 rate limit exceeded
```

Set a personal access token:

```bash
export GITHUB_TOKEN=<your_token>
```

---

## No SQAaaS reports found for repository

```
No SQAaaS assessment reports found for "myrepo".
The project may not be registered with SQAaaS.
```

The fetcher looks for `eosc-synergy/<repo>.assess.sqaaas` on GitHub. The repository must be registered with SQAaaS. Check at [https://sqaaas.eosc-synergy.eu/](https://sqaaas.eosc-synergy.eu/).

---

## Invalid JSON uploaded

Make sure you are uploading a yProv4SQA provenance document (output of `process-provenance`), not a raw SQAaaS report. The file must contain `entity` and `activity` keys with `ex:assessment*` entries.

---

## yProvStore login fails

- Check that yProvStore is reachable: `curl -s http://yprov.disi.unitn.it:8000/health`
- Make sure you are using your **email** (not username) to log in
- Tokens expire — log out and log in again if you get a 401

---

## Port already in use

```bash
prov-chat prov_output.json --web --port 5001   # use a different port
```
