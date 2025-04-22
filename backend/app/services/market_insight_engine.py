from app.services.phi3_engine import query_phi3

def analyze_market_text(text: str) -> str:
    prompt = f"""
    You're a maritime analyst. Given the following market text, extract:
    - Key insights
    - Active routes
    - Price anomalies
    - Cargo type patterns
    - Risk alerts

    TEXT:
    {text}

    STRUCTURED RESPONSE:
    """
    return query_phi3(prompt)
