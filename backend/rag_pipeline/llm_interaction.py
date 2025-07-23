import os
import logging
from langchain_community.llms import Ollama 
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage, AIMessage, AIMessageChunk
logger = logging.getLogger(__name__)

class LLMInteraction:
    def __init__(self):
        ollama_base_url = os.getenv("OLLAMA_BASE_URL")
        ollama_model = os.getenv("OLLAMA_MODEL")


        self.model = Ollama(
            base_url=ollama_base_url,
            model=ollama_model,
            temperature=0.7, 
            num_ctx=4096,
            keep_alive="10m"
        )

        self.prompt_template = PromptTemplate.from_template(
            """You are a helpful assistant for WAEC past questions.
            You have access to the following relevant WAEC past questions:

            {context}

            Based on the above WAEC questions and the conversation history, answer the user's question.
            If the provided questions do not contain enough information to answer, state that you don't have enough information.

            Human: {query}
            AI:"""
        )

    def generate_response_streaming(self, query: str, context: str, chat_history: list):

        context_str = context if context else "No specific relevant questions were found in the database"
        
        full_context_for_ollama = f"{context_str}\n\nChat History:\n"
        for msg in chat_history:
            if isinstance(msg, HumanMessage):
                full_context_for_ollama += f"Human: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                full_context_for_ollama += f"AI: {msg.content}\n"


        formatted_prompt = self.prompt_template.format(context=full_context_for_ollama, query=query)

        try:

            for chunk in self.model.stream(formatted_prompt):
                
                if isinstance(chunk, AIMessageChunk):
                    yield f"data: {chunk.content}\n\n"
                elif isinstance(chunk, str):
                    yield f"data: {chunk}\n\n"

        except Exception as e:
            logger.error(f"Error generating response from LLM: {e}")
            yield f"Error: Could not generate response from LLM. Details: {e}"