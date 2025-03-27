import os
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    # Create uploads directory if it doesn't exist
    os.makedirs('uploads', exist_ok=True)
    
    # Create static directories if they don't exist
    os.makedirs('app/static/css', exist_ok=True)
    os.makedirs('app/static/js', exist_ok=True)
    os.makedirs('app/static/images', exist_ok=True)
    
    # Run the FastAPI application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )