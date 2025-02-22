################### Folder Structure ##################################

# folder to put all the pdfs found in raw pdf folder
PDF_PAPERS_FOLDER = "resources/papers"

# Original PDFs
PDF_PAPERS_RAW_FOLDER = "resources/papers_raw"

# Json file that should contain list of objects with fields title (paper title)
# and id - a reference key
JSON_REFERENCE_KEY_FILE = "Thesis.json"

# Folder to export raw text from PDFs
EXTRACTED_TEXT_FOLDER = "resources/extracted"

# Folder to export token count of texts from PDFs
TOKEN_COUNT_FOLDER = "resources/token_count"

# Folder for outputting notes out of the paper
NOTES_OUTPUT_FOLDER = "resources/notes"

################### Models  ##################################

# Models used for calculating number of tokens
TOKENIZER_MODEL = "Kijai/llava-llama-3-8b-text-encoder-tokenizer"

################### API ##################################

# Key used to call open router
OPENROUTER_API_KEY="" # TODO: your open-router API key goes here

# Open router base url
OPENROUTER_URL = "https://openrouter.ai/api/v1"

# API has maximum input token limit
MAX_API_TOKENS_ALLOWED = 10e5

# Limit concurrent requests to open router
MAX_CONCURRENT_REQUESTS = 10


################### Other  ##################################

# Total max is 128 minus 4 in ".pdf"
MAX_CHARS_IN_FILE_NAME = 128 - 4
