import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WAECDatabase:
    
    def __init__(self, mongo_uri, db_name):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGO_DB_NAME", "waec_questions_db")
        
        self.collections = {
            'raw_documents': 'raw_documents',
            'processed_questions': 'processed_questions',
            'scraped_data': 'scraped_data',
            'metadata': 'metadata'
        }
        
        self.client = None
        self.db = None

    def connect(self):
        """
        Establish connection to MongoDB and returns True if successful or False if otherwise
        """
        try:
            self.client = MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000
            )
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            logger.info(f"Successfully connected to MongoDB: {self.db_name}")
            return True

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection failed: {e}")
            logger.error("Please ensure MongoDb is running")
            return False

        except Exception as e:
            logger.error(f"Unexpected error during MongoDB connection: {e}")
            return False

    def create_collections(self):
        """
        Creates collections with indexes for faster lookups and returns True if collections were created successfully
        """
        try:
            for collection_name, collection_key in self.collections.items():
                collection = self.db[collection_key]

                if collection_key == 'raw_documents':
                    collection.create_index("source", unique=True)
                    collection.create_index("type")
                    collection.create_index("collected_at")
                    collection.create_index("year")

                elif collection_key == 'processed_questions':
                    collection.create_index("question_id", unique=True)
                    collection.create_index("year")
                    collection.create_index("subject")
                    collection.create_index("question_type")

                elif collection_key == 'scraped_data':
                    collection.create_index("url", unique=True)
                    collection.create_index("scraped_at")
                    collection.create_index("content_type")

                elif collection_key == 'metadata':
                    collection.create_index("collection_name")
                    collection.create_index("created_at")

                logger.info(f"Collection '{collection_key}' created and added indexes")
            return True

        except Exception as e:
            logger.error(f"Error creating collections: {e}")
            return False

    def get_collection(self, collection_name):
        """
        Get a specific collection and returns MongoDB collection object or None
        """
        if not self.db:
            logger.error("Database not connected")
            return None

        if collection_name not in self.collections:
            logger.error(f"Collection '{collection_name}' not found in available collections")
            return None

        return self.db[self.collections[collection_name]]

    def test_connection(self):
        """
        Test database connection and display info and returns database information
        """
        try:
            stats = self.db.command("dbstats")
            collection_info = {}

            for name, collection_key in self.collections.items():
                collection = self.db[collection_key]
                collection_info[name] = {
                    'document_count': collection.count_documents({}),
                    'indexes': list(collection.list_indexes())
                }

            db_info = {
                'database_name': self.db_name,
                'connection_status': 'Connected',
                'database_size': stats.get('dataSize', 0),
                'collections': collection_info
            }

            logger.info("Database connection test successful")
            return db_info

        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return None

    def close_connection(self):
        """
        Close database connection
        """
        if self.client:
            self.client.close()
            logger.info("Database connection closed")


def setup_waec_database():
    """
    Setup WAEC database
    """
    db = WAECDatabase()

    if not db.connect():
        logger.error("Failed to connect to database")
        return None

    if not db.create_collections():
        logger.error("Failed to create collections")

    db_info = db.test_connection()

    if db_info:
        logger.info("Database setup completed successfully")
        print("DATABASE SETUP SUMMARY")
        print(f"Database Name: {db_info['database_name']}")
        print(f"Status: {db_info['connection_status']}")
        print(f"Database Size: {db_info['database_size']} bytes")
        print("\nCollections Created:")
        for name, info in db_info['collections'].items():
            print(f"  - {name}: {info['document_count']} documents")


    return db


if __name__ == "__main__":
    waec_db = setup_waec_database()

    if waec_db:
        print("\n✅ Database setup completed successfully!")
        print("You can now use this database for data collection.")
        waec_db.close_connection()
    else:
        print("\n❌ Database setup failed!")
