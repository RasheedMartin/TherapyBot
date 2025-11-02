# TherapyBot 🧠💬

A full-stack AI-powered mental health support application that provides evidence-based therapeutic guidance through natural language conversations. Built with React, Django, and LlamaIndex for intelligent document retrieval.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Django](https://img.shields.io/badge/Django-4.0+-green.svg)
![React](https://img.shields.io/badge/React-18+-61DAFB.svg)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-Latest-purple.svg)

## 🌟 Features

- **AI-Powered Therapy Conversations**: Leverages OpenAI and LlamaIndex for context-aware, evidence-based responses
- **Multiple Therapy Modalities**: Supports various therapy types including CBT, DBT, Family Therapy, and Teen Counseling
- **Real-time Processing**: Instant responses with query processing feedback
- **Knowledge Base Integration**: Built on curated mental health resources from trusted sources
- **Modern React Frontend**: Clean, responsive Material-UI interface
- **Django REST API**: Robust backend with RESTful endpoints
- **Vector Search**: Semantic search through therapy documents using embeddings

## 🏗️ Architecture

```
TherapyBot/
├── backend/
│   ├── therapybot/           # Django app
│   │   ├── views.py          # API endpoints
│   │   ├── urls.py           # URL routing
│   │   └── settings.py       # Django configuration
│   ├── testingAI.py          # LlamaIndex integration
│   └── storage/              # Vector index storage
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── api/              # API client
│   │   └── App.tsx           # Main app
│   └── package.json
└── requirements.txt
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- npm or yarn (for React frontend)
- OpenAI API Key

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
   pip install llama-index-llms-openai llama-index-embeddings-huggingface openai
   ```

4. **Set up environment variables**

   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

5. **Build the knowledge base (first time only)**

   ```python
   python testingAI.py
   # Type 'rebuild' to create the vector index
   ```

6. **Run the Django server**
   ```bash
   python manage.py runserver
   ```

### Frontend Setup

1. **Navigate to frontend directory**

   ```bash
   cd ../frontend
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Start the development server**

   ```bash
   npm start
   ```

4. **Open your browser**
   ```
   http://localhost:3000
   ```

## 💡 Usage

1. Select a therapy type from the dropdown (e.g., Family Therapy, CBT)
2. Enter your question or concern in the text area
3. Click "Submit" to get an AI-powered response
4. The system retrieves relevant information from the knowledge base and generates a contextual response

## 🔧 Configuration

### Changing the AI Model

Edit `backend/testingAI.py`:

```python
# Use GPT-4 for better quality
_llm_instance = OpenAI(
    model="gpt-4",  # Change from gpt-3.5-turbo
    temperature=0.7,
    max_tokens=500,
)
```

### Adding More Knowledge Sources

Edit the URLs in `build_index_local()`:

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

- Django 4+
- Django REST Framework
- LlamaIndex
- OpenAI API
- HuggingFace Embeddings
- Sentence Transformers

**AI/ML:**

- OpenAI GPT-3.5/GPT-4
- Vector embeddings (sentence-transformers/all-MiniLM-L6-v2)
- Semantic search with LlamaIndex

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

## 🎯 Features in Development

- [ ] Session history and context persistence
- [ ] User authentication and personalized sessions
- [ ] Streaming responses for real-time feedback
- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Crisis detection and resource recommendations

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## ⚠️ Disclaimer

**This application is for informational and educational purposes only. It is NOT a substitute for professional mental health care.** If you are experiencing a mental health crisis, please contact:

- **National Suicide Prevention Lifeline**: 988
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
- Powered by [OpenAI](https://openai.com/)

---

**Note**: Originally created during a 9-hour hackathon and evolved into a full-stack React application with advanced AI capabilities.
