import logging
from typing import List, Dict, Optional
import re
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WAECQuestionExtractor:
    
    def __init__(self):
        
        self.question_patterns = [
            re.compile(r'(?:^|\n)\s*(\d+)\.\s*(.+?)(?=\n\s*\d+\.|\n\s*SECTION\s+[IVXLCDM]+|\n\s*Questions\s+\d+-\d+|\n\s*Question\s+\d+|$)', re.DOTALL | re.IGNORECASE),
            re.compile(r'(?:^|\n)\s*(?:QUESTION|Q)\s*(\d+)\:?\s*(.+?)(?=\n\s*(?:QUESTION|Q)\s*\d+\:?|\n\s*SECTION\s+[IVXLCDM]+|\n\s*Questions\s+\d+-\d+|\n\s*Question\s+\d+|$)', re.DOTALL | re.IGNORECASE),
            re.compile(r'(?:^|\n)\s*(\d+)\)\s*(.+?)(?=\n\s*\d+\)|\n\s*SECTION\s+[IVXLCDM]+|\n\s*Questions\s+\d+-\d+|\n\s*Question\s+\d+|$)', re.DOTALL | re.IGNORECASE),
        ]

        self.option_patterns = [
            re.compile(r'^\s*([A-Ea-e])\.\s*(.+?)(?=\n\s*[A-Ea-e]\.|\n\s*\d+\.|\Z)', re.MULTILINE),
            re.compile(r'^\s*([A-Ea-e])\)\s*(.+?)(?=\n\s*[A-Ea-e]\)|\n\s*\d+\.|\Z)', re.MULTILINE),
        ]
        
        self.subject_patterns = {
            'mathematics': r'(?i)(?:math|mathematics|maths|further\s*maths)',
            'english': r'(?i)(?:english|literature\s*in\s*english|use\s*of\s*english)',
            'physics': r'(?i)physics',
            'chemistry': r'(?i)chemistry',
            'biology': r'(?i)biology',
            'economics': r'(?i)economics',
            'geography': r'(?i)geography',
            'history': r'(?i)history',
            'government': r'(?i)government',
            'commerce': r'(?i)commerce',
            'accounting': r'(?i)(?:accounting|accounts|book\s*keeping)',
            'agricultural_science': r'(?i)(?:agricultural\s*science|agric)',
            'technical_drawing': r'(?i)(?:technical\s*drawing|tech\s*drawing)',
            'food_and_nutrition': r'(?i)(?:food\s*and\s*nutrition|nutrition)',
            'christian_religious_knowledge': r'(?i)(?:christian\s*religious\s*knowledge|crk)',
            'islamic_religious_studies': r'(?i)(?:islamic\s*religious\s*studies|irs)',
            'civic_education': r'(?i)civic\s*education',
            'data_processing': r'(?i)data\s*processing',
            'computer_studies': r'(?i)computer\s*studies',
            'general_knowledge': r'(?i)(?:general\s*knowledge|gk|aptitude)', 
        }
    
    def clean_text(self, text: str) -> str:
        text = re.sub(r'(?i)(?:WAEC|WASSCE|SSCE)\s*PAST\s*QUESTIONS?|OBJECTIVE\s*TEST|ESSAY\s*TEST|SECTION [IVXLCDM]+.*?|Instructions:.*?\n|Time:.*?\n|Paper \d+.*?\n', '', text, flags=re.DOTALL)
        text = re.sub(r'\s{2,}', ' ', text).strip() 
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        return text
        
    def extract_subject(self, text: str, filename: str = "") -> Optional[str]:
        
        combined_text = f"{filename} {text}".lower()
        
        for subject, pattern in self.subject_patterns.items():
            if re.search(pattern, combined_text):
                return subject
        return None

    def extract_options(self, text_after_question: str) -> List[Dict]:
        
        options = []
        clean_text_after_question = text_after_question
        
        for pattern in self.option_patterns:
            matches = list(pattern.finditer(clean_text_after_question))
            
            if matches:
                for i, match in enumerate(matches):
                    letter = match.group(1).upper()
                    option_text = match.group(2).strip()
                    
                    if len(option_text) < 2:
                        continue
                    
                    options.append({
                        'letter': letter,
                        'text': option_text
                    })
            break
        
        return options
    
    def determine_question_type(self, question_text: str, options: List[Dict]) -> str:
        text_lower = question_text.lower()
        
        if options:
            return 'multiple_choice'
        elif any(word in text_lower for word in ['calculate', 'find', 'solve', 'compute', 'determine the value of']):
            return 'calculation'
        elif any(word in text_lower for word in ['explain', 'describe', 'discuss', 'define', 'state', 'list', 'outline', 'differentiate']):
            return 'essay'
        elif any(word in text_lower for word in ['true or false', 'correct or incorrect', 'identify the true statement']):
            return 'true_false'
        else:
            return 'short_answer'
    
    def extract_questions(self, text: str, source: str = "") -> List[Dict]:
        
        questions = []
        cleaned_text = self.clean_text(text)
        remaining_text = cleaned_text
        
        for pattern in self.question_patterns:
            
            matches = list(pattern.finditer(remaining_text))
            
            if not matches:
                continue
            
            extracted_indices = []
            
            for i, match in enumerate(matches):
                question_num_str = match.group(1).strip()
                question_content_raw = match.group(2).strip()
                start_idx = match.start()
                end_idx = match.end()
                
                try:
                    question_num = int(question_num_str)
                except ValueError:
                    continue 

                if len(question_content_raw) < 10:
                    continue
                
                question_stem = question_content_raw
                options = []
                
                option_start_match = re.search(r'^\s*([A-Ea-e][\.\)])', question_content_raw, re.MULTILINE)
                
                if option_start_match:
                    option_start_index = option_start_match.start()
                    question_stem = question_content_raw[:option_start_index].strip()
                    options_text = question_content_raw[option_start_index:].strip()
                    options = self.extract_options(options_text)
                    if not options and len(question_content_raw) > 200:
                        question_stem = question_content_raw   
                else:
                    options = self.extract_options(question_content_raw)
                    if options:
                        first_option_text = next((opt['text'] for opt in options), '')
                        if first_option_text:
                            first_option_match = re.search(re.escape(options[0]['letter']) + r'[\.\)]', question_content_raw)
                            if first_option_match:
                                question_stem = question_content_raw[:first_option_match.start()].strip()
                                
                question_type = self.determine_question_type(question_stem, options)
                question_id = hashlib.md5(f"{source}-{question_num}-{question_stem}".encode()).hexdigest()
                
                question_data = {
                    'question_number': question_num,
                    'question_text': question_stem,
                    'question_type': question_type,
                    'options': options,
                    'source': source,
                    'question_id': question_id,
                }
                questions.append(question_data)
                extracted_indices.append((start_idx, end_idx))
            
            if questions:
                logger.info(f"Extracted {len(questions)} questions using pattern: {pattern.pattern[:50]}...")
                break 
            
        if not questions and len(cleaned_text) > 100:
            logger.warning(f"No questions found using any pattern for source: {source}. Raw length: {len(cleaned_text)}")  

        return questions
                    
                    
            
        
    