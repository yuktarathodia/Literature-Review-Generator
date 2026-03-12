# 📄 Literature Review Generator
*A fully automated pipeline to parse PDFs, extract structure, and generate high-quality hierarchical literature reviews using LLMs.*

---

## 🚀 Overview

Research papers, technical documents, and financial PDFs are long, unstructured, and time-consuming to read.

This project provides an **end-to-end automated system** that:

- Extracts text, tables, and metadata from PDFs  
- Reconstructs semantic structure using Regex + layout analysis  
- Uses a **Map-Reduce summarization pipeline** to overcome LLM context limits  
- Generates coherent, high-level summaries using Groq LPU-powered models  
- Produces clean JSON output for downstream systems  

---

## 🧠 Key Features

### 🔍 1. PDF Parsing & Layout Reconstruction
- **PyMuPDF (fitz)** for text extraction with bounding boxes  
- **pdfplumber** for high-accuracy table extraction  
- Supports complex layouts:
  - Multi-column documents  
  - Headers & footers  
  - Sidebars  
  - Tables and figures  

### ✨ 2. Section Detection & Document Structuring
- Advanced Regex patterns detect:
  - Numeric headings (`1. Introduction`)
  - Roman numeral sections (`I. Background`)
  - Common academic keywords (Abstract, Results, Conclusion)
- Combines Regex + layout heuristics (font size, spacing)
- Builds a clean **hierarchical structure**:

### Section → Subsection → Paragraph


### 🧩 3. Map-Reduce Hierarchical Summarization
To handle long PDFs without exceeding context limits:

**Map Step**  
- Split PDF text into overlapping chunks  
- Summarize each chunk using **Gemma-2 9B** (fast + low cost)

**Reduce Step**  
- Merge chunk summaries  
- Generate final summary using **Llama-3.3-70B** (high quality)

### ⚡ 4. Ultra-Fast AI Processing via Groq
- Summarization runs on **Groq LPUs** → extremely low latency  
- Supports concurrent summarization for large PDFs  

### 📦 5. Clean JSON Output
```json
{
  "title": "...",
  "sections": {...},
  "tables": [...],
  "final_summary": "..."
}


