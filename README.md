# Regulatory-Classifier

I am doing a different hackathon challenge where I have to classify documents based on their safety. I will post the challenge information below

AI-Powered Regulatory Document Classifier — Datathon Submission
Description
Build an AI-powered assistant that dynamically analyzes multi-page, multi-modal documents to classify them into Public, Confidential, Highly Sensitive, or Unsafe categories. The solution should leverage a configurable prompt library to generate dynamic prompt trees, incorporate Human-in-the-Loop (HITL) feedback to improve accuracy over time, and support both interactive and batch processing with real-time status updates. Pre-processing checks (e.g., legibility, page/image counts) are required. Outputs must include citation-based evidence pointing to the exact pages or images that led to each classification. Optionally, teams may employ two LLMs to cross-verify classifications to reduce HITL needs. The UI should be business-friendly with visualizations, detailed classification reports, audit trails, and easy file management, while ensuring compliance with data privacy and security policies.
Categories
1.	Sensitive/Highly Sensitive: Content that includes PII like SSNs, account/credit card numbers, and proprietary schematics (e.g., defense or next‑gen product designs of military equipment).  
2.	Confidential: Internal communications and business documents, customer details (names, addresses), and non-public operational content.
3.	Public: Marketing materials, product brochures, public website content, generic images.
4.	Unsafe Content: In any case all content should be evaluated for Child Safety and should not include Hate speech, exploitative, violent, criminal, political news or cyber-threat content.

Evaluation Criteria
I.	Multi-modal input: accept text, images, and optional video.
II.	Interactive and batch processing modes with real-time status updates.
III.	Pre-processing checks: document legibility, page and image count.
IV.	Dynamic prompt tree generation from a configurable prompt library.
V.	Citation-based results: reference exact pages or images for audit and compliance.
VI.	Safety monitoring: automatically detect Unsafe content and flag for human review.
VII.	HITL feedback loop: enable SMEs to validate outputs and refine prompt logic.
VIII.	Double-layered AI validation (optional): two LLMs to cross-verify classifications.
IX.	Rich UI: clear visualizations, detailed classification reports, audit trails, and file management.
Test Cases (for Judging & Testing)
Use these five test cases to verify end-to-end functioning, performance of the categorizations of compliance using the files with the same name as the input data.
1.	TC1 — Public Marketing Document
Input: Multi-page brochure or program viewbook (Public)
Expected Category: Public
Judging Focus: Public; verify pre-checks and page-level citations.
Expected Outcome:
•	# of pages in the document
•	# of Images
•	Evidence Required: Cite pages containing only public marketing statements; confirm no PII or confidential details.
•	Content Safety: Content is safe for the kids.

2.	TC2 — Filled In Employment Application (PII)
Input: Application form containing synthetic PII (name, address, SSN)
Expected Category: Highly Sensitive
Judging Focus: PII detection and precise citations; HITL handoff optional.
Expected Outcome:
•	# of pages in the document
•	# of Images
•	Evidence Required: Cite the field(s) containing SSN or other PII; show redaction suggestions if supported.
•	Content Safety: Content is safe for the kids.

3.	TC3 — Internal Memo (No PII)
Input: Internal project memo with milestones/risks; no PII
Expected Category: Confidential (Important/Internal)
Judging Focus: Policy reasoning for internal but non-sensitive content; UI explanation clarity.
Expected Outcome:
•	# of pages in the document
•	# of Images
•	Evidence Required: Cite internal-only operational details; confirm absence of PII.
•	Content Safety: Content is safe for the kids.

4.	TC4 — Stealth Fighter with part names
Input: High-resolution image of stealth Fighter
Expected Category: Confidential (policy-based)
Judging Focus: Image handling, region citation, policy explanation.
Expected Outcome:
•	# of pages in the document
•	# of Images
•	Evidence Required: Cite the region with the serial; explain policy mapping for identifiable equipment.
•	Content Safety: Content is safe for the kids.

5.	TC5 – Testing multiple non-compliance categorizations
Input: document embedded with a stealth fighter and kid's unsafe content
Expected Category: Confidential (policy-based) and Unsafe
Judging Focus: Image handling, region citation, policy explanation.
Expected Outcome:
•	# of pages in the document
•	# of Images
•	Evidence Required: Cite the region with the serial; explain policy mapping for identifiable equipment and where and why content is unsafe
•	Content Safety: Content is safe for the kids.

Scoring & Rubric
1.	Classification Accuracy (50%): Precision/recall on the five test cases, correct category mapping, and clarity of page/region citations.
2.	Reducing HITL involvement (20%): Confidence scoring, optional dual-LLM consensus, clear reviewer queue, and reduction of manual review time.
3.	Processing Speed (10%): Aside the throughput and responsiveness aligned with typical business SLAs for batch and interactive modes, the emphasis here is on leverage Light weight or SLM models that are cheaper yet give the best accuracy.  Cite your model used for the problem during submission.
4.	User Experience & UI (10%): Clear explanations, audit-ready reports, region highlights for images, and straightforward file management.
5.	Content Safety evaluation (10%):  Ensure the content is always validated for Child Safety and should not include Hate speech, exploitative, violent, criminal, political news or cyber-threat content.
Submission Notes
1.	End to end demo video showcasing a flow by uploading the documents and categorizing it against the provided categories. 
2.	The AI should provide a summary alongside the reason on why it is categorized in the respective category. (reasoning module)
3.	Cite your model used for the problem during submission.




