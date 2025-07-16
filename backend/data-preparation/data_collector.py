import time 
import os
import requests
from bs4 import BeautifulSoup
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import re
from langchain_community.document_loaders import PyPDFLoader
import hashlib

from waec_question_extractor import WAECQuestionExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WAECDataCollector:
    
    """
    data collector for waec questions from web and pdfs
    """
    
    def __init__(self, db_instance, base_data_dir="data-preparation"):
        
        self.db = db_instance
        self.base_data_dir = Path(base_data_dir)
        self.question_extractor = WAECQuestionExtractor()
        
        self.directories = {
            'raw_web_data': self.base_data_dir / 'raw_web_data',
            'pdf_documents': self.base_data_dir / 'pdf_documents',
            'processed_data': self.base_data_dir / 'processed_data',
            'logs': self.base_data_dir / 'logs'
        }
        
        for dir_path in self.directories.values():
            os.makedirs(dir_path, exist_ok=True) 
        
        self.questions_collection = self.db.get_collection('processed_questions')
        self.raw_collection = self.db.get_collection('raw_documents')
        self.scraped_collection = self.db.get_collection('scraped_data')
        self.metadata_collection = self.db.get_collection('metadata')
        
        self.waec_urls = [
            "https://myschool.ng/",
        ]
        
        self.session = requests.Session() 
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        
    def extract_year_from_content(self, content: str, filename: str = "") -> Optional[int]:

        filename_patterns = [
            r'(?:waec|wassce|ssce)[_ -]*(\d{4})',
            r'(\d{4})[_ -]*(?:waec|wassce|ssce)',
            r'\b(19|20)\d{2}\b'
        ]

        combined_name_lower = filename.lower()
        for pattern in filename_patterns:
            matches = re.findall(pattern, combined_name_lower)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        match = ''.join(match)
                    year = int(match)
                    if 1990 <= year <= 2030:
                        return year

        content_patterns = [
            r'(?:waec|wassce|ssce)\s*(\d{4})',
            r'(\d{4})\s*(?:waec|wassce|ssce)',
            r'\b(19|20)\d{2}\b' 
        ]
        content_lower = content.lower()
        years_found = []
        for pattern in content_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                year = int(match) if match.isdigit() else int(match)
                if 1990 <= year <= 2030:
                    years_found.append(year)
        
        if years_found:
            return max(years_found)

        return None
    
    def fetch_web_content(self, url: str) -> Optional[Dict]:
        
        try:
            logger.info(f"fetching web content from {url}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            title = soup.title.string if soup.title else url.split('/')[-1]
            title = title.strip()
            
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
                element.decompose() 
                
            main_content = None
            content_selectors = [
                'main', 'article', '.content', '.main-content', '#content', '#main', '.post-content', '.entry-content', '.entry-content', '.question-content'
            ]
            
            for selectors in content_selectors:
                main_content = soup.select_one(selectors)
                if main_content:
                    break
            
            if not main_content:
                main_content = soup.find('body')
                
            if not main_content:
                logger.warning(f"No content found for {url}")
                return None 
            
            text_content = main_content.get_text(separator='\n', strip=True)
            text_content = ' '.join(text_content.split())
            
            if len(text_content) < 100:
                logger.warning(f"Content too short for {url}")
                return None
            
            sanitized_title = re.sub(r'[^\w\s-]', '', title)[:50] 
            filename = f"{sanitized_title}_{int(time.time())}.html"
            filepath = self.directories['raw_web_data'] / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)
                
            year = self.extract_year_from_content(text_content, url)
            
            content_hash = hashlib.md5(text_content.encode()).hexdigest()
            
            return {
                "content": text_content,
                "source": url,
                "type": "web",
                "title": title,
                "year": year,
                "content_hash": content_hash,
                "collected_at": datetime.now().isoformat(),
                "raw_html_path": str(filepath),
                "content_length": len(text_content),
                "metadata": {
                    "domain": url.split('/')[2] if '/' in url else url,
                    "response_status": response.status_code,
                    "content_type": response.headers.get('content-type', '')
                }
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {e}") 
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            return None
        
    

    def process_pdf_document(self, pdf_path: Path, year: Optional[int]= None) -> List[Dict]:
        
        """
        process pdf documents and extract content
        """
        
        documents = []
        
        try:
            logger.info(f"Proccessing PDF: {pdf_path}")
            
            if not year:
                year = self.extract_year_from_content("", pdf_path.name)
            
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()
            
            for i, page in enumerate(pages):
                content = page.page_content.strip()
                
                if len(content) < 50:
                    continue
                
                content_hash = hashlib.md5(content.encode()).hexdigest()
                
                document = {
                    "content": content,
                    "source": f"{pdf_path.name}#page={i+1}",
                    "type": "pdf",
                    "year": year,
                    "content_hash": content_hash,
                    "collected_at": datetime.now().isoformat(),
                    "file_info": {
                        "filename": pdf_path.name,
                        "filepath": str(pdf_path),
                        "page_number": i + 1,
                        "total_pages": len(pages),
                        "file_size": pdf_path.stat().st_size
                    },
                    "metadata": page.metadata
                }
                
                documents.append(document)
            
            logger.info(f"Processed {len(documents)} pages from {pdf_path}")
            return documents
        
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            return []
    
    def extract_and_store_questions(self, document: Dict) -> int:

        try:
            content = document.get('content', '')
            source = document.get('source', '')
            year = document.get('year')

            questions = self.question_extractor.extract_questions(content, source)

            if not questions:
                logger.info(f"No questions found in {source}")
                return 0

            subject = self.question_extractor.extract_subject(content, source)
            if not subject:
                subject = 'unknown'

            stored_count = 0

            for question in questions:
                question_doc = {
                    **question,
                    'year': year,
                    'subject': subject,
                    'document_source': source,
                    'processed_at': datetime.now().isoformat()
                }

                try:
                    self.questions_collection.update_one(
                        {"question_id": question_doc['question_id']},
                        {"$set": question_doc},
                        upsert=True
                    )
                    stored_count += 1
                except Exception as e:
                    logger.error(f"Error storing question with ID {question_doc.get('question_id', 'N/A')}: {e}")
                    continue

            logger.info(f"Stored {stored_count} questions from {source}")
            return stored_count

        except Exception as e:
            logger.error(f"Error during question extraction and storage for {document.get('source', 'Unknown')}: {e}")
            return 0

                
    def insert_document(self, document: Dict, collection_name: str = 'raw_documents') -> bool:
        """
        insert document into mongodb without duplicates
        """
        
        try:
            collection = self.db.get_collection(collection_name)
            if collection is None: 
                logger.error(f"Collection {collection_name} not found")
                return False
            
            result = collection.update_one(
                {"content_hash": document.get("content_hash")},
                {"$set": document},
                upsert=True
            )
            
            if result.upserted_id:
                logger.info(f"Inserted new document: {document.get('source', 'Unknown')}") 
            elif result.modified_count > 0:
                logger.info(f"Updated document: {document.get('source', 'Unknown')}") 
            else:
                logger.info(f"Document already exists: {document.get('source', 'Unknown')}")

            return True
        
        except Exception as e:
            logger.error(f"Error inserting document: {e}")
            return False
        
    
    def collect_web_data(self) -> int:
        
        collected_web_data_count = 0
        
        for url in self.waec_urls:
            try:
                document = self.fetch_web_content(url)
                
                if document:
                    if self.insert_document(document, 'raw_documents'):
                        collected_web_data_count += 1
                        
                    self.extract_and_store_questions(document)
                    
                    scraped_doc = {
                        "url": url,
                        "content_hash": document["content_hash"],
                        "scraped_at": document["collected_at"],
                        "content_type": "waec_web_content",
                        "year": document.get("year"),
                        "status": "success"
                    }
                    
                    self.insert_document(scraped_doc, 'scraped_data')
                    
                    time.sleep(2)        
            except Exception as e:
                logger.error(f"Error collecting from {url}: {e}")
                continue 

        return collected_web_data_count
    
    def collect_pdf_data(self) -> int:
        
        pdf_directory = self.directories['pdf_documents']
        
        collected_count = 0
        
        pdf_files = list(pdf_directory.glob("**/*.pdf"))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {pdf_directory}")
            return 0
        
        for pdf_path in pdf_files: 
            try:
                year = None
                for part in pdf_path.parts:
                    if part.isdigit() and len(part) == 4:
                        year = int(part)
                        break
                
                if not year:
                    year = self.extract_year_from_content("", pdf_path.name)
                    
                    documents = self.process_pdf_document(pdf_path, year)
                    
                    for document in documents:
                        if self.insert_document(document, 'raw_documents'):
                            collected_count += 1
                            
                        self.extract_and_store_questions(document)
                        
            except Exception as e:
                logger.error(f"Error processing PDF {pdf_path}: {e}") 
                continue

        return collected_count
    
    def organize_by_year(self):
        
        try:
            documents = self.raw_collection.find({})
            
            year_count = {}
            
            for doc in documents:
                year = doc.get('year')
                if year:
                    year_dir = self.directories['processed_data'] / str(year)
                    year_dir.mkdir(exist_ok=True)
                    
                    filename = f"{doc.get('content_hash', 'unknown')}.json"
                    filepath = year_dir / filename
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(doc, f, indent=2, default=str)
                        
                    year_count[year] = year_count.get(year, 0) + 1 
                    
                else:
                    unknown_dir = self.directories['processed_data'] / "unknown_year"
                    unknown_dir.mkdir(exist_ok=True)

                    filename = f"{doc.get('content_hash', 'unknown')}.json"
                    filepath = unknown_dir / filename

                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(doc, f, indent=2, default=str)

                    year_count['unknown'] = year_count.get('unknown', 0) + 1
                    
        except Exception as e:
            logger.error(f"Error organizing documents by year: {e}")
    