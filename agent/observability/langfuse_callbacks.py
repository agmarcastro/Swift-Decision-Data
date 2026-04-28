from __future__ import annotations

import os
from functools import lru_cache

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

_otel_initialised = False


@lru_cache(maxsize=1)
def get_langfuse_client():
    return Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ.get("LANGFUSE_HOST", "http://langfuse:3000"),
    )


def get_langfuse_handler():
    get_langfuse_client()
    return CallbackHandler()


def init_crewai_otel() -> None:
    global _otel_initialised
    if _otel_initialised:
        return

    import openlit

    client = get_langfuse_client()
    openlit.init(
        tracer=client._otel_tracer,  # type: ignore[attr-defined]
        disable_batch=True,
    )
    _otel_initialised = True
