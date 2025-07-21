import os
from dotenv import load_dotenv
from .vector_db_manager import VectorDBManager
from .llm_interaction import LLMInteraction 
import logging
from typing import Generator, Optional

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
mongo_db_name = os.getenv("MONGO_DB_NAME")

vector_db_manager = VectorDBManager()
llm_interaction = LLMInteraction()

logger.info("WAEC RAG Pipeline Core Components Initialized and Ready.")

def get_rag_response_stream(query: str, subject: Optional[str] = None, year: Optional[int] = None) -> Generator[str, None, None]:
    logger.info(f"RAG process initiated for query: '{query}', subject: '{subject}', year: '{year}'")

    retrieved_docs = vector_db_manager.retrieve_documents(
        query=query,
        k=5,
        subject=subject,
        year=year
    )
    logger.info(f"Retrieved {len(retrieved_docs)} documents for the query with filters.")

    yield from llm_interaction.generate_response_streaming(query, retrieved_docs, [])