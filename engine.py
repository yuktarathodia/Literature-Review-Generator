import fitz  # PyMuPDF for PDF parsing
import re    # Regular expressions
from collections import defaultdict  # For grouping blocks by page
import pdfplumber
from groq import Groq
import json # Import the json library


# Replace with your API key or load from environment
client = Groq(api_key="gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")


# Load PDF
pdf_path = 'file.pdf'
doc = fitz.open(pdf_path)

extracted_blocks = []

for page_num in range(len(doc)):
    page = doc.load_page(page_num)
    text_blocks = page.get_text("blocks")

    for block in text_blocks:
        x0, y0, x1, y1, text, block_no, block_type = block
        bbox = (x0, y0, x1, y1)

        # Clean up text (remove extra spaces/newlines)
        clean_text = text.strip()

        # Store only non-empty text blocks
        if clean_text:
            extracted_blocks.append({
                'page': page_num + 1,
                'text': clean_text,
                'bbox': bbox
            })

doc.close()

# Debugging: print first few blocks
for i, block_data in enumerate(extracted_blocks[:10]):
    print(f"Page {block_data['page']}, Bbox: {block_data['bbox']}")
    print(f"Text:\n{block_data['text'][:200]}...\n")



identified_headings = []

# === BROADENED HEADING PATTERNS ===
heading_patterns = [
    re.compile(r'^ABSTRACT$', re.IGNORECASE),                          # Abstract
    re.compile(r'^[IVXLCDM]+\.\s+.*'),                                 # Roman numeral headings: I. Intro
    re.compile(r'^\d+\.\s+.*'),                                       # 1. Intro
    re.compile(r'^\d+\s+[A-Z].*'),                                   # 1 INTRODUCTION (no dot)
    re.compile(r'^\d+(\.\d+)+\s+.*'),                                # 3.1 Training-Data Poisoning / 3.1.1 Batch Learner
    re.compile(r'^[A-Z]\.\s+.*'),                                    # A. Title / B. Design Case
    re.compile(r'^[a-z]\)\s+.*'),                                    # a) Why RAG
    re.compile(r'^\d+\)\s+.*'),                                      # 1) Classification
    re.compile(r'^Theorem\s+\d+\.?', re.IGNORECASE),                  # Theorem 3.
    re.compile(r'^(Preface|Abstract|Introduction|Conclusion|References|Acknowledgements)\s*$', re.IGNORECASE),
    re.compile(r'^(Preface|Abstract|Introduction|Conclusion|References|Acknowledgements)\s*\.*\s+.*', re.IGNORECASE),
]

# === IDENTIFY HEADINGS ===
for block_data in extracted_blocks:
    text = block_data['text'].strip()
    page_num = block_data['page']
    bbox = block_data['bbox']

    lines_in_block = text.split('\n')
    for line in lines_in_block:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        is_heading = False
        for pattern in heading_patterns:
            if pattern.match(cleaned_line):
                identified_headings.append({'page': page_num, 'text': cleaned_line, 'bbox': bbox})
                is_heading = True
                break

        # OPTIONAL: could add heuristics for very short lines that look like headings
        # but leaving this disabled per your preference.

# === OUTPUT ===
print("Identified Headings:")
for heading in identified_headings:
    print(f"Page {heading['page']}, Bbox: {heading['bbox']}, Text: {heading['text']}")


# === REMOVE HEADINGS AFTER REFERENCES ===
filtered_headings = []
stop_after_references = False

for heading in identified_headings:
    if stop_after_references:
        break  # Stop collecting once References is reached
    filtered_headings.append(heading)
    if re.match(r'^REFERENCES$', heading['text'], re.IGNORECASE):
        stop_after_references = True

# === OUTPUT FILTERED HEADINGS ===
print("Headings up to References:")
for heading in filtered_headings:
    print(f"Page {heading['page']}, Bbox: {heading['bbox']}, Text: {heading['text']}")



sections = {}
current_section_title = "Metadata (Title/Authors)"  # Default section before first heading
sections[current_section_title] = []

# Sort filtered headings by page and vertical position
filtered_headings.sort(key=lambda x: (x['page'], x['bbox'][1]))

heading_index = 0
bbox_tolerance = 10  # Relaxed vertical tolerance

for block_data in extracted_blocks:
    block_page = block_data['page']
    block_bbox = block_data['bbox']
    block_text = block_data['text'].strip()

    # If there are headings left to match
    if heading_index < len(filtered_headings):
        current_heading = filtered_headings[heading_index]
        heading_page = current_heading['page']
        heading_bbox = current_heading['bbox']
        heading_text = current_heading['text'].strip()

        # Relaxed matching: same page + similar Y position + heading text appears in block text
        if (
            block_page == heading_page
            and abs(block_bbox[1] - heading_bbox[1]) < bbox_tolerance
            and heading_text.lower() in block_text.lower()
        ):
            # Start a new section
            current_section_title = heading_text
            sections[current_section_title] = []
            heading_index += 1
            continue  # Skip adding heading text itself to content

    # Otherwise, treat as part of current section
    sections[current_section_title].append(block_text)

# Combine text blocks per section
section_contents = {
    title: "\n".join(blocks) for title, blocks in sections.items()
}

# Print first few characters of each section for verification
for title, content in section_contents.items():
    print(f"--- Section: {title} ---")
    print(content[:500] + "...\n")



# === CLEAN AND NORMALIZE SECTION TEXTS ===
cleaned_section_contents = {}

# Pattern to detect lines that are just page numbers
page_number_pattern = re.compile(r'^\s*\d+\s*$')

# Minimum line length for regular sections
min_line_length = 30

for title, blocks in sections.items():  # Using sections built from filtered_headings
    cleaned_lines = []
    for line in blocks:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue
        # Skip lines that are just page numbers
        if page_number_pattern.match(cleaned_line):
            continue
        # Normalize whitespace
        cleaned_line = re.sub(r'\s+', ' ', cleaned_line)
        # Preserve short lines in Metadata / ABSTRACT
        if title in ["Metadata (Title/Authors)", "ABSTRACT"]:
            cleaned_lines.append(cleaned_line)
        else:
            # For other sections, apply minimum length heuristic
            if len(cleaned_line) >= min_line_length:
                cleaned_lines.append(cleaned_line)

    # Combine back into single string per section
    cleaned_section_contents[title] = '\n'.join(cleaned_lines)

# Replace original section_contents with cleaned version
section_contents = cleaned_section_contents

# Print first 500 characters of each cleaned section for verification
for title, content in section_contents.items():
    print(f"--- Cleaned Section: {title} ---")
    print(content[:500] + "...\n")




pdf_path = 'file.pdf'
extracted_tables_data = [] # Store extracted tables with page number

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages):
        print(f"--- Tables on Page {page_num + 1} ---")
        tables_on_page = page.extract_tables()
        if tables_on_page:
            extracted_tables_data.append({'page': page_num + 1, 'tables': tables_on_page})
            for table_num, table in enumerate(tables_on_page):
                print(f"Table {table_num + 1}:")
                for row in table:
                    print(row)
                print("-" * 20)
        else:
            print("No tables found on this page.")


# Assuming 'extracted_tables_data' contains the extracted tables from the previous step

def format_table_as_markdown(table):
    """
    Formats a list of lists representing a table into a Markdown table string.
    Handles potential None values in cells.
    """
    if not table:
        return ""

    markdown_output = ""
    # Add header row
    header = table[0]
    markdown_output += "| " + " | ".join([str(cell) if cell is not None else "" for cell in header]) + " |\n"
    # Add separator line, ensuring it aligns with header length
    separator = "|-" + "-|-".join(['-' * (len(str(cell)) if cell is not None else 0) for cell in header]) + "-|\n"
    # Adjust separator length if needed (basic approach)
    if len(separator) < len(markdown_output.split('\n')[0]):
        separator = "|---" * len(header) + "|\n"
    markdown_output += separator

    # Add data rows
    for row in table[1:]:
        markdown_output += "| " + " | ".join([str(cell) if cell is not None else "" for cell in row]) + " |\n"
    return markdown_output

formatted_tables = []
if 'extracted_tables_data' in locals() and extracted_tables_data:
    for page_data in extracted_tables_data:
        page_num = page_data['page']
        tables_on_page = page_data['tables']
        formatted_tables.append(f"\n--- Tables on Page {page_num} ---\n")
        for table_num, table in enumerate(tables_on_page):
            formatted_tables.append(f"\nTable {table_num + 1}:\n")
            formatted_tables.append(format_table_as_markdown(table))
            formatted_tables.append("-" * 20)
        formatted_tables.append("\n")

# Print the formatted tables to verify
for ft in formatted_tables:
    print(ft)



pdf_path = 'file.pdf'
doc = fitz.open(pdf_path)
extracted_captions = []

# Common patterns for figure captions
caption_patterns = [
    re.compile(r'^Figure\s+\d+[\.\s_]', re.IGNORECASE),
    re.compile(r'^Fig\.\s+\d+[\.\s_]', re.IGNORECASE),
    re.compile(r'^Figure\s+\w\.\s+', re.IGNORECASE), # For captions like Figure A.
    re.compile(r'^Fig\.\s+\w\.\s+', re.IGNORECASE), # For captions like Fig. A.
]

for page_num in range(len(doc)):
    page = doc.load_page(page_num)
    text_blocks = page.get_text("blocks") # Get text blocks with coordinates

    for block in text_blocks:
        text = block[4] # The text content of the block
        # Split the block text into lines to check each line
        lines_in_block = text.split('\n')

        for line in lines_in_block:
            cleaned_line = line.strip()
            if not cleaned_line:
                continue

            # Check if the line starts with a common caption pattern
            is_caption = False
            for pattern in caption_patterns:
                if pattern.match(cleaned_line):
                    extracted_captions.append({'page': page_num + 1, 'text': cleaned_line})
                    is_caption = True
                    break # Move to the next line if a caption is found

            # Optional: Add heuristics based on text position or size if needed
            # For example, captions are often below figures and might have a specific font size (more advanced)


doc.close()

# Print the extracted captions to verify
print("Extracted Figure Captions:")
for caption_data in extracted_captions:
    print(f"Page {caption_data['page']}: {caption_data['text']}")



pdf_path = 'file.pdf'
doc = fitz.open(pdf_path)

# Organize tables and captions by page
tables_by_page = {}
if 'extracted_tables_data' in locals():
    for page_data in extracted_tables_data:
        tables_by_page[page_data['page']] = page_data['tables']

captions_by_page = {}
if 'extracted_captions' in locals():
    for caption_data in extracted_captions:
        page = caption_data['page']
        if page not in captions_by_page:
            captions_by_page[page] = []
        captions_by_page[page].append(caption_data['text'])

# Use filtered headings to assign page ranges
section_titles_ordered = list(section_contents.keys())
section_page_ranges = {}

# Handle "Metadata" section
if section_titles_ordered:
    first_heading_page = filtered_headings[0]['page'] if filtered_headings else 1
    section_page_ranges[section_titles_ordered[0]] = (1, first_heading_page - 1)

# Remaining sections
for i in range(1, len(section_titles_ordered)):
    start_page = filtered_headings[i-1]['page']
    end_page = filtered_headings[i]['page'] - 1 if i < len(filtered_headings) else doc.page_count
    section_page_ranges[section_titles_ordered[i]] = (start_page, end_page)

# Combine sections with tables and captions
final_combined_output_list = []

for section_title, section_text in section_contents.items():
    final_combined_output_list.append(f"\n--- Section: {section_title} ---\n")
    final_combined_output_list.append(section_text)
    final_combined_output_list.append("\n")

    # Get page range for section
    start_page, end_page = section_page_ranges.get(section_title, (0, -1))

    # Add tables in the section
    section_tables = []
    for page_num in range(start_page, end_page + 1):
        if page_num in tables_by_page:
            for table in tables_by_page[page_num]:
                section_tables.append({'page': page_num, 'table': table})

    if section_tables:
        final_combined_output_list.append(f"\n--- Tables in Section: {section_title} ---\n")
        section_tables.sort(key=lambda x: x['page'])
        for table_data in section_tables:
            page_num = table_data['page']
            table = table_data['table']
            final_combined_output_list.append(f"\nTable on Page {page_num}:\n")
            final_combined_output_list.append(format_table_as_markdown(table))
            final_combined_output_list.append("-" * 20)
        final_combined_output_list.append("\n")

    # Add figure captions in the section
    section_captions = []
    for page_num in range(start_page, end_page + 1):
        if page_num in captions_by_page:
            for caption in captions_by_page[page_num]:
                section_captions.append({'page': page_num, 'text': caption})

    if section_captions:
        final_combined_output_list.append(f"\n--- Figure Captions in Section: {section_title} ---\n")
        section_captions.sort(key=lambda x: x['page'])
        for caption_data in section_captions:
            page_num = caption_data['page']
            caption_text = caption_data['text']
            final_combined_output_list.append(f"- Page {page_num}: {caption_text}\n")
        final_combined_output_list.append("\n")

doc.close()

# Final combined string
final_combined_output = "\n".join(final_combined_output_list)

# Preview first 10000 characters
print(final_combined_output[:50000])


import re

# === STEP 1: Chunking with overlap ===
def chunk_text_with_headings(text, max_chunk_size=1200, overlap=200):
    sections = re.split(r"(?i)(?=^\s*(?:abstract|introduction|related work|conclusion|references|section|chapter)[\s:])", 
                        text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        heading_match = re.match(r"^\s*(.+)", section.strip(), flags=re.MULTILINE)
        heading = heading_match.group(1) if heading_match else "Unnamed Section"

        start = 0
        while start < len(section):
            end = min(start + max_chunk_size, len(section))
            chunk = section[start:end].strip()
            if chunk:
                chunks.append((heading, chunk))
            start = end - overlap if end - overlap > start else end
    return chunks


# === STEP 2: Summarize individual chunks (short + precise) ===
def summarize_chunk_with_groq(chunk_text, heading):
    try:
        completion = client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[{
                "role": "user",
                "content": (
                    f"You are an expert research assistant.\n\n"
                    f"Section heading: {heading}\n\n"
                    f"Text:\n{chunk_text}\n\n"
                    f"Task: Write a very concise summary (3–4 sentences maximum). "
                    f"Prefer brevity over detail. Remove pseudocode, examples, and lists unless essential. "
                    f"Keep only the scientific insights."
                )
            }],
            temperature=0.4,
            max_completion_tokens=150,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"


# === STEP 3: Group summaries in batches ===
def batch_summarize_summaries(summaries, heading, batch_size=5):
    grouped = []
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i+batch_size]
        batch_text = "\n\n".join(batch)

        print(f"\n[INFO] Merging batch {i//batch_size + 1} for section: {heading}...")

        try:
            completion = client.chat.completions.create(
                model="gemma2-9b-it",
                messages=[{
                    "role": "user",
                    "content": (
                        f"Section heading: {heading}\n\n"
                        f"Here are partial summaries:\n{batch_text}\n\n"
                        f"Task: Merge these into a single concise summary (max 6 sentences). "
                        f"Remove redundancy and irrelevant details, but preserve all key insights."
                    )
                }],
                temperature=0.3,
                max_completion_tokens=200,
            )
            group_summary = completion.choices[0].message.content.strip()
            grouped.append(group_summary)

            # ✅ Log intermediate group summary
            print(f"[GROUP SUMMARY {i//batch_size + 1}] {group_summary}\n")

        except Exception as e:
            grouped.append(f"Error: {e}")
    return grouped


# === STEP 4: Final summary of group summaries ===
def finalize_section_summary(grouped_summaries, heading):
    all_text = "\n\n".join(grouped_summaries)
    print(f"\n[INFO] Creating detailed final summary for section: {heading}...")

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": (
                    f"Final synthesis for section: {heading}\n\n"
                    f"Partial summaries:\n{all_text}\n\n"
                    f"Task: Write a detailed, structured, and comprehensive final summary. "
                    f"Length should be equivalent to 1.5–2 pages of text (~800–1200 words). "
                    f"Organize the summary into clear paragraphs (at least 6–10). "
                    f"Cover all critical points, technical insights, and nuances from the grouped summaries. "
                    f"Do not shorten excessively, and ensure readability. "
                    f"Avoid redundant filler and skip citation numbers."
                )
            }],
            temperature=0.3,
            max_completion_tokens=1500,  # ✅ supports ~2 pages
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"


# === MASTER FUNCTION ===
def process_section(text, section_heading):
    print(f"\n--- Processing Section: {section_heading} ---")

    result = {
        "section": section_heading,
        "chunk_summaries": [],
        "group_summaries": [],
        "final_summary": ""
    }

    # Step 1: Chunk section
    chunks = chunk_text_with_headings(text)

    # Step 2: Summarize chunks
    chunk_summaries = []
    for heading, chunk in chunks:
        summary = summarize_chunk_with_groq(chunk, heading)
        chunk_summaries.append(summary)
    result["chunk_summaries"] = chunk_summaries

    # Step 3: Batch summarize
    grouped_summaries = batch_summarize_summaries(chunk_summaries, section_heading, batch_size=5)
    result["group_summaries"] = grouped_summaries

    # Step 4: Final summary
    final_summary = finalize_section_summary(grouped_summaries, section_heading)
    result["final_summary"] = final_summary

    print(f"\n[FINAL SUMMARY for {section_heading}] {final_summary}\n")

    return result


# === CALLING EXAMPLE ===
# Suppose `intro_text` contains the "Introduction" section of the paper:
# intro_result = process_section(intro_text, "Introduction")
# print(intro_result)


# === AFTER EXTRACTION ===

# You already have:
# final_combined_output = "\n".join(final_combined_output_list)

# Now run the summarization pipeline
result = process_section(final_combined_output, "Full Document")

# Print results
print("\n=== RESULTS ===")
print("\n--- Chunk Summaries ---")
for i, cs in enumerate(result["chunk_summaries"], 1):
    print(f"[Chunk {i}] {cs}")

print("\n--- Group Summaries ---")
for i, gs in enumerate(result["group_summaries"], 1):
    print(f"[Group {i}] {gs}")

print("\n--- Final Summary ---")
print(result["final_summary"])


import json # Import the json library

# Save everything (chunks + groups + final) in JSON
with open("summaries.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=4, ensure_ascii=False)

# Save just the polished final summary in TXT
with open("final_summary.txt", "w", encoding="utf-8") as f:
    f.write(result["final_summary"])

print("\n[INFO] All summaries saved to summaries.json and final_summary.txt ✅")
