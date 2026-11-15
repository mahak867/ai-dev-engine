"""Run the whole team on a local or self-hosted model.

Any server that speaks the OpenAI chat API works: LM Studio, vLLM, llama.cpp
server, LiteLLM, or OpenAI itself.

    export OPENAI_BASE_URL=http://localhost:1234/v1   # LM Studio's default
    python examples/local_model.py
"""
import apex

result = apex.generate(
    "CLI tool that converts CSV files to JSON, with tests",
    name="csv2json",
    output_dir="out",
    model="openai/qwen2.5-coder-14b",   # "openai/<whatever id your server exposes>"
)
print(result.path, result.quality_score)
