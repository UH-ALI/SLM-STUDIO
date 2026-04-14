pip install unsloth sentence-transformers chromadb pypdf python-dotenv google-genai trl

python data_generator_v2.py          # generates train.jsonl
python finetune_v2.py                # trains and saves adapter
python rag_inference.py --build      # builds vector store + starts chat
python rag_inference.py              # subsequent runs skip the --build step