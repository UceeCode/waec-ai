import os
import faiss
from pymongo import MongoClient
import numpy as np
import logging
import json
from bson import ObjectId
from typing import List, Dict, Optional
from dotenv import load_dotenv 
from langchain_huggingface.embeddings import HuggingFaceEmbeddings 

load_dotenv()

logger = logging.getLogger(__name__)

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "artefacts/faiss_index.bin")
FAISS_ID_MAP_PATH = "artefacts/faiss_id_map.json" 

os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
os.makedirs(os.path.dirname(FAISS_ID_MAP_PATH), exist_ok=True)


class VectorDBManager:
    
    def __init__(self):
        
        mongo_uri = os.getenv("MONGO_URI")
        mongo_db_name = os.getenv("MONGO_DB_NAME")
        
        self.client = MongoClient(mongo_uri)
        self.db = self.client[mongo_db_name]
        self.questions_collection = self.db['processed_questions'] 
        
        self.embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.faiss_index = None
        self.doc_id_map = []
        
        self._load_or_create_index()
        
    def _load_or_create_index(self):
        
        if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(FAISS_ID_MAP_PATH):
            try:
                self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
                with open(FAISS_ID_MAP_PATH, 'r') as f:
                    self.doc_id_map = json.load(f)
                logger.info(f"Loaded {len(self.doc_id_map)} document IDs and FAISS index.")     
            except Exception as e:
                self._create_index_from_mongodb()
        else:
            self._create_index_from_mongodb()
            
    def _create_index_from_mongodb(self):
        
        self.doc_id_map = []
        
        all_documents = list(self.questions_collection.find({})) 
        
        if not all_documents:
            logger.warning("No documents found in MongoDB to create FAISS index.")
            self.faiss_index = None
            return
            
        texts_to_embed = []
        
        for doc in all_documents:
            text = doc.get('question_text', '')
            if doc.get('options'):
                options_str = "\n".join([f"{opt['letter']}) {opt['text']}" for opt in doc['options']])
                text = f"{text}\n{options_str}"
                
            texts_to_embed.append(text)
            self.doc_id_map.append(str(doc['_id']))

        logger.info(f"Generating embeddings for {len(texts_to_embed)} documents...")
        embeddings = self.embedding_model.embed_documents(texts_to_embed)
        embeddings = np.array(embeddings).astype('float32')
        logger.info(f"Embeddings generated with shape: {embeddings.shape}")
        
        dimensions = embeddings.shape[1]
        self.faiss_index = faiss.IndexFlatL2(dimensions)
        self.faiss_index.add(embeddings)
        
        faiss.write_index(self.faiss_index, FAISS_INDEX_PATH)
        logger.info(f"FAISS index created and saved to {FAISS_INDEX_PATH}")
        
        with open(FAISS_ID_MAP_PATH, 'w') as f:
            json.dump(self.doc_id_map, f)
        logger.info(f"Document ID map created and saved to {FAISS_ID_MAP_PATH}")
        
    def retrieve_documents(self, query: Optional[str] = None, k: int = 5, subject: Optional[str] = None, year: Optional[int] = None) -> List[Dict]:
        
        mongo_filter = {}
        if subject:
            mongo_filter["subject"] = subject.lower()
        if year:
            mongo_filter["year"] = year
            
        if not query and mongo_filter:
            return list(self.questions_collection.find(mongo_filter))
        
        query_embedding = self.embedding_model.embed_query(query)
        query_embedding_np = np.array([query_embedding]).astype('float32')
        
        if not mongo_filter:
            logger.info(f"Retrieving TOP {k} documents globally for query: '{query}'")
            distances, faiss_indices = self.faiss_index.search(query_embedding_np, k)
        
            retrieved_mongo_ids = []
            for i in faiss_indices[0]:
                if i < len(self.doc_id_map):
                    retrieved_mongo_ids.append(self.doc_id_map[i])
            
            docs = list(self.questions_collection.find({"_id": {"$in": [ObjectId(mid) for mid in retrieved_mongo_ids]}}))
            logger.info(f"Retrieved {len(docs)} documents.")
            return docs
        else:
            logger.info(f"Retrieving documents matching filters: {mongo_filter} then finding TOP {k} relevant to query: '{query}'")
            
            filtered_by_metadata_docs = list(self.questions_collection.find(mongo_filter))
            
            if not filtered_by_metadata_docs:
                logger.info(f"No documents found matching the subject/year filters: {mongo_filter}.")
                return []

            logger.info(f"Found {len(filtered_by_metadata_docs)} documents matching metadata filters. Performing secondary relevance search...")
            
            subset_texts_to_embed = []
            subset_doc_ids = []
            
            for doc in filtered_by_metadata_docs:
                text = doc.get('question_text', '')
                if doc.get('options'):
                    options_str = "\n".join([f"{opt['letter']}) {opt['text']}" for opt in doc['options']])
                    text = f"{text}\n{options_str}"
                subset_texts_to_embed.append(text)
                subset_doc_ids.append(str(doc['_id']))
                
            if not subset_texts_to_embed: 
                logger.warning("No text found in filtered documents to create subset embeddings.")
                return []
            
            subset_embeddings = self.embedding_model.embed_documents(subset_texts_to_embed)
            subset_embeddings_np = np.array(subset_embeddings).astype('float32')
            
            subset_dimension = subset_embeddings_np.shape[1]
            subset_faiss_index = faiss.IndexFlatL2(subset_dimension)
            subset_faiss_index.add(subset_embeddings_np)
            
            distances, subset_faiss_indices = subset_faiss_index.search(query_embedding_np, min(k, len(subset_embeddings_np)))
            
            final_retrieved_mongo_ids = []
            for idx in subset_faiss_indices[0]:
                final_retrieved_mongo_ids.append(subset_doc_ids[idx])
                
            final_docs = list(self.questions_collection.find({"_id": {"$in": [ObjectId(mid) for mid in final_retrieved_mongo_ids]}}))

            logger.info(f"Retrieved {len(final_docs)} relevant documents from the filtered set.")
            return final_docs

    def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")