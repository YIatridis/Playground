from pydantic import BaseModel, Field, EmailStr, ValidationError
from typing import Optional, Dict, Any
import os
import json
import requests
from datetime import datetime
from pydantic_prompt import prompt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class UserProfile(BaseModel):
    """Base model for user profile data"""
    name: str = Field(..., description="User's full name", min_length=2)
    email: EmailStr = Field(..., description="Valid email address")
    age: Optional[int] = Field(None, description="Age of the user", gt=0, lt=150)
    created_at: datetime = Field(..., description="Timestamp when profile was created")

class UserAddress(UserProfile):
    """Extends UserProfile with additional address details"""
    street: str
    city: str
    country: str
    postal_code: str

# Example data from a dictionary
data_dict = {
    "name": "John Doe",
    "email": "john.doe@example.com",
    "age": 30,
    "created_at": datetime.now()
}

# Example data from a JSON file
try:
    with open('user_data.json') as f:
        data_json = json.load(f)
except FileNotFoundError:
    print("JSON file not found. Using dictionary data instead.")
    data_json = None

def create_user_model(data: Dict[str, Any]) -> UserProfile:
    """Create and validate a user profile model from provided data"""
    try:
        user = UserProfile(**data)
        return user
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise

# Create instances of models
user_from_dict = create_user_model(data_dict)

if data_json:
    # If JSON data is available, create a more detailed model
    address_data = data_json.get("address", {})
    user_address = UserAddress(
        street=address_data.get("street"),
        city=address_data.get("city"),
        country=address_data.get("country"),
        postal_code=address_data.get("postal_code")
    )

# Example of using Pydantic models with environment variables
class Settings(BaseModel):
    """Settings model for application configuration"""
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///default.db")
    debug_mode: bool = os.getenv("DEBUG_MODE", False)
    secret_key: str = Field(..., description="Secret key for API authentication")

settings = Settings()

# Example of using Pydantic models with external APIs
def fetch_data_from_api():
    """Fetch data from an external API and validate the response"""
    try:
        response = requests.get("https://api.example.com/data")
        response.raise_for_status()
        data = json.loads(response.text)
        # Validate the response against a Pydantic model
        validated_data = UserProfile(**data)
        return validated_data
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        raise

# Example of using Pydantic models for serialization
def serialize_model(user: UserProfile) -> Dict[str, Any]:
    """Serialize the user model to a dictionary format"""
    return user.dict()

def serialize_to_json(user: UserProfile) -> str:
    """Serialize the user model to a JSON string"""
    from pydantic.json import jsonable_encoder
    return json.dumps(jsonable_encoder(user))

# Example of using Pydantic models for input validation
def validate_user_input():
    """Get and validate user input through command line prompts"""
    try:
        data = prompt({
            "type": "input",
            "name": "name",
            "message": "Enter your name:"
        })
        user_model = UserProfile(name=data["body"])
        print(f"Validated user: {user_model}")
    except ValidationError as e:
        print(f"Input validation failed: {e}")

# Example of using Pydantic models for error handling
def handle_errors():
    """Demonstrate error handling with Pydantic models"""
    try:
        # Intentionally create an invalid model instance
        invalid_user = UserProfile(name="", email="invalid_email")
    except ValidationError as e:
        print(f"Validation errors: {e}")
    else:
        print("User created successfully")

# Example of using Pydantic models for input/output with prompt
def interact_with_user():
    """Interactively gather user information and validate it"""
    try:
        responses = prompt([
            {
                "type": "input",
                "name": "name",
                "message": "Enter your name:",
                "validate": lambda val: len(val) >= 2 or "Name must be at least 2 characters long"
            },
            {
                "type": "input",
                "name": "email",
                "message": "Enter your email:",
                "validate": lambda val: EmailStr.validate(val)
            }
        ])
        user = UserProfile(name=responses['body']['name'], email=responses['body']['email'])
        print(f"Created user profile for {user.name}")
    except ValidationError as e:
        print(f"Input validation failed during interaction: {e}")

# Example of unit testing with Pydantic models
def test_create_user_model():
    """Test creating a valid user model instance"""
    user = UserProfile(name="Jane Smith", email="jane.smith@example.com")
    assert user.name == "Jane Smith"
    assert user.email == "jane.smith@example.com"

def test_data_loading():
    """Test loading data from various sources"""
    # Test loading from dictionary
    user_dict = create_user_model(data_dict)
    assert user_dict.age == 30

if __name__ == "__main__":
    import pytest
    pytest.main()