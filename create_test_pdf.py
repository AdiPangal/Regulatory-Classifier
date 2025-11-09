"""Create a simple test PDF for testing purposes."""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pathlib import Path


def create_test_pdf(filename: str = "test.pdf", content: str = None):
    """Create a simple test PDF file.
    
    Args:
        filename: Output filename
        content: Optional custom content (default: sample text)
    """
    if content is None:
        content = """
        TEST DOCUMENT FOR REGULATORY CLASSIFIER
        
        This is a test document to verify the classification system.
        
        Page 1 Content:
        - This document contains test content
        - It should be classified as Public
        - No sensitive information is present
        
        Contact Information:
        Email: test@example.com
        Phone: (555) 123-4567
        
        This is a sample document for testing purposes.
        """
    
    # Create PDF
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Add text
    text = c.beginText(50, height - 50)
    text.setFont("Helvetica", 12)
    
    for line in content.split('\n'):
        text.textLine(line.strip())
        if text.getY() < 50:  # New page if needed
            c.drawText(text)
            c.showPage()
            text = c.beginText(50, height - 50)
            text.setFont("Helvetica", 12)
    
    c.drawText(text)
    c.save()
    
    print(f"Created test PDF: {filename}")


if __name__ == "__main__":
    # Check if reportlab is installed
    try:
        create_test_pdf()
    except ImportError:
        print("reportlab is not installed. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "reportlab"])
        create_test_pdf()

