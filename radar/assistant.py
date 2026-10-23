"""Free, local TF-IDF extractive NLP. Not an LLM or an eligibility oracle."""
from functools import lru_cache

@lru_cache(maxsize=256)
def evidence(description):
    import re
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    sentences=[s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',description) if len(s.strip())>30]
    if not sentences: return []
    query='contract corp to corp C2C hourly remote United States data engineering Snowflake Databricks Azure AWS GCP Fabric Palantir Cortex'
    matrix=TfidfVectorizer(stop_words='english').fit_transform([query]+sentences)
    scores=cosine_similarity(matrix[0],matrix[1:]).ravel()
    indices=sorted(range(len(sentences)),key=lambda i:float(scores[i]),reverse=True)[:3]
    return [sentences[i][:700] for i in sorted(indices) if scores[i]>0]
