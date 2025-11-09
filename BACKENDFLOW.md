Perfect — let’s focus on **just the analysis pipeline** and **what LLMs to use** for this hackathon challenge.

Below is a concise but complete breakdown of **how your backend should analyze PDFs/text** (step-by-step) and **which models to use** for best performance, cost, and hackathon practicality.

---

## 🧠 1. The Core “Analysis Pipeline” — Step-by-Step

Here’s the data flow for analyzing **any uploaded document** (PDF, image, etc.) before classification.

### **Step 1 — Preprocessing**

Purpose: clean & structure the data before AI touches it.

* **PDF split** → extract each page.
* **OCR** each page if scanned or image-based.

  * Tools: `pytesseract`, `paddleocr`, or AWS Textract.
  * Output → `[(page_number, text, bounding_boxes, confidence_scores)]`
* **Page metrics** → count total pages, count images, check legibility (average OCR confidence).
* **Extract embedded images** for visual classification.

---

### **Step 2 — Basic Rule-Based Extraction**

Before invoking any LLM, catch obvious features with fast code.

**Why?** You save tokens and get structured “evidence candidates.”

* **PII Detection**

  * Regex: SSN, credit card, email, phone, address, etc.
  * Use: `re`, `phonenumbers`, or `presidio-analyzer`.
* **Sensitive Keywords**

  * Defense terms, internal code names, financial language.
* **Safety Filters** (text-only):

  * Pre-trained small model (like `roberta-base-openai-detector`, `hate-speech-roberta`, or `Detoxify`).
* **Output Example:**

  ```json
  {
    "page": 2,
    "matches": [
      {"type": "SSN", "text": "123-45-6789"},
      {"type": "Keyword", "text": "stealth fighter"}
    ]
  }
  ```

This gives structured “evidence” that the LLM can reason over.

---

### **Step 3 — LLM Analysis (Context-Aware Classification)**

Now you pass text + evidence + image summaries into the LLM.

Each page (or the full doc) goes through **a dynamic prompt**, like:

```
Given the extracted text, detected PII fields, and image objects, classify this document 
as one of [Public, Confidential, Highly Sensitive, Unsafe]. 
Provide reasoning and cite which pages or fields triggered your classification.
```

**Output Schema (structured JSON)**:

```json
{
  "classification": "Highly Sensitive",
  "confidence": 0.93,
  "reasons": ["SSN found on page 2"],
  "evidence_pages": [2]
}
```

LLM reasoning = explanation + traceability.

---

### **Step 4 — (Optional) Dual-LLM Validation**

To increase trust and reduce manual review (HITL):

1. **Primary LLM:** Does the full reasoning + classification.
2. **Secondary LLM:** Reads the primary’s result and either confirms or disputes it.

**Example logic:**

* If both models agree (same label) → mark as confident.
* If disagreement → send to human review.

---

### **Step 5 — Combine, Aggregate, and Cite**

At the end:

* Aggregate all page-level outputs → document-level category.
* Collect cited pages and regions → build “Evidence Summary.”
* Attach reasoning and model confidences.
* Return result as JSON (and optionally produce a visual overlay in the UI).

---

## ⚙️ 2. Recommended LLM Stack for Your Backend

You need models that are:
✅ Fast
✅ Affordable (hackathon-friendly)
✅ Good with both reasoning + compliance tone

### **🧩 Tiered LLM Setup**

| Role                                    | Model Type                      | Example Models                                                  | Purpose                                                                                               |
| --------------------------------------- | ------------------------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Primary Classifier**                  | Mid/large reasoning model       | `GPT-4o-mini`, `Claude 3 Haiku`, or `Gemini 1.5 Flash`          | Interpret text, reason contextually, produce structured JSON outputs with classification + reasoning. |
| **Secondary Validator (optional)**      | Small/fast model                | `GPT-4o-mini`, `Llama 3 8B`, or `Mistral 7B Instruct`           | Cross-check classification or validate reasoning for consensus.                                       |
| **Pre-filter / PII & safety detection** | Tiny specialized model (no LLM) | spaCy NER, `Presidio`, `Detoxify`, `OpenAI moderation` endpoint | Quickly detect PII and unsafe patterns before sending to LLM.                                         |

---

### **📊 Why this combo works**

* The smaller pre-filters cut down on cost & token usage by handling obvious detections.
* A mid-size reasoning model (like GPT-4o-mini or Claude Haiku) has enough “policy awareness” to reason about compliance and sensitivity.
* If you want dual-LLM verification, run the same prompt through `Mistral 7B` (self-hosted) or `Gemini Flash` for a sanity check — it’s fast and can catch hallucinations.

---

### **💡 Example workflow with GPT-4o-mini**

```python
prompt = f"""
You are a compliance classifier. Analyze the document text and metadata below.
Return a JSON with classification, reasoning, and evidence pages.

Document Text:
{page_text}

Detected Entities:
{detected_entities}

Categories:
1. Public
2. Confidential
3. Highly Sensitive
4. Unsafe
"""

response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    response_format="json"
)
```

Then you can run:

```python
classification = response.choices[0].message["content"]
```

---

### **Optional: Self-Hosted Local Models (if internet-limited)**

If you want to run locally (e.g., for privacy or offline hackathon judging):

* **Reasoning/Classifier:** `Llama 3 8B` or `Mistral 7B Instruct`
* **OCR + PII + Safety:** local tools (Tesseract + spaCy + Detoxify)
* Use `vLLM` or `Ollama` for inference — good latency and can serve JSON outputs reliably.

---

## 🧩 3. What the Backend Actually Returns

Each run of your backend should output:

```json
{
  "document_id": "app_form_01.pdf",
  "pages": 3,
  "classification": "Highly Sensitive",
  "confidence": 0.92,
  "reasons": ["Detected SSN pattern on page 2", "Contains address and bank details"],
  "citations": [{"page": 2, "snippet": "SSN: 123-45-6789"}],
  "safety_check": "Safe",
  "models_used": {
    "primary": "gpt-4o-mini",
    "secondary": "mistral-7b-instruct"
  }
}
```

---

## ✅ TL;DR Summary

| Stage                             | Purpose                                         | Tools/Models                               |
| --------------------------------- | ----------------------------------------------- | ------------------------------------------ |
| **Preprocessing**                 | OCR, legibility, count pages/images             | Tesseract / PaddleOCR                      |
| **Rule-based Extraction**         | Detect PII, keywords, unsafe terms              | Regex, spaCy NER, Presidio                 |
| **LLM Classification**            | Reason about sensitivity + produce explanations | GPT-4o-mini / Claude Haiku                 |
| **Cross-Verification (optional)** | Validate first model’s reasoning                | Mistral 7B / Gemini Flash                  |
| **Safety Check**                  | Detect unsafe content (text/images)             | Detoxify, NSFW detector, OpenAI moderation |
| **Aggregation**                   | Merge outputs and produce final JSON            | Your backend logic (FastAPI, Python)       |

---

Would you like me to outline **how to structure the prompt library + dynamic prompt selection logic** next (i.e., how to auto-select which prompt to send to the LLM based on detections)? That’s the key piece that makes your system “configurable and dynamic.”
