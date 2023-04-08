import os

os.environ['OPENAI_API_KEY'] = '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'

from dotenv import load_dotenv
from llama_index import GPTSimpleVectorIndex, QuestionAnswerPrompt, download_loader
from llama_index.node_parser import SimpleNodeParser
load_dotenv()

SimpleWebPageReader = download_loader("SimpleWebPageReader")
loader = SimpleWebPageReader()
documents = loader.load_data(urls=['https://childmind.org/article/helping-resistant-teens-into-treatment/'])

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

query_str = "What is the best way to treat a teen with depression?"

response = index.query(query_str, text_qa_template=QA_PROMPT)
print(response)
