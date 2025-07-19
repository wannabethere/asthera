import tiktoken
import re 
from langchain.docstore.document import Document
import PyPDF2
import pandas as pd
import textwrap




def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """
    Calculates the number of tokens in a given string using a specified encoding.

    Args:
        string: The input string to tokenize.
        encoding_name: The name of the encoding to use (e.g., 'cl100k_base').

    Returns:
        The number of tokens in the string according to the specified encoding.
    """

    encoding = tiktoken.encoding_for_model(encoding_name)  # Get the encoding object
    num_tokens = len(encoding.encode(string))  # Encode the string and count tokens
    return num_tokens


def replace_t_with_space(list_of_documents):
    """
    Replaces all tab characters ('\t') with spaces in the page content of each document.

    Args:
        list_of_documents: A list of document objects, each with a 'page_content' attribute.

    Returns:
        The modified list of documents with tab characters replaced by spaces.
    """

    for doc in list_of_documents:
        doc.page_content = doc.page_content.replace('\t', ' ')  # Replace tabs with spaces
    return list_of_documents

def replace_double_lines_with_one_line(text):
    """
    Replaces consecutive double newline characters ('\n\n') with a single newline character ('\n').

    Args:
        text: The input text string.

    Returns:
        The text string with double newlines replaced by single newlines.
    """

    cleaned_text = re.sub(r'\n\n', '\n', text)  # Replace double newlines with single newlines
    return cleaned_text


def split_into_sections(document_path):
    """
    Splits a PDF document into sections based on section title patterns.

    Args:
        document_path (str): The path to the PDF document file.

    Returns:
        list: A list of Document objects, each representing a section with its text content and section number metadata.
    """

    with open(document_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        documents = pdf_reader.pages  # Get all pages from the PDF

        # Concatenate text from all pages
        text = " ".join([doc.extract_text() for doc in documents])

        # Split text into sections based on section title pattern (adjust as needed)
        sections = re.split(r'(SECTION\s[0-9]+(?:\.[0-9]+)*)', text)

        # Create Document objects with section metadata
        section_docs = []
        section_num = 1
        for i in range(1, len(sections), 2):
            section_text = sections[i] + sections[i + 1]  # Combine section title and content
            doc = Document(page_content=section_text, metadata={"section": section_num})
            section_docs.append(doc)
            section_num += 1

    return section_docs


def extract_key_facts_as_documents(documents, min_length=50):
    key_facts_as_documents = []
    # Correct pattern for key facts longer than min_length characters, including line breaks
    key_fact_pattern_longer_than_min_length = re.compile(rf'"(.{{{min_length},}}?)"', re.DOTALL)

    for doc in documents:
        content = doc.page_content
        content = content.replace('\n', ' ')
        found_key_facts = key_fact_pattern_longer_than_min_length.findall(content)
        for key_fact in found_key_facts:
            key_fact_doc = Document(page_content=key_fact)
            key_facts_as_documents.append(key_fact_doc)
    
    return key_facts_as_documents



def escape_quotes(text):
  """Escapes both single and double quotes in a string.

  Args:
    text: The string to escape.

  Returns:
    The string with single and double quotes escaped.
  """
  return text.replace('"', '\\"').replace("'", "\\'")



def text_wrap(text, width=120):
    """
    Wraps the input text to the specified width.

    Args:
        text (str): The input text to wrap.
        width (int): The width at which to wrap the text.

    Returns:
        str: The wrapped text.
    """
    return textwrap.fill(text, width=width)
    

def analyse_metric_results(results_df):
    """
    Analyzes and prints the results of various metrics.

    Args:
        results_df: A pandas DataFrame containing the metric results.
    """

    for metric_name, metric_value in results_df.items():
        print(f"\n**{metric_name.upper()}**")

        # Extract the numerical value from the Series object
        if isinstance(metric_value, pd.Series):
            metric_value = metric_value.values[0]  # Assuming the value is at index 0

        # Print explanation and score for each metric
        if metric_name == "faithfulness":
            print("Measures how well the generated answer is supported by the retrieved documents.")
            print(f"Score: {metric_value:.4f}")
            # Interpretation: Higher score indicates better faithfulness.
        elif metric_name == "answer_relevancy":
            print("Measures how relevant the generated answer is to the question.")
            print(f"Score: {metric_value:.4f}")
            # Interpretation: Higher score indicates better relevance.
        elif metric_name == "context_precision":
            print("Measures the proportion of retrieved documents that are actually relevant.")
            print(f"Score: {metric_value:.4f}")
            # Interpretation: Higher score indicates better precision (avoiding irrelevant documents).
        elif metric_name == "context_relevancy":
            print("Measures how relevant the retrieved documents are to the question.")
            print(f"Score: {metric_value:.4f}")
            # Interpretation: Higher score indicates better relevance of retrieved documents.
        elif metric_name == "context_recall":
            print("Measures the proportion of relevant documents that are successfully retrieved.")
            print(f"Score: {metric_value:.4f}")
            # Interpretation: Higher score indicates better recall (finding all relevant documents).
        elif metric_name == "context_entity_recall":
            print("Measures the proportion of relevant entities mentioned in the question that are also found in the retrieved documents.")
            print(f"Score: {metric_value:.4f}")
            # Interpretation: Higher score indicates better recall of relevant entities.
        elif metric_name == "answer_similarity":
            print("Measures the semantic similarity between the generated answer and the ground truth answer.")
            print(f"Score: {metric_value:.4f}")
            # Interpretation: Higher score indicates closer semantic meaning between the answers.
        elif metric_name == "answer_correctness":
            print("Measures whether the generated answer is factually correct.")
            print(f"Score: {metric_value:.4f}")
            # Interpretation: Higher score indicates better correctness.