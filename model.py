from transformers import PreTrainedTokenizerFast, GPT2LMHeadModel
import torch
import numpy as np

tokenizer = PreTrainedTokenizerFast.from_pretrained("skt/kogpt2-base-v2")
model = GPT2LMHeadModel.from_pretrained("skt/kogpt2-base-v2")
model.eval()

def get_embedding(text: str):
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs, output_hidden_states=True)
    last_hidden = outputs.hidden_states[-1]
    sentence_embedding = torch.mean(last_hidden, dim=1).squeeze().cpu().numpy()
    return sentence_embedding

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
