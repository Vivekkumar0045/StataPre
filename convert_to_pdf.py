import markdown
import pdfkit
from pathlib import Path

def convert_markdown_to_pdf():
    # Read the markdown file
    readme_path = Path("README.md")
    
    if not readme_path.exists():
        print("README.md not found!")
        return
    
    with open(readme_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    # Convert markdown to HTML
    html = markdown.markdown(markdown_content, extensions=['codehilite', 'fenced_code'])
    
    # Add CSS styling for better PDF appearance
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3, h4 {{
                color: #2c3e50;
                margin-top: 30px;
            }}
            h1 {{
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }}
            h2 {{
                border-bottom: 1px solid #bdc3c7;
                padding-bottom: 5px;
            }}
            code {{
                background-color: #f8f9fa;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }}
            pre {{
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 5px;
                padding: 15px;
                overflow-x: auto;
            }}
            blockquote {{
                border-left: 4px solid #3498db;
                padding-left: 20px;
                margin-left: 0;
                color: #7f8c8d;
            }}
            ul, ol {{
                padding-left: 20px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
        </style>
    </head>
    <body>
    {html}
    </body>
    </html>
    """
    
    # Convert HTML to PDF
    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': "UTF-8",
        'no-outline': None,
        'enable-local-file-access': None
    }
    
    try:
        pdfkit.from_string(styled_html, 'README.pdf', options=options)
        print("✅ PDF created successfully: README.pdf")
    except Exception as e:
        print(f"❌ Error creating PDF: {e}")
        print("\n📋 Alternative methods:")
        print("1. Install wkhtmltopdf: https://wkhtmltopdf.org/downloads.html")
        print("2. Or use online converters like markdown-pdf.com")
        print("3. Or use VS Code with 'Markdown PDF' extension")

if __name__ == "__main__":
    convert_markdown_to_pdf()