import os

os.environ['OPENAI_API_KEY'] = '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'

from dotenv import load_dotenv
from llama_index import GPTSimpleVectorIndex, QuestionAnswerPrompt, download_loader
from llama_index.node_parser import SimpleNodeParser
load_dotenv()

SimpleWebPageReader = download_loader("SimpleWebPageReader")
loader = SimpleWebPageReader()
documents = loader.load_data(urls=['https://testdriven.io/blog/django-custom-user-model/ '])

parser = SimpleNodeParser()

nodes = parser.get_nodes_from_documents(documents)
index = GPTSimpleVectorIndex(nodes)

QA_PROMPT_TMPL = (
    "Hello, I have some context information for you:\n"
    "---------------------\n"
    "{context_str}"
    "\n---------------------\n"
    "Based on this context, could you please help me understand the answer to this question: {query_str}?\n"
)
QA_PROMPT = QuestionAnswerPrompt(QA_PROMPT_TMPL)

query_str = "What are the advantages of using a custom User model in Django?"

response = index.query(query_str, text_qa_template=QA_PROMPT)
print(response)
