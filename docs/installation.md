# Installation

## Requirements

- Python 3.10+
- Git
- [Ollama](https://ollama.com) (for local LLM) **or** a Google Gemini API key

---

## 1. Clone the repository

```bash
git clone https://github.com/HPCI-Lab/yProv4SQA.git
cd yProv4SQA
```

## 2. Create and activate a virtual environment

```bash
python3 -m venv yProv4SQA_venv
source yProv4SQA_venv/bin/activate   # Linux / macOS
# yProv4SQA_venv\Scripts\activate    # Windows
```

## 3. Install the package

```bash
pip install -e .
pip install -r requirements.txt
```

## 4. (Optional) Set a GitHub token

GitHub allows only 60 API requests/hour without a token. For processing large repositories, set a personal access token:

```bash
export GITHUB_TOKEN=<your_token>
```

Verify the quota:

```bash
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
```

You should see `"limit": 5000`.

---

## 5. Install Ollama (for local LLM)

```bash
# Linux / macOS
curl -fsSL https://ollama.com/install.sh | sh

# Windows — download from https://ollama.com/download
```

Pull a model:

```bash
ollama pull llama3.2       # recommended — fast, ~15s per answer on GPU
ollama pull qwen2.5        # alternative — better structured tool calling
ollama pull qwen2.5:3b     # lightweight — works on 8 GB RAM
```

---

## Optional: GraphViz (for SVG graph output)

Required only if you use the `json2graph` command:

```bash
sudo apt install graphviz   # Ubuntu/Debian
brew install graphviz       # macOS
```
