from langchain_openai import OpenAIEmbeddings, ChatOpenAI

def openai_gpt35(temperature: float=0.0) -> ChatOpenAI:
    return ChatOpenAI(model_name="gpt-3.5-turbo")

def openai_gpt4mini(temperature: float=0.0) -> ChatOpenAI:
    return ChatOpenAI(model_name="gpt-4.1-nano-2025-04-14")

def openai_gpt5nano(temperature: float=0.0) -> ChatOpenAI:
    return ChatOpenAI(model_name="gpt-5-nano")

def embedding_model_openai() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model="text-embedding-3-small")

def build_tree(paths, branch_name='main'):
    tree = {}
    for path in paths:
        parts = path.split('/')
        if branch_name not in parts:
            continue  

        branch_index = parts.index(branch_name)
        relevant_parts = parts[branch_index + 1:]  # everything after the branch
        current = tree
        for part in relevant_parts:
            current = current.setdefault(part, {})
    return tree



