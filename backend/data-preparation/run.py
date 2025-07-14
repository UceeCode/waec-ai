import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from mongo_setup import WAECDatabase
from data_collector import WAECDataCollector
from waec_question_extractor import WAECQuestionExtractor

class WAECDataPipeline:
    
    def __init__(self):
        
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
        self.database_name = os.getenv("MONGO_DB_NAME", "waec_questions_db")
        
        self.db = None
        self.collector = None
        self.extractor = None
        
    def setup_database(self):
        """Setup database connection and collections"""
        
        self.db = WAECDatabase(self.mongo_uri, self.database_name)
        
        if not self.db.connect():
            print("Failed to connect to database")
            return False
        
        if not self.db.create_collections():
            print("Failed to create collections")
            return False
        
        print("Database setup complete")
        return True
        
    
    def setup_collector(self):
        
        self.collector = WAECDataCollector(
            db_instance=self.db,
            base_data_dir="data-preparation"
        )
        
        print("Data collector setup complete")
        return True
    
    def setup_extractor(self):
        
        self.extractor = WAECQuestionExtractor()
        
        print("Question extractor setup complete")
        return True
    
    
    def collect_web_data(self):
        
        collected_count = self.collector.collect_web_data()
        
        if collected_count > 0:
            print(f"web data collection complete: {collected_count} documents processed")
        else:
            print("No web data collected")
        
        return collected_count
    
    def collect_pdf_data(self):
        
        collected_count = self.collector.collect_pdf_data()
        
        if collected_count > 0:
            print(f"PDF data collection complete: {collected_count} documents processed")
        else:
            print("No PDF data collected")
        
        return collected_count
    
    def organize_data(self):
        
        try:
            self.collector.organize_by_year()
            print("Data organization complete")
            return True
        except Exception as e:
            print(f"Data organization failed: {e}")
            return False
        
    def run_pipeline(self):
        """Run the complete data collection pipeline"""
        print("🚀 Starting WAEC Data Collection Pipeline...")
        
        try:
            if not self.setup_database():
                return False
            
            if not self.setup_collector():
                return False
            
            if not self.setup_extractor():
                return False
            
            self.collect_web_data()
            
            self.collect_pdf_data()
            
            self.organize_data()
            
            print("\nPipeline completed successfully")
            return True
            
        except Exception as e:
            print(f"Pipeline failed: {e}")
            return False
        
        finally:
            if self.db:
                self.db.close_connection()

def main():
    pipeline = WAECDataPipeline()
    
    if pipeline.run_pipeline():
        print("WAEC Data Collection Pipeline completed successfully!")
    else:
        print("WAEC Data Collection Pipeline failed!")

if __name__ == "__main__":
    main()