import os
import httpx
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "30"))

api = FastAPI(title="LLM Service", version="1.0.0")

class EvaluateRequest(BaseModel):
    qid: str
    direction: Literal["IT", "EN"]
    source: str
    user_answer: str

class EvaluateResponse(BaseModel):
    feedback: str
    correct: Optional[str] = None
    score: Optional[float] = None
    provider: str

@api.get("/health")
def health():
    return {"ok": True, "provider": PROVIDER}

def _mock(req: EvaluateRequest) -> EvaluateResponse:
    return EvaluateResponse(
        feedback="✅ Received (mock).",
        correct=None,
        score=None,
        provider="mock",
    )

async def _ollama(req: EvaluateRequest) -> EvaluateResponse:
    direction = "Italian → English" if req.direction == "IT" else "English → Italian"
    target_lang = "English" if req.direction == "IT" else "Italian"

    prompt = f"""
        You are a strict bilingual tutor. Please evaluate the user's translation of the source sentence.

        Direction: {direction}
        Source: "{req.source}"
        User: "{req.user_answer}"

        RULES:
        - The correct translation MUST be in {target_lang}
        - Output MUST follow the format exactly
        - No extra paragraphs, no headings, no blank lines
        - Do not add anything before "Verdict:"
        - Verdict is CORRECT if meaning is faithful and grammatical enough to be understood.

        OUTPUT FORMAT (EXACT):
        ```
        Verdict: CORRECT or WRONG
        Correct translation: <one sentence in {target_lang}>
        Feedback:
        - <bullet 1>
        - <bullet 2 (optional)>
        ```
        """

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}},
        )
        r.raise_for_status()
        text = (r.json().get("response") or "").strip()

    return EvaluateResponse(feedback=text, provider="ollama")

@api.post("/v1/evaluate", response_model=EvaluateResponse)
async def evaluate(req: EvaluateRequest):
    if PROVIDER == "mock":
        return _mock(req)
    if PROVIDER == "ollama":
        return await _ollama(req)
    raise HTTPException(status_code=501, detail=f"Provider not implemented: {PROVIDER}")
