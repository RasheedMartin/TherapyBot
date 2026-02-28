# TherapyBot 🧠💬

A full-stack AI-powered mental health support application that provides evidence-based therapeutic guidance through natural language conversations. Built with React, Django, and LlamaIndex for intelligent document retrieval.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/Django-5.2+-green.svg)
![React](https://img.shields.io/badge/React-18+-61DAFB.svg)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.14+-purple.svg)

## 🌟 Features

- **AI-Powered Therapy Conversations**: Leverages Groq (Llama 3.3 70B) and LlamaIndex for context-aware, evidence-based responses
- **Multiple Therapy Modalities**: Supports various therapy types including CBT, DBT, Family Therapy, and Teen Counseling
- **Crisis Detection**: Automatically detects crisis messages and directs users to appropriate resources
- **Knowledge Base Integration**: Built on curated mental health resources from trusted sources
- **Modern React Frontend**: Clean, responsive Material-UI interface
- **Django REST API**: Robust backend with RESTful endpoints and JWT authentication
- **Vector Search**: Semantic search through therapy documents using remote HuggingFace embeddings

## 🏗️ Architecture

```
TherapyBot/
├── backend/
│   ├── djangoProject/        # Django project config
│   │   ├── settings.py       # Django configuration
│   │   ├── urls.py           # URL routing
│   │   └── wsgi.py           # WSGI entrypoint
│   ├── therapybot/           # Django app
│   │   ├── views.py          # API endpoints
│   │   └── urls.py           # App URL routing
│   ├── testingAI.py          # LlamaIndex + Groq integration
│   ├── storage/              # Vector index storage
│   └── manage.py
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── api/              # API client
│   │   └── App.tsx           # Main app
│   └── package.json
├── requirements.txt
└── Dockerfile
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js & npm (for React frontend)
- [Groq API Key](https://console.groq.com) (free)
- [HuggingFace API Key](https://huggingface.co/settings/tokens) (free, Read access only)

### Backend Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/RasheedMartin/TherapyBot.git
   cd TherapyBot
   ```

2. **Create and activate virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables** — create a `.env` file in the backend directory:

   ```
   GROQ_API_KEY=your-groq-api-key
   HF_API_KEY=your-huggingface-api-key
   SECRET_KEY=your-django-secret-key
   DEBUG=True
   ```

5. **Run migrations**

   ```bash
   cd backend
   python manage.py migrate
   ```

6. **Build the knowledge base (first time only)**

   ```bash
   python testingAI.py
   # Type 'rebuild' to create the vector index
   ```

7. **Run the Django server**

   ```bash
   python manage.py runserver
   ```

### Frontend Setup

1. **Navigate to frontend directory**

   ```bash
   cd frontend
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Start the development server**

   ```bash
   npm run dev
   ```

4. **Open your browser**
   ```
   http://localhost:5173
   ```

## ☁️ Deployment

### Backend — Railway

The backend is deployed on [Railway](https://railway.app) using Docker.

**Required environment variables in Railway:**

| Variable        | Description                                       |
| --------------- | ------------------------------------------------- |
| `SECRET_KEY`    | Django secret key                                 |
| `GROQ_API_KEY`  | Groq API key                                      |
| `HF_API_KEY`    | HuggingFace API key (Read access)                 |
| `ALLOWED_HOSTS` | Your Railway domain e.g. `yourapp.up.railway.app` |
| `FRONTEND_URL`  | Your Vercel frontend URL                          |
| `DATABASE_URL`  | Auto-injected by Railway Postgres plugin          |

Railway automatically runs migrations and starts gunicorn on deploy via the Dockerfile CMD.

### Frontend — Vercel

The frontend is deployed on [Vercel](https://vercel.com). Connect your GitHub repo and Vercel handles the rest. Set your backend Railway URL as an environment variable in Vercel for API calls.

## 💡 Usage

1. Select a therapy type from the dropdown (e.g., Family Therapy, CBT)
2. Enter your question or concern in the text area
3. Click "Submit" to get an AI-powered response
4. The system retrieves relevant information from the knowledge base and generates a contextual response

## 🔧 Configuration

### Adding More Knowledge Sources

Edit the URLs in `build_index_local()` in `testingAI.py`:

```python
documents = loader.load_data(
    urls=[
        "https://childmind.org/article/helping-resistant-teens-into-treatment/",
        "https://childmind.org/article/anxiety-disorders-in-children/",
        # Add your URLs here
    ]
)
```

## 🛠️ Tech Stack

**Frontend:**

- React 18
- Material-UI (MUI)
- TanStack Query (React Query)
- TypeScript
- Axios

**Backend:**

- Django 5.2
- Django REST Framework
- Django REST Framework SimpleJWT
- LlamaIndex 0.14
- Groq API (Llama 3.3 70B)
- HuggingFace Inference API (remote embeddings)

**Infrastructure:**

- Railway (backend + PostgreSQL)
- Vercel (frontend)
- Docker

## 📊 API Endpoints

### Get Therapy Response

```
GET /api/get_started/
Parameters:
  - question: string (required)
  - therapy_type: string (optional, default: "general therapy")

Response:
{
  "response": "AI-generated therapeutic guidance..."
}
```

## ⚠️ Disclaimer

**This application is for informational and educational purposes only. It is NOT a substitute for professional mental health care.** If you are experiencing a mental health crisis, please contact:

- **988 Suicide & Crisis Lifeline**: Call or text 988
- **Crisis Text Line**: Text HOME to 741741
- **Emergency Services**: 911

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Rasheed Martin**

- GitHub: [@RasheedMartin](https://github.com/RasheedMartin)

## 🙏 Acknowledgments

- Mental health resources from [Child Mind Institute](https://childmind.org)
- Built with [LlamaIndex](https://www.llamaindex.ai/)
- Powered by [Groq](https://groq.com/)

---

**Note**: Originally created during a 9-hour hackathon and evolved into a full-stack production application with AI capabilities.
