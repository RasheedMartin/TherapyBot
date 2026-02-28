import os
from llama_index.core import VectorStoreIndex, Settings, StorageContext, load_index_from_storage
from llama_index.embeddings.huggingface_api import HuggingFaceInferenceAPIEmbedding  # pip: llama-index-embeddings-huggingface-api
from llama_index.llms.groq import Groq
from llama_index.readers.web import SimpleWebPageReader

from dotenv import load_dotenv

load_dotenv()

# Configuration
INDEX_DIR = "./storage"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Initialize REMOTE HuggingFace Inference API embedding model
# Requires HF_API_KEY env var — free tier available at huggingface.co/settings/tokens
remote_embed_model = HuggingFaceInferenceAPIEmbedding(
    model_name=EMBED_MODEL_NAME,
    token=os.getenv("HF_API_KEY"),
)

# Set global settings — no local model download, no PyTorch
Settings.embed_model = remote_embed_model
Settings.chunk_size = 512
Settings.chunk_overlap = 50

_llm_instance = None

CRISIS_KEYWORDS = [
    "kill myself", "suicide", "end my life", "want to die",
    "hurt myself", "self harm", "don't want to live", "not worth living"
]

CRISIS_RESPONSE = """I'm really concerned about what you've shared. If you're having thoughts of suicide or self-harm, please reach out for immediate support:

- **988 Suicide & Crisis Lifeline**: Call or text 988 (US)
- **Crisis Text Line**: Text HOME to 741741
- **Emergency Services**: Call 911

You don't have to face this alone. These services are free, confidential, and available 24/7. Please reach out to them — they are better equipped to help than I am."""

def is_crisis_message(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CRISIS_KEYWORDS)

def get_llm():
    global _llm_instance
    if _llm_instance is None:
        print("Initializing Groq...")
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        
        _llm_instance = Groq(
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=500,
            api_key=api_key
        )
        Settings.llm = _llm_instance
    return _llm_instance

def build_index_local():
    """
    Build and save the index from web articles (run once).
    """
    print("Building index from web sources...")
    
    loader = SimpleWebPageReader()
    documents = loader.load_data(
        urls=[
            "https://childmind.org/article/helping-resistant-teens-into-treatment/",
            "https://childmind.org/article/anxiety-disorders-in-children/",
            "https://childmind.org/article/what-is-cbt/",
        ]
    )
    
    print(f"Loaded {len(documents)} documents")
    
    index = VectorStoreIndex.from_documents(
        documents,
        show_progress=True
    )
    
    index.storage_context.persist(persist_dir=INDEX_DIR)
    print(f"Index saved to {INDEX_DIR}")
    
    return index

def load_index_local():
    """
    Load the precomputed local index from disk.
    """
    if os.path.exists(INDEX_DIR):
        print("Loading existing index...")
        storage_context = StorageContext.from_defaults(persist_dir=INDEX_DIR)
        index = load_index_from_storage(storage_context)
        return index
    else:
        print("No existing index found. Building new index...")
        return build_index_local()

def therapy_chat(question: str, therapy_type: str = "general therapy") -> str:
    """
    Answer a user question using the precomputed local therapy index.
    """
    if is_crisis_message(question):
        return CRISIS_RESPONSE

    get_llm()
    
    index = load_index_local()
    
    query_engine = index.as_query_engine(
        similarity_top_k=3,
        response_mode="compact"
    )
    
    formatted_question = (
        f"You are a compassionate assistant specialized in {therapy_type}. "
        f"If the user expresses any suicidal thoughts, self-harm, or is in crisis, "
        f"you MUST direct them to call or text 988 immediately and not engage further. "
        f"Provide evidence-based, supportive guidance for non-crisis questions. "
        f"You are not a replacement for professional help.\n\n"
        f"Question: {question}"
    )

    print("Generating response...")
    response = query_engine.query(formatted_question)
    
    return str(response)

def chat_interface():
    """
    Simple command-line chat interface for the therapy bot.
    """
    print("\n" + "="*60)
    print("Therapy Support Bot")
    print("="*60)
    print("Type 'quit' or 'exit' to end the conversation")
    print("Type 'rebuild' to rebuild the index from sources")
    print("="*60 + "\n")
    
    try:
        get_llm()
        print("✓ Connected to Groq successfully!\n")
    except Exception as e:
        print(f"✗ Could not connect to Groq: {e}")
        print("Please set GROQ_API_KEY environment variable\n")
        return
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() in ['quit', 'exit']:
            print("\nTake care! Remember to reach out to a professional if needed.")
            break
        
        if user_input.lower() == 'rebuild':
            build_index_local()
            print("Index rebuilt successfully!")
            continue
        
        if not user_input:
            continue
        
        try:
            response = therapy_chat(user_input, therapy_type="supportive counseling")
            print(f"\nBot: {response}")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Uncomment to rebuild index on first run:
    # build_index_local()
    chat_interface()