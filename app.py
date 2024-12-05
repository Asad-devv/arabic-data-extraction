import os
import time
import fitz  # PyMuPDF for PDF handling
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()
# Default API Key
DEFAULT_API_KEY = os.getenv("API_KEY")

# Function to convert PDF to images
def pdf_to_images(pdf_path, output_folder, page_limit=None):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    pdf_document = fitz.open(pdf_path)
    total_pages = len(pdf_document)
    pages_to_process = page_limit if page_limit else total_pages
    st.write(f"Number of pages in the PDF: {total_pages}. Processing {pages_to_process} pages.")

    for page_number in range(min(pages_to_process, total_pages)):
        page = pdf_document.load_page(page_number)
        pix = page.get_pixmap()
        image_path = os.path.join(output_folder, f"page_{page_number + 1}.jpg")
        pix.save(image_path)
    pdf_document.close()

# Function to process a single page
def process_page(image_path, prompt, model, doc, page_number):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"The file at {image_path} was not found.")

    # Simulate file upload (replace with actual logic for uploading)
    uploaded_file = genai.upload_file(image_path)
    if uploaded_file is None:
        raise ValueError(f"File upload failed for {image_path}")

    # Generate content
    result = model.generate_content([uploaded_file, prompt])
    if not result or not hasattr(result, "text"):
        raise ValueError(f"Content generation failed for {image_path}")

    # Clean the extracted text
    extracted_text = result.text
    unwanted_markers = ["```arabic", "```", "'''", "arabic", "#"]
    for marker in unwanted_markers:
        if marker in extracted_text:
            extracted_text = extracted_text.replace(marker, "")
    st.write(f"Extracted Text for Page {page_number}")
    # Add the text to the document
    if page_number>1:
        doc.add_page_break()
    
    for line in extracted_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("**/") and line.endswith("/**"):  # Bold and centered
            clean_text = line.strip("**/")
            paragraph = doc.add_paragraph(clean_text)
            run = paragraph.runs[0]
            run.bold = True
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run.font.size = Pt(16)
        elif line.startswith("/") and line.endswith("/"):  # Center-aligned
            clean_text = line.strip("/")
            paragraph = doc.add_paragraph(clean_text)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if paragraph.runs:
                paragraph.runs[0].font.size = Pt(14)
        elif line.startswith("**") and line.endswith("**"):  # Bold text
            clean_text = line.strip("**")
            paragraph = doc.add_paragraph(clean_text)
            run = paragraph.runs[0]
            run.bold = True
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run.font.size = Pt(14)
        else:  # Normal text
            paragraph = doc.add_paragraph(line)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if paragraph.runs:
                paragraph.runs[0].font.size = Pt(12)

prompt = """
You will be given pages of a PDF file containing text in Arabic. Your task is to extract the content from each page while ensuring the following:

1. **Exclude Text Below the Black Line**:
   - Carefully identify any black horizontal line present on the page.
   - If the line exists, exclude all text below it.
   - The black line will typically cover about half the width of the page and is visually distinct.
   - If no black line is present, extract all the text from the page.

2. **Exclude Headers and Footers**:
   - Do not include any text from the header or footer sections of the page.

3. **Formatting Requirements**:
   - Maintain the original Arabic text formatting as closely as possible.
   - Follow these formatting guidelines:
     - **Headings**: Represent headings in a larger, bold font.
     - **Centered Text**: Denote centered text using `/arabic text/`.
     - **Bold Text**: Represent bold text using `**arabic text**`.
     - **Bold and Centered Text**: Combine both formats as `**/arabic text/**`.
   - Ensure all extracted text is **right-aligned** to match proper Arabic formatting.

4. **Do Not Include**:- Any text that appears below the black line.

5. Ensure proper **right-to-left alignment** in the Word document.

**Important Notes**:
- Ensure identification of the black line and verify that only the text above the line is extracted and exclude text below the line.
"""

# Streamlit UI
st.title("Arabic PDF to Word Converter")
st.write("Upload a PDF, extract Arabic content, and download the result in a Word document.")

# Input fields
user_api_key = st.text_input("Enter your Gemini API Key (optional) should be a paid one else the Quota will end in the middle of the program execution:", type="password")
pdf_file = st.file_uploader("Upload a PDF file", type=["pdf"])
output_file_name = st.text_input("Enter output Word file name (without extension):", "result.docx")

# Buttons
if st.button("Process PDF"):
    if not pdf_file:
        st.error("Please upload a PDF file.")
    else:
        # Use default API key if none is provided
        api_key = user_api_key if user_api_key else DEFAULT_API_KEY
        st.write(f"Using API Key: {'Provided by user' if user_api_key else 'Default key'}")

        # Save uploaded PDF to a temporary file
        pdf_path = os.path.join("temp", "uploaded_pdf.pdf")
        os.makedirs("temp", exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(pdf_file.read())

        # Set page limit based on API key presence
        page_limit = None if user_api_key else 10

        # Convert PDF to images
        output_folder = "temp_images"
        pdf_to_images(pdf_path, output_folder, page_limit)

        # Create Word document
        doc = Document()
        genai.configure(api_key=api_key)  # Initialize model
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        # Process images and add to Word document
        image_files = sorted(
            os.listdir(output_folder),
            key=lambda x: int("".join(filter(str.isdigit, os.path.splitext(x)[0]))),
        )
        for i, image_file in enumerate(image_files, start=1):
            image_path = os.path.join(output_folder, image_file)
            try:
                process_page(image_path, prompt, model, doc, i)
            except Exception as e:
                st.error(f"Error processing page {i}: {e}")
            time.sleep(3 if user_api_key else 15)  # Adjust delay based on API key

        # Save the Word document
        output_path = os.path.join("temp", output_file_name)
        doc.save(output_path)

        # Provide download link
        with open(output_path, "rb") as f:
            st.download_button("Download Word Document", f, file_name=output_file_name)

        # Clean up temporary files
        for folder in ["temp", output_folder]:
            for file in os.listdir(folder):
                os.remove(os.path.join(folder, file))
            os.rmdir(folder)
