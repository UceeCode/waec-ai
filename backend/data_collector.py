import time
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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WAECDataCollector:
    
    """
    data collector for waec questions from web and pdfs
    """
    
    def __init__(self, db_instance, base_data_dir="data-preparation"):
        
        self.db = db_instance
        self.base_data_dir = Path(base_data_dir)
        
        self.directories = {
            'raw_web_data': self.base_data_dir / 'raw_web_data',
            'pdf_documents': self.base_data_dir / 'pdf_documents',
            'processed_data': self.base_data_dir / 'processed_data',
            'logs': self.base_data_dir / 'logs'
        }
        
        for dir_path in self.directories.values():
            dir_path.mkdir(parents=True, exists_ok=True)

        self.raw_collection = self.db.get_collection('raw_documents')
        self.scrapped_collection = self.db.get_collection('scrapped_data')
        self.metadata_collection = self.db.get_collection('metadata')
        
        self.waec_urls = [
            "https://www.waecnigeria.org/",
            "https://myschool.ng/",
            "https://www.pass.ng/"
        ]
        
        self.session = requests.Session() 
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        
    def extract_year_from_content(self, content: str, filename: str = "") -> Optional[int]:
        
        year_pattern = [
            r'\b(19|20)\d{2}\b',
            r'\b\d{2}\b(?=\s*(?:exam|question|paper|waec))', 
        ]
        
        for pattern in year_pattern:
            matches = re.findall(pattern, filename.lower())
            if matches:
                year = matches[0]
                if len(year) == 4:
                    return int(year)
                elif len(year) == 2: 
                    year_int = int(year)
                    if year_int < 50:
                        return 2000 + year_int 
                    else:
                        return 1900 + year_int 
        year_matches = re.findall(r'\b(19|20)\d{2}\b', content)
        if year_matches:
            years = [int(y) for y in year_matches if 1990 <= int(y) <= 2030]
            if years:
                return max(years)
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
                'main', 'article', '.content', '.main-content', '#content', '#main', '.post-content', '.entry-content'
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
            
            text_content = main_content.get_text(seperator='\n', strip=True)
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
                    "source": f"{pdf_path}#page={i+1}",
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
    
    def insert_document(self, document: Dict, collection_name: str = 'raw_documents') -> bool:
        """
        insert document into mongodb without duplicates
        """
        
        try:
            collection = self.db.get_collection(collection_name)
            if not collection: 
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
        
    
    def collect_web_data(self, urls) -> int:
        
        urls = self.waec_urls
        
        collected_web_data_count = 0
        
        for url in urls:
            try:
                document = self.fetch_web_content(url)
                
                if document:
                    if self.insert_document(document, 'raw_document'):
                        collected_web_data_count += 1
                    
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
    
    def collect_pdf_data(self, pdf_directory) -> int:
        
        pdf_directory = self.directories['pdf-documents']
        
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
    