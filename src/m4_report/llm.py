"""Provider-isolated LLM client (LangChain + Groq) with a cache<->API toggle.

The rest of M4 calls ``structured()`` and never imports the provider directly, so the
model/provider is swappable behind this one seam (D7 spirit).

Toggle ``ESA_LLM_USE_CACHE`` (default "true"):
  - true  + response cached  -> return the cached structured object (offline, no key).
  - true  + NOT cached       -> raise: export GROQ_API_KEY + ESA_LLM_USE_CACHE=false.
  - false + key              -> call the API, cache the result, return it.

The committed cache is the CANONICAL reference: an LLM is not bit-deterministic even at
temperature 0, so a regenerated response may differ slightly (= exploration mode, not a
bug). Never hardcode keys -- the key is read from the environment via config.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402

LLM_CACHE = config.CACHE_DIR / "m4_llm_cache.json"  # raw structured responses, keyed by content hash

T = TypeVar("T", bound=BaseModel)


def _use_cache() -> bool:
    """Read the toggle at call time (so tests can flip the env var)."""
    return os.getenv("ESA_LLM_USE_CACHE", "true").lower() != "false"


def _key(model: str, system: str, user: str) -> str:
    """Content hash identifying one (model, system, user) call -- the cache key."""
    raw = f"{model}\x00{system}\x00{user}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _load() -> dict:
    return json.loads(LLM_CACHE.read_text()) if LLM_CACHE.exists() else {}


# SHORT EXPLANATION: plain-prose call for the Brief (F5). gpt-oss via Groq fails
# intermittently on forced tool-calling with a 1-field schema ("tool_use_failed"), and a
# prose paragraph needs no structure anyway -- so the generator asks for text directly.
# Same cache contract as structured(): cache-first, committed cache = canonical (D9).
def text(system: str, user: str, *, model: str | None = None) -> str:
    """Return the model's plain-text answer for one grounded call. Cache-first."""
    model = model or config.LLM_MODEL
    key = _key(model, system, user)
    cache = _load()

    if _use_cache():
        if key in cache:
            return cache[key]
        raise RuntimeError(
            f"No cached LLM response for key {key} (model={model}). Export "
            f"{config.LLM_API_KEY_ENV} and set ESA_LLM_USE_CACHE=false to generate it "
            f"(it is then cached as the canonical reference)."
        )

    from langchain_groq import ChatGroq  # imported only on the API path

    # max_tokens explicit: reasoning models can burn the completion budget on internal
    # reasoning and return EMPTY content -- the budget must reach the text.
    llm = ChatGroq(model=model, temperature=0, max_tokens=2048,
                   api_key=config.require_llm_api_key())
    answer = str(llm.invoke([("system", system), ("human", user)]).content)
    if not answer.strip():
        # an empty answer must NEVER be cached as canonical -- fail loud instead
        raise RuntimeError(f"model {model} returned empty content")
    cache[key] = answer
    LLM_CACHE.write_text(json.dumps(cache, indent=2))
    return answer


def structured(system: str, user: str, schema: type[T], *, model: str | None = None) -> T:
    """Return a validated ``schema`` instance for one grounded call. Cache-first."""
    model = model or config.LLM_MODEL
    key = _key(model, system, user)
    cache = _load()

    if _use_cache():
        if key in cache:
            return schema(**cache[key])
        raise RuntimeError(
            f"No cached LLM response for key {key} (model={model}). Export "
            f"{config.LLM_API_KEY_ENV} and set ESA_LLM_USE_CACHE=false to generate it "
            f"(it is then cached as the canonical reference)."
        )

    from langchain_groq import ChatGroq  # imported only on the API path

    llm = ChatGroq(model=model, temperature=0, api_key=config.require_llm_api_key())
    result: T = llm.with_structured_output(schema).invoke(
        [("system", system), ("human", user)]
    )
    cache[key] = result.model_dump()
    LLM_CACHE.write_text(json.dumps(cache, indent=2))
    return result
