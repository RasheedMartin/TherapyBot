import os
from llama_index.core import VectorStoreIndex, Settings, StorageContext, load_index_from_storage
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.readers.web import SimpleWebPageReader

# Configuration
INDEX_DIR = "./storage"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Initialize local embedding model (free, no API needed)
local_embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)

# Set global settings
Settings.embed_model = local_embed_model
Settings.chunk_size = 512
Settings.chunk_overlap = 50

_llm_instance = None

def get_llm():
    """Initialize OpenAI LLM."""
    global _llm_instance
    if _llm_instance is None:
        print("Initializing OpenAI...")
        
        # Make sure OPENAI_API_KEY is set in environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        _llm_instance = OpenAI(
            model="gpt-3.5-turbo",  # or "gpt-4" for better quality
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
    
    # Load documents from web
    loader = SimpleWebPageReader()
    documents = loader.load_data(
        urls=[
            "https://childmind.org/article/helping-resistant-teens-into-treatment/",
            "https://childmind.org/article/anxiety-disorders-in-children/",
            "https://childmind.org/article/what-is-cbt/",
            # Add more therapy URLs as needed
        ]
    )
    
    print(f"Loaded {len(documents)} documents")
    
    # Create index with local embeddings (no LLM needed for indexing)
    index = VectorStoreIndex.from_documents(
        documents,
        show_progress=True
    )
    
    # Persist index to disk
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
    
    Args:
        question: User's question
        therapy_type: Type of therapy context (e.g., "CBT", "DBT", "teen counseling")
    
    Returns:
        Response string from the therapy bot
    """
    # Ensure LLM is loaded
    get_llm()
    
    # Load index
    index = load_index_local()
    
    # Create query engine
    query_engine = index.as_query_engine(
        similarity_top_k=3,
        response_mode="compact"
    )
    
    # Format the question with therapy context
    formatted_question = (
        f"You are a compassionate and knowledgeable assistant specialized in {therapy_type}. "
        f"Provide evidence-based, supportive guidance. Remember that you are not a replacement "
        f"for professional help, but can offer information and support.\n\n"
        f"Question: {question}"
    )
    
    # Query the index
    print("Generating response...")
    response = query_engine.query(formatted_question)
    
    return str(response)

def chat_interface():
    """
    Simple command-line chat interface for the therapy bot.
    """
    print("\n" + "="*60)
    print("Therapy Support Bot (OpenAI Edition)")
    print("="*60)
    print("Type 'quit' or 'exit' to end the conversation")
    print("Type 'rebuild' to rebuild the index from sources")
    print("="*60 + "\n")
    
    # Pre-load the LLM
    try:
        get_llm()
        print("✓ Connected to OpenAI successfully!\n")
    except Exception as e:
        print(f"✗ Could not connect to OpenAI: {e}")
        print("Please set OPENAI_API_KEY environment variable\n")
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
    # Uncomment to rebuild index on first run
    # build_index_local()
    
    # Start chat interface
    chat_interface()