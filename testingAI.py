import os

os.environ['OPENAI_API_KEY'] = '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'

from dotenv import load_dotenv
from llama_index import GPTSimpleVectorIndex, QuestionAnswerPrompt, download_loader
from llama_index.node_parser import SimpleNodeParser

load_dotenv()


def therapy(question, therapy_type):
    SimpleWebPageReader = download_loader("SimpleWebPageReader")
    loader = SimpleWebPageReader()

    documents = loader.load_data(urls=['https://childmind.org/article/helping-resistant-teens-into-treatment/'])
    # documents = loader.load_data(urls=['https://www.verywellmind.com/couples-therapy-definition-types-techniques-and-efficacy-5191137'])
    # documents = loader.load_data(urls=['https://www.verywellmind.com/family-therapy-definition-types-techniques-and-efficacy-5190233'])
    # documents = loader.load_data(urls=['https://www.keckmedicine.org/treatments/general-therapy-rehabilitation/#:~:text=General%20therapy%2Frehabilitation%20is%20a%20combination%20of%20physical%2C%20occupational,physical%20capabilities%20after%20a%20serious%20injury%20or%20illness.'])

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

    query_str = question

    response = index.query(query_str, text_qa_template=QA_PROMPT)
    return response
