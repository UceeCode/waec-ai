from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging


from .rag_core import get_rag_response_stream 

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WAEC RAG Pipeline API",
    description="API for WAEC past questions Retrieval-Augmented Generation.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str
    subject: Optional[str] = None
    year: Optional[int] = None


@app.post("/ask")
async def ask_question(request: QuestionRequest):
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    logger.info(f"Received API question: '{request.question}', Subject: '{request.subject}', Year: '{request.year}'")

    try:
        response_generator = get_rag_response_stream(
            query=request.question,
            subject=request.subject,
            year=request.year
        )
        return StreamingResponse(response_generator, media_type="text/event-stream")
    except EnvironmentError as e:
        logger.error(f"Error during RAG processing: {e}")
        raise HTTPException(status_code=500, detail=f"Server configuration error: {e}")
    except Exception as e:
        logger.error(f"Error processing RAG request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")