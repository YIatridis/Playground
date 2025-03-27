from datetime import datetime
import uuid
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    validator,
    ValidationError,
    model_validator,
)
from typing import Optional, Dict, Any
from faker import Faker

faker = Faker()

class User(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    age: int = Field(..., ge=0)
    phone_number: Optional[str] = Field(
        None,
        regex=r'^\+?1?\d{9,15}$'  # E.164 format validation
    )
    registration_date: datetime = Field(default_factory=datetime.now)

    @model_validator(mode='before')
    def check_age_and_phone(cls, values):
        if values.get('phone_number') and values.get('age') < 18:
            raise ValueError('Age must be at least 18 to have a phone number')
        return values

    @property
    def user_type(self) -> str:
        return 'minor' if self.age < 18 else 'adult'

class UserProfile(BaseModel):
    user: User
    bio: Optional[str] = None
    location: Optional[str] = Field(None, max_length=50)

def create_user_data() -> Dict[str, Any]:
    """Create a dictionary with fake user data."""
    return {
        'name': faker.name(),
        'email': faker.email(),
        'age': faker.random_int(min=1, max=99),
        'phone_number': f"+{faker.country_code()}{faker.msisdn()[2:]}",  # Generate valid E.164 number
    }

def main():
    print("Creating a User instance with valid data:")
    try:
        user_data = create_user_data()
        user = User(**user_data)
        print(user.dict())
    except ValidationError as e:
        print(f"Error creating user: {e}")

    # Example of invalid data
    print("\nAttempting to create a User with invalid age:")
    try:
        invalid_user = User(
            name="Invalid User",
            email="invalid@example.com",
            age=-1,
            phone_number="+1234567890"
        )
    except ValidationError as e:
        print(f"Validation error: {e}")

    # Example of parsing from dict
    print("\nParsing a dictionary into User model:")
    user_dict = {
        'name': "John Doe",
        'email': "john.doe@example.com",
        'age': 30,
        'phone_number': "+1234567890"
    }
    try:
        parsed_user = User.parse_obj(user_dict)
        print(parsed_user)
    except ValidationError as e:
        print(f"Parse error: {e}")

    # Example of nested models
    print("\nCreating a UserProfile with nested User:")
    profile_data = {
        'user': user_dict,
        'bio': "Tech enthusiast",
        'location': "New York"
    }
    try:
        profile = UserProfile.parse_obj(profile_data)
        print(profile.user.dict())
        print(f"User type: {profile.user.user_type}")
    except ValidationError as e:
        print(f"Profile validation error: {e}")

    # Example of serialization
    print("\nSerializing to dict:")
    serialized_user = parsed_user.dict()
    print(serialized_user)

    print("\nSerializing to JSON:")
    import json
    user_json = parsed_user.json(indent=2)
    print(user_json)

    print("\nParsing from JSON:")
    try:
        parsed_from_json = User.parse_raw(user_json)
        print(parsed_from_json)
    except ValidationError as e:
        print(f"Parse error: {e}")

    # Example of data manipulation
    print("\nUpdating user age and registration date:")
    try:
        parsed_user.age += 1
        parsed_user.registration_date = datetime.now()
        print(parsed_user)
    except ValidationError as e:
        print(f"Update error: {e}")

    # Example of custom validation
    print("\nAttempting to create a User with phone number but age < 18:")
    try:
        minor_user = User(
            name="Minor User",
            email="minor@example.com",
            age=17,
            phone_number="+1234567890"
        )
    except ValidationError as e:
        print(f"Validation error: {e}")

if __name__ == "__main__":
    main()