pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126


pip install unsloth


# 1. Core RAG & Database
pip install chromadb pypdf sentence-transformers 

# 2. Environment & Utility
pip install python-dotenv

# 3. Unsloth & Optimization (Re-verify these are present)
pip install --upgrade "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
pip install --no-deps "xformers<0.0.27" "trl<0.9.0" peft accelerate bitsandbytes

