import google.generativeai as genai
import logging
from typing import List, Dict, Generator
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

class LLMInteraction:
    
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

        self.rag_prompt_template = PromptTemplate(
            input_variables=["chat_history", "context", "question"],
            template="""You are a helpful assistant for WAEC past questions.
            You have access to the following relevant WAEC past questions:

            {context}

            Based on the above WAEC questions and the conversation history, answer the user's question.
            If the provided questions do not contain enough information to answer, state that you don't have enough information.

            Chat History:
            {chat_history}
            Human: {question}
            AI:"""
                    )
        
        
    def generate_response_streaming(self, user_query: str, retrieved_docs: List[Dict]) -> Generator[str, None, None]:
        
        context_str = ""
        
        if retrieved_docs:
            context_str = "Relevant WAEC Questions:\n"
            for i, doc in enumerate(retrieved_docs):
                context_str += f"--- Question {i+1} (Subject: {doc.get('subject', 'N/A')}, Year: {doc.get('year', 'N/A')}, Source: {doc.get('document_source', 'N/A')}) ---\n"
                context_str += f"Question Number: {doc.get('question_number', 'N/A')}\n"
                context_str += f"Question Text: {doc.get('question_text', 'N/A')}\n"
                if doc.get('options'):
                    options_formatted = "\n".join([f"  {opt['letter']}) {opt['text']}" for opt in doc['options']])
                    context_str += f"Options:\n{options_formatted}\n"
                context_str += "\n"
        else:
            context_str = "No specific relevant questions were found in the database. I will try to answer based on general knowledge."
            
        chat_history = self.memory.load_memory_variables({})["chat_history"]
        
        history_for_model = []
        for message in chat_history:
            if message.type == "human":
                history_for_model.append({"role": "user", "parts": [message.content]})
            elif message.type == "ai":
                history_for_model.append({"role": "model", "parts": [message.content]})
                
        final_user_message = f"{self.rag_prompt_template.template.split('Chat History:')[0].format(context=context_str)}\nHuman: {user_query}"
        history_for_model.append({"role": "user", "parts": [final_user_message]})
        
        try:
            
            response_stream = self.model.generate_content(
                history_for_model,
                stream=True,
                safety_settings={
                    "HARASSMENT": "block_none",
                    "HATE_SPEECH": "block_none",
                    "DANGEROUS_CONTENT": "block_none",
                }
            )
            
            full_response_content = ""
            
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
                    full_response_content += chunk.text
                    
            self.memory.chat_memory.add_ai_message(full_response_content)
            
        except Exception as e:
            logger.error(f"Error generating response from LLM: {e}")
            yield f"An error occurred: {e}"
            
            
              