# InvoiceScan - OCR Invoice Processing Web Application

InvoiceScan is a web application that allows users to extract data from invoice PDFs using OCR and AI. The application supports subscription tiers, user authentication, and exporting data to various formats.

## Features

- PDF invoice scanning and data extraction using OpenAI's GPT-4o-mini model
- User registration and authentication with both email/password and Google OAuth
- Subscription tiers with different monthly scan limits
- Secure storage and management of scan results
- Export functionality to Excel, CSV, and JSON formats
- Dashboard to view and manage scans
- RESTful API for integration with other systems

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, Pydantic, Alembic
- **Frontend:** HTML, CSS, JavaScript (with support for modern frameworks)
- **Database:** SQLite (can be replaced with PostgreSQL for production)
- **Authentication:** JWT, OAuth2 (Google)
- **Payments:** Stripe
- **AI/ML:** OpenAI API
- **Logging:** Logfire

## Prerequisites

- Python 3.8+
- OpenAI API key
- (Optional) Google OAuth credentials
- (Optional) Stripe API keys

## Getting Started

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/invoice-scan.git
   cd invoice-scan
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file:
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file with your actual configuration values.

5. Initialize the database:
   ```
   alembic upgrade head
   ```

6. Run the development server:
   ```
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. Open your browser and navigate to http://localhost:8000

## Project Structure

```
invoice_conv/
├── alembic.ini               # Alembic configuration
├── app/                      # Application package
│   ├── core/                 # Core functionality
│   ├── db/                   # Database models and session
│   ├── models/               # SQLAlchemy models
│   ├── routers/              # API routes
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # Business logic
│   ├── static/               # Static files (CSS, JS, images)
│   ├── templates/            # Jinja2 templates
│   ├── utils/                # Utility functions
│   └── main.py               # Application entry point
├── migrations/               # Alembic migrations
├── uploads/                  # Directory for uploaded files
├── .env                      # Environment variables
├── .env.example              # Example environment variables
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

## API Documentation

The API documentation is available at http://localhost:8000/docs when the server is running. This includes all endpoints, request/response models, and authentication requirements.

## Subscription Tiers

- **Free:** 5 scans per month
- **Basic:** 50 scans per month
- **Pro:** 200 scans per month
- **Enterprise:** 1000 scans per month

## Development

To run the tests:
```
pytest
```

To generate a new migration after model changes:
```
alembic revision --autogenerate -m "describe your changes"
```

To apply migrations:
```
alembic upgrade head
```

## Deployment

For production deployment, consider:

1. Using a production WSGI server like Gunicorn
2. Implementing HTTPS using Nginx as a reverse proxy
3. Configuring a production database like PostgreSQL
4. Setting up proper monitoring and logging
5. Implementing rate limiting and additional security measures

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Pydantic](https://pydantic-docs.helpmanual.io/)
- [OpenAI](https://openai.com/)
- [Stripe](https://stripe.com/)