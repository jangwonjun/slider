from model import get_embedding, cosine_similarity

command_templates = {
    "save": "저장해줘 카드 보관해줘 넣어줘 맡겨 저장",
    "delete": "지워줘 삭제 필요없어 빼 삭제해줘",
    "move": "꺼내줘 꺼내 필요해 줘 이동"
}

command_embeddings = {k: get_embedding(v) for k, v in command_templates.items()}

def classify_command(text: str):
    emb = get_embedding(text)
    sims = {cmd: cosine_similarity(emb, command_embeddings[cmd]) for cmd in command_embeddings}
    best_cmd = max(sims, key=sims.get)
    print(f"AI 분류: {best_cmd} (유사도: {sims[best_cmd]:.3f})")
    return best_cmd
