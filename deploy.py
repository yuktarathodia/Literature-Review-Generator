import streamlit as st
import fitz  # PyMuPDF
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import nltk

# Download NLTK tokenizer data
nltk.download('punkt')

# Load the summarization model and tokenizer
checkpoint = "sshleifer/distilbart-cnn-12-6"
tokenizer = AutoTokenizer.from_pretrained(checkpoint)
model = AutoModelForSeq2SeqLM.from_pretrained(checkpoint)


# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text


# Function to summarize text
def summarize_text(text):
    # Split text into sentences
    sentences = nltk.tokenize.sent_tokenize(text)

    # Chunk sentences to fit within the model's max length
    length = 0
    chunk = ""
    chunks = []
    count = -1
    for sentence in sentences:
        count += 1
        combined_length = len(tokenizer.tokenize(sentence)) + length

        if combined_length <= tokenizer.max_len_single_sentence:
            chunk += sentence + " "
            length = combined_length

            if count == len(sentences) - 1:
                chunks.append(chunk.strip())
        else:
            chunks.append(chunk.strip())
            length = 0
            chunk = ""
            chunk += sentence + " "
            length = len(tokenizer.tokenize(sentence))

    # Summarize each chunk
    summary = []
    inputs = [tokenizer(chunk, return_tensors="pt", truncation=True) for chunk in chunks]
    for input in inputs:
        output = model.generate(**input)
        summary_generated = tokenizer.decode(*output, skip_special_tokens=True)
        summary.append(summary_generated)

    return " ".join(summary)


# Streamlit app layout
def main():
    st.title("PDF Summarizer")

    # File uploader on the left sidebar
    st.sidebar.header("Upload PDF")
    uploaded_file = st.sidebar.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
        # Display the PDF file content
        with st.expander("Uploaded PDF Content", expanded=False):
            pdf_text = extract_text_from_pdf(uploaded_file)
            st.text_area("Extracted Text", pdf_text, height=300)

        # Generate and display the summary
        if st.button("Summarize"):
            with st.spinner("Generating summary..."):
                summary = summarize_text(pdf_text)
                st.subheader("Summary")
                st.write(summary)


if __name__ == "_main_":
    main()
