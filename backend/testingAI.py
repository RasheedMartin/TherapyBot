from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.readers.web import SimpleWebPageReader
from llama_index.llms.openai import OpenAI
from llama_index.core.prompts import PromptTemplate

load_dotenv()

def therapy(question, therapy_type):
    # Load data from a web page
    loader = SimpleWebPageReader()
    documents = loader.load_data(
        urls=[
            "https://childmind.org/article/helping-resistant-teens-into-treatment/"
            # You can add more URLs here for other therapy types
        ]
    )

    # Create a simple OpenAI-based LLM
    Settings.llm = OpenAI(model="gpt-4-turbo")  # or gpt-3.5-turbo


    # Build the vector index
    index = VectorStoreIndex.from_documents(documents)

    # Custom QA prompt template
    QA_PROMPT_TMPL = (
        f"You are a helpful assistant specialized in {therapy_type}.\n"
        "Below is some context information:\n"
        "---------------------\n"
        "{context_str}\n"
        "---------------------\n"
        "Based on this, please answer the question clearly:\n"
        "{query_str}\n"
    )
    QA_PROMPT = PromptTemplate(QA_PROMPT_TMPL)

    # Query the index
    query_engine = index.as_query_engine(text_qa_template=QA_PROMPT)
    response = query_engine.query(question)

    return str(response)
