import os
import PyPDF2
import csv
import io
import docx
import magic
from typing import Optional
import json
import xml.etree.ElementTree as ET

async def extract_text_from_file(file_content: bytes, filename: str) -> Optional[str]:
    """
    Extract text from various file formats.
    
    Args:
        file_content: Raw file content
        filename: Original filename
        
    Returns:
        Extracted text or None if extraction failed
    """
    # Detect MIME type
    mime = magic.Magic(mime=True)
    file_type = mime.from_buffer(file_content)
    
    # Handle different file types
    try:
        if file_type == 'application/pdf':
            return extract_from_pdf(file_content)
        elif file_type == 'text/plain':
            return file_content.decode('utf-8')
        elif file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            return extract_from_docx(file_content)
        elif file_type in ['text/csv', 'application/csv']:
            return extract_from_csv(file_content)
        elif file_type in ['application/json']:
            return extract_from_json(file_content)
        elif file_type in ['application/xml', 'text/xml']:
            return extract_from_xml(file_content)
        else:
            # Try to decode as text
            try:
                return file_content.decode('utf-8')
            except UnicodeDecodeError:
                return None
    except Exception as e:
        print(f"Error extracting text: {e}")
        return None

def extract_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF."""
    text = ""
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
    for page_num in range(len(pdf_reader.pages)):
        text += pdf_reader.pages[page_num].extract_text() + "\n\n"
    return text

def extract_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX."""
    doc = docx.Document(io.BytesIO(file_content))
    return "\n\n".join([para.text for para in doc.paragraphs if para.text])

def extract_from_csv(file_content: bytes) -> str:
    """Extract text from CSV."""
    text = ""
    try:
        # Try UTF-8 first
        csv_text = file_content.decode('utf-8')
    except UnicodeDecodeError:
        # Fall back to Latin-1
        csv_text = file_content.decode('latin-1')
    
    csv_reader = csv.reader(io.StringIO(csv_text))
    for row in csv_reader:
        text += ", ".join(row) + "\n"
    return text

def extract_from_json(file_content: bytes) -> str:
    """Extract text from JSON."""
    try:
        # Parse JSON
        json_data = json.loads(file_content.decode('utf-8'))
        
        # Convert to string representation
        if isinstance(json_data, dict):
            return "\n".join([f"{k}: {v}" for k, v in flatten_dict(json_data).items()])
        elif isinstance(json_data, list):
            return "\n\n".join([json.dumps(item, indent=2) for item in json_data])
        else:
            return str(json_data)
    except:
        # Return raw content if parsing fails
        return file_content.decode('utf-8')

def extract_from_xml(file_content: bytes) -> str:
    """Extract text from XML."""
    try:
        root = ET.fromstring(file_content.decode('utf-8'))
        return extract_text_from_element(root)
    except:
        # Return raw content if parsing fails
        return file_content.decode('utf-8')

def extract_text_from_element(element: ET.Element, path: str = "") -> str:
    """Recursively extract text from XML element."""
    result = []
    
    # Add element text
    if element.text and element.text.strip():
        if path:
            result.append(f"{path}: {element.text.strip()}")
        else:
            result.append(element.text.strip())
    
    # Process attributes
    for attr_name, attr_value in element.attrib.items():
        attr_path = f"{path}@{attr_name}" if path else f"@{attr_name}"
        result.append(f"{attr_path}: {attr_value}")
    
    # Process child elements
    for child in element:
        child_path = f"{path}/{child.tag}" if path else child.tag
        result.append(extract_text_from_element(child, child_path))
    
    return "\n".join(result)

def flatten_dict(d: dict, parent_key: str = '') -> dict:
    """Flatten a nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)