import logging
from vector_db_manager import VectorDBManager
from llm_interaction import LLMInteraction
import re
from typing import Optional

logger = logging.getLogger(__name__)

def parse_query_filters(query: str) -> tuple[str, Optional[str], Optional[int]]:
    """
    Parses the user query for subject and year filters.
    Returns (cleaned_query, subject, year).
    """
    subject = None
    year = None

    subject_match = re.search(r'subject\s+([a-zA-Z_]+)', query, re.IGNORECASE)
    if subject_match:
        subject = subject_match.group(1).lower().replace('_', ' ') 
        query = re.sub(r'subject\s+[a-zA-Z_]+', '', query, re.IGNORECASE).strip()

    year_match = re.search(r'(?:year|in)\s+(\d{4})', query, re.IGNORECASE)
    if year_match:
        try:
            year = int(year_match.group(1))
        except ValueError:
            year = None
        query = re.sub(r'(?:year|in)\s+\d{4}', '', query, re.IGNORECASE).strip()
    query = re.sub(r'\s+', ' ', query).strip()
    
    return query, subject, year

def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting WAEC RAG Pipeline...")

    vector_manager = VectorDBManager()
    
    llm_interactor = LLMInteraction()

    print("\nWAEC RAG Pipeline Ready!")
    print("Type your questions. You can specify subject and year (e.g., 'Give me biology questions in year 2012 about cells').")
    print("Type 'exit' to quit.")

    while True:
        user_input = input("\nYour question: ")
        if user_input.lower() == 'exit':
            break

        # Parse query for filters
        cleaned_query, filter_subject, filter_year = parse_query_filters(user_input)
        
        # Filter documents based on subject and year before retrieval
        filtered_documents = []
        if filter_subject or filter_year:
            logger.info(f"Applying filters: Subject='{filter_subject}', Year='{filter_year}'")
            for doc in vector_manager.documents:
                match_subject = True
                if filter_subject and doc.get('subject'):
                    if filter_subject not in doc['subject'].lower():
                        match_subject = False
                
                match_year = True
                if filter_year and doc.get('year'):
                    if doc['year'] != filter_year:
                        match_year = False

                if match_subject and match_year:
                    filtered_documents.append(doc)
            
            if not filtered_documents:
                print("AI: I couldn't find any questions matching your specific subject and year filters. Please try a different query or broader filters.")
                continue
            
            original_documents = vector_manager.documents
            vector_manager.documents = filtered_documents
            logger.info(f"Reduced document set to {len(filtered_documents)} after filtering.")

        # Retrieve relevant documents (questions)
        retrieved_questions = vector_manager.retrieve_documents(cleaned_query, k=5)

        # Restore original documents after retrieval
        if filter_subject or filter_year:
            vector_manager.documents = original_documents


        # Generate streaming response from LLM
        print("AI: ", end='', flush=True)
        for chunk in llm_interactor.generate_response_streaming(cleaned_query, retrieved_questions):
            print(chunk, end='', flush=True)
        print() # Newline at the end of AI response

    vector_manager.close()
    logger.info("Pipeline finished.")

if __name__ == "__main__":
    main()