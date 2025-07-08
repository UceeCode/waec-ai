from fastapi import FastAPI
from mongo_setup import setup_waec_database, WAECDatabase 

app = FastAPI()

db_instance: WAECDatabase | None = None

@app.on_event("startup")
async def startup_event():
    global db_instance
    print("Running database setup on startup...")
    db_instance = setup_waec_database()
    if db_instance:
        print("Database setup completed successfully during startup.")
    else:
        print("Database setup FAILED during startup.")

@app.on_event("shutdown")
async def shutdown_event():
    global db_instance
    if db_instance:
        db_instance.close_connection()
        print("Database connection closed on shutdown.")

@app.get("/db-status")
def get_db_status():
    if db_instance:
        return db_instance.test_connection()
    return {"status": "Database not connected"}