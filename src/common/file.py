import re
import unicodedata

def clean_string(input_str):
    return ''.join(
        c for c in input_str
        if not unicodedata.category(c).startswith('C')  # Remove control characters
        and c != '\t'
        and c != '\r'
    )

def sanitize_file_name(name: str, replacement: str = "") -> str:
    cleaned_from_non_printable = clean_string(name)

    harmful_chars = r'[<>:"/\\|?*]'
    safe_name = re.sub(harmful_chars, replacement, cleaned_from_non_printable)
    return safe_name.strip()
