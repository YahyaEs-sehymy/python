# Flask API Application

A Flask-based API application with natural language processing capabilities using spaCy.

## Features

- RESTful API endpoints
- Natural Language Processing with spaCy
- Fuzzy string matching
- Language detection
- Session management
- CORS support

## Prerequisites

- Python 3.9 or higher
- pip (Python package installer)

## Installation

### Local Setup

1. Clone the repository

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
flask run
```

The API will be available at `http://localhost:5000`

### Docker Setup

1. Build the Docker image:
```bash
docker build -t flask-api .
```

2. Run the container:
```bash
docker run -p 5555:5555 flask-api
```

The API will be available at `http://localhost:5555`

## Configuration

The application uses the following environment variables:
- `FLASK_APP`: Set to `app.py`
- `FLASK_ENV`: Set to `development` for development mode or `production` for production

## Data Storage

The application uses a JSON file (`db.json`) for data storage. Ensure this file exists and is properly configured before running the application.

## Development

### Project Structure
```
├── app.py           # Main application file
├── requirements.txt # Python dependencies
├── Dockerfile      # Docker configuration
├── db.json         # Data storage
└── .gitignore      # Git ignore rules
```

### Adding New Features

1. Modify `app.py` to add new routes or functionality
2. Update requirements.txt if new dependencies are added
3. Test thoroughly before deploying

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License.