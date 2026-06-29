# HPC Setup

Run yProv4SQA on an HPC cluster with Ollama on a GPU node, tunneled to your local machine.

---

## Step 1 — Connect to HPC

```bash
ssh hpc3
```

## Step 2 — Request a GPU node

```bash
qsub -I -q shortGPUQ -l select=1:ncpus=8:ngpus=1:mem=32gb -l walltime=07:59:00
```

Wait until you get a prompt like:
```
(base) [youruser@hpc3-g04-n01 ~]$
```

## Step 3 — Start Ollama on the GPU node

```bash
module load CUDA/12.4.0
export PATH=$HOME/ollama/bin:$PATH
export OLLAMA_MODELS=$HOME/ollama/models
ollama serve &
```

Verify it is running:
```bash
curl -s http://localhost:11434/api/tags
```

## Step 4 — Forward port from GPU node to login node

```bash
ssh -N -R 11434:localhost:11434 hpc3-login0 &
```

## Step 5 — Tunnel from your local machine to the login node

```bash
ssh -N -L 11434:localhost:11434 youruser@hpc3-login0.yourinstitution.it
```

## Step 6 — Verify the tunnel from your local machine

```bash
curl -s http://localhost:11434/api/tags
```

You should see the list of available Ollama models.

## Step 7 — Start the app

```bash
prov-chat --web --port 5000 --model llama3.2
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## Model recommendations on GPU

| Model | VRAM | Speed | Notes |
|-------|------|-------|-------|
| `llama3.2` | ~3 GB | ~15s | recommended |
| `llama3.1:8b` | ~6 GB | ~30s | better reasoning |
| `llama3.3:70b` | >40 GB | very slow | avoid — causes OOM with large context |
