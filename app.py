from flask import Flask, render_template, request, jsonify, url_for, redirect
import google.generativeai as genai
import os
import uuid
from PIL import Image
from werkzeug.utils import secure_filename
import base64
import requests
import json
import logging
import time
import re
import PyPDF2

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure the Gemini API
API_KEY = "AIzaSyA8k5-cC2WGEbgo6S-zuxPNcj8MmxBiVkU"
genai.configure(api_key=API_KEY)

# Initialize Gemini models - use the latest Gemini 2.5 Pro model
model = genai.GenerativeModel('gemini-2.0-flash')  # Latest Gemini 2.5 Pro model

# Configure upload folder
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Rate limiting configuration
RATE_LIMIT_WINDOW = 120  # 60 seconds
MAX_REQUESTS_PER_WINDOW = 50
request_timestamps = []

def check_rate_limit():
    """Simple rate limiting implementation"""
    global request_timestamps
    current_time = time.time()
    
    # Remove timestamps older than the window
    request_timestamps = [ts for ts in request_timestamps if current_time - ts < RATE_LIMIT_WINDOW]
    
    # Check if we've hit the limit
    if len(request_timestamps) >= MAX_REQUESTS_PER_WINDOW:
        return False
    
    # Add current timestamp and allow the request
    request_timestamps.append(current_time)
    return True

def basic_spell_check(word):
    """Basic fallback spell checker when API rate limit is reached"""
    # Common misspellings dictionary - can be expanded
    common_misspellings = {
        'teh': 'the',
        'recieve': 'receive',
        'wierd': 'weird',
        'thier': 'their',
        'accomodate': 'accommodate',
        'occured': 'occurred',
        'seperate': 'separate',
        'definately': 'definitely',
        'pharoah': 'pharaoh',
        'publically': 'publicly',
        'truely': 'truly',
        'tommorrow': 'tomorrow',
        'gaurd': 'guard',
        'untill': 'until',
        'wich': 'which',
        'recieved': 'received',
        'beleive': 'believe',
        'concious': 'conscious',
        'existance': 'existence',
        'goverment': 'government',
        'independant': 'independent',
        'occassion': 'occasion',
        'prefered': 'preferred',
        'priviledge': 'privilege',
        'restaurent': 'restaurant',
        'succesful': 'successful',
    }
    
    # Check if word is in common misspellings
    if word.lower() in common_misspellings:
        return False, common_misspellings[word.lower()]
    
    # Very basic check for repeated letters
    repeated_chars = re.findall(r'(.)\1{2,}', word)
    if repeated_chars:
        return False, word
    
    # Default to assuming it's correct if we can't determine otherwise
    return True, ""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file using PyPDF2"""
    try:
        logger.info(f"Extracting text from PDF: {pdf_path}")
        
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
        
        logger.info(f"Successfully extracted text from PDF")
        return text.strip() or "No text detected in the PDF."
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return f"Error extracting text from PDF: {str(e)}"

def extract_text_from_image_with_gemini(image_path):
    """Extract text from image using Gemini Vision API"""
    try:
        logger.info(f"Extracting text from image: {image_path}")
        
        # Check rate limit
        if not check_rate_limit():
            logger.warning("Rate limit exceeded for image text extraction")
            return "Rate limit exceeded. Please try again later."
            
        # Load the image
        img = Image.open(image_path)
        
        # Ask Gemini to extract text from the image
        prompt = "Extract all the text from this image. Return only the extracted text, nothing else."
        response = model.generate_content([prompt, img])
        
        # Get the extracted text
        extracted_text = response.text.strip()
        logger.info(f"Successfully extracted text from image")
        
        return extracted_text or "No text detected in the image."
    except Exception as e:
        logger.error(f"Error extracting text with Gemini: {e}")
        if "429" in str(e) or "quota" in str(e).lower():
            return "API quota exceeded. Please try again later."
        return f"Error extracting text: {str(e)}"

def check_spelling_from_text(text):
    # This mirrors the logic from check_spelling, but for internal use (no Flask request context)
    words = text.split()
    results = []
    api_quota_exceeded = False
    
    # Regular expressions to identify URLs, emails, phone numbers, and product names
    url_pattern = re.compile(r'^(https?:\/\/)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$')
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    phone_pattern = re.compile(r'^\+?[\d\s\(\)-]{7,}$')
    product_pattern = re.compile(r'^([A-Z0-9]+-[A-Za-z0-9]+|[A-Z][A-Za-z0-9]*[0-9]+[A-Za-z0-9]*|[A-Z][A-Za-z]+\s[0-9]+(\.[0-9]+)?|[A-Z][A-Za-z]+-[A-Za-z0-9]+)$')
    
    for i, word in enumerate(words):
        try:
            # Skip URLs, emails, phone numbers, and product names
            if (url_pattern.match(word) or 
                email_pattern.match(word) or 
                phone_pattern.match(word) or
                product_pattern.match(word) or
                (word.isupper() and len(word) >= 2) or  # All caps words like "LUZ" are likely product names/acronyms
                (word[0].isupper() and any(c.isdigit() for c in word))  # Words starting with capital and containing numbers
               ):
                results.append({
                    'word': word,
                    'is_correct': True,  # Mark as correct to avoid flagging
                    'suggestion': '',
                    'full_response': "Skipped checking (URL/email/phone/product)"
                })
                continue
            
            # If we already hit the quota, use fallback
            if api_quota_exceeded:
                is_correct, suggestion = basic_spell_check(word)
                results.append({
                    'word': word,
                    'is_correct': is_correct,
                    'suggestion': suggestion,
                    'full_response': "Using fallback spell checker due to API quota exceeded"
                })
                continue
            
            prompt = f"""
            Check if the word '{word}' is spelled correctly.
            
            Instructions:
            1. Analyze the spelling of the word '{word}'
            2. If it's correct, respond with ONLY: "CORRECT"
            3. If it's incorrect, respond with: "INCORRECT: [correct_spelling]"
            4. For non-English words (like Bengali), make sure to provide the correct spelling
            5. IMPORTANT: Skip checking the following types of content:
               - Website addresses (URLs) like www.example.com
               - Email addresses like example@domain.com
               - Phone numbers and contact information
               - Social media handles (@username)
               - Product names and model numbers (like iPhone 13, LUZ-nol, etc.)
               - Brand names and trademarks
            
            Example responses:
            - "CORRECT" (if the word is spelled correctly)
            - "INCORRECT: [correct_spelling]" (if the word is misspelled)
            """
            
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Process the response - improved parsing
            is_correct = False
            suggestion = ""
            
            if response_text.upper().startswith("CORRECT"):
                is_correct = True
            elif response_text.upper().startswith("INCORRECT:"):
                is_correct = False
                # Extract suggestion directly from the structured response
                parts = response_text.split(":", 1)
                if len(parts) > 1:
                    suggestion = parts[1].strip()
            else:
                # Fallback to previous logic for unstructured responses
                if 'correct' in response_text.lower() and 'incorrect' not in response_text.lower():
                    is_correct = True
                elif 'incorrect' in response_text.lower():
                    is_correct = False
                    
                # Extract suggestion if available using patterns
                if not is_correct and not suggestion:
                    suggestion_patterns = [
                        r"correct spelling is[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"correct spelling[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"should be[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"correct form is[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"spelled as[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"spelled correctly as[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"correct version is[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"correct version[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"correction[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"correctly spelled[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"suggestion[:\s]+['\"]*([^'\".,\n\r]+)",
                        r"->\s*([^'\".,\n\r]+)"
                    ]
                    found = False
                    for pattern in suggestion_patterns:
                        match = re.search(pattern, response_text, re.IGNORECASE)
                        if match:
                            suggestion = match.group(1).strip()
                            found = True
                            break
                    # If not found, try to extract the first word after a colon or an arrow
                    if not found:
                        # Special case: response like 'incorrect: পণ্য'
                        if response_text.strip().lower().startswith('incorrect:'):
                            possible = response_text.split(':', 1)[1].strip().split()[0]
                            if possible and possible.lower() not in ['incorrect', 'correct']:
                                suggestion = possible
                        elif ":" in response_text:
                            parts = response_text.split(":", 1)
                            if len(parts) > 1:
                                possible = parts[1].strip().split()[0]
                                if possible.lower() not in ['incorrect', 'correct']:
                                    suggestion = possible
                        elif "->" in response_text:
                            parts = response_text.split("->", 1)
                            if len(parts) > 1:
                                possible = parts[1].strip().split()[0]
                                if possible.lower() not in ['incorrect', 'correct']:
                                    suggestion = possible
            
            results.append({
                'word': word,
                'is_correct': is_correct,
                'suggestion': suggestion,
                'full_response': response_text
            })
            time.sleep(0.2)
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                api_quota_exceeded = True
                is_correct, suggestion = basic_spell_check(word)
                results.append({
                    'word': word,
                    'is_correct': is_correct,
                    'suggestion': suggestion,
                    'full_response': "Using fallback spell checker due to API quota exceeded"
                })
            else:
                results.append({
                    'word': word,
                    'is_correct': False,
                    'suggestion': '',
                    'full_response': f"Error checking this word: {error_msg}"
                })
    return results

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        logger.info("Processing file upload request")
        if 'file' not in request.files:
            logger.warning("No file part in request")
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            logger.warning("No selected file")
            return jsonify({'error': 'No selected file'}), 400
        
        if file and allowed_file(file.filename):
            # Generate a unique filename
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save the file
            file.save(filepath)
            logger.info(f"File saved to {filepath}")
            
            # Extract text based on file type
            file_extension = filename.rsplit('.', 1)[1].lower()
            extracted_text = ""
            
            if file_extension == 'pdf':
                extracted_text = extract_text_from_pdf(filepath)
            else:
                # For image files, use Gemini
                extracted_text = extract_text_from_image_with_gemini(filepath)
            
            # Now, check spelling on the extracted text
            spelling_results = []
            if extracted_text and not extracted_text.lower().startswith('error') and not extracted_text.lower().startswith('api quota exceeded'):
                spelling_results = check_spelling_from_text(extracted_text)
            
            return jsonify({
                'success': True,
                'filename': filename,
                'filepath': url_for('static', filename=f'uploads/{filename}'),
                'extracted_text': extracted_text,
                'spelling_results': spelling_results
            })
        logger.warning("File type not allowed")
        return jsonify({'error': 'File type not allowed'}), 400
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/check_spelling', methods=['POST'])
def check_spelling():
    try:
        logger.info("Processing spelling check request")
        data = request.get_json()
        if not data:
            logger.warning("No JSON data in request")
            return jsonify({'error': 'No data provided'}), 400
            
        text = data.get('text', '')
        if not text:
            logger.warning("No text provided for spelling check")
            return jsonify({'error': 'No text provided'}), 400
        
        # Split the text into words
        words = text.split()
        logger.info(f"Checking spelling for {len(words)} words")
        
        # Check if we're hitting the rate limit
        if not check_rate_limit() and len(words) > 3:
            logger.warning("Rate limit exceeded, using fallback spell checker")
            # Use fallback for all words
            results = []
            for word in words:
                is_correct, suggestion = basic_spell_check(word)
                results.append({
                    'word': word,
                    'is_correct': is_correct,
                    'suggestion': suggestion,
                    'full_response': "Using fallback spell checker due to rate limiting"
                })
            return jsonify(results)
        
        results = []
        api_quota_exceeded = False
        
        # Regular expressions to identify URLs, emails, phone numbers, and product names
        url_pattern = re.compile(r'^(https?:\/\/)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$')
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        phone_pattern = re.compile(r'^\+?[\d\s\(\)-]{7,}$')
        product_pattern = re.compile(r'^([A-Z0-9]+-[A-Za-z0-9]+|[A-Z][A-Za-z0-9]*[0-9]+[A-Za-z0-9]*|[A-Z][A-Za-z]+\s[0-9]+(\.[0-9]+)?|[A-Z][A-Za-z]+-[A-Za-z0-9]+)$')
        
        for i, word in enumerate(words):
            try:
                logger.info(f"Checking word {i+1}/{len(words)}: '{word}'")
                
                # Skip URLs, emails, phone numbers, and product names
                if (url_pattern.match(word) or 
                    email_pattern.match(word) or 
                    phone_pattern.match(word) or
                    product_pattern.match(word) or
                    (word.isupper() and len(word) >= 2) or  # All caps words like "LUZ" are likely product names/acronyms
                    (word[0].isupper() and any(c.isdigit() for c in word))  # Words starting with capital and containing numbers
                   ):
                    results.append({
                        'word': word,
                        'is_correct': True,  # Mark as correct to avoid flagging
                        'suggestion': '',
                        'full_response': "Skipped checking (URL/email/phone/product)"
                    })
                    continue
                
                # If we already hit the quota, use fallback
                if api_quota_exceeded:
                    is_correct, suggestion = basic_spell_check(word)
                    results.append({
                        'word': word,
                        'is_correct': is_correct,
                        'suggestion': suggestion,
                        'full_response': "Using fallback spell checker due to API quota exceeded"
                    })
                    continue
                
                # Improved prompt for better spelling check and suggestion extraction
                prompt = f"""
                Check if the word '{word}' is spelled correctly.
                
                Instructions:
                1. Analyze the spelling of the word '{word}'
                2. If it's correct, respond with ONLY: "CORRECT"
                3. If it's incorrect, respond with: "INCORRECT: [correct_spelling]"
                4. For non-English words (like Bengali), make sure to provide the correct spelling
                5. IMPORTANT: Skip checking the following types of content:
                   - Website addresses (URLs) like www.example.com
                   - Email addresses like example@domain.com
                   - Phone numbers and contact information
                   - Social media handles (@username)
                   - Product names and model numbers (like iPhone 13, LUZ-nol, etc.)
                   - Brand names and trademarks
                
                Example responses:
                - "CORRECT" (if the word is spelled correctly)
                - "INCORRECT: [correct_spelling]" (if the word is misspelled)
                """
                
                response = model.generate_content(prompt)
                response_text = response.text.strip()
                
                # Process the response - improved parsing
                is_correct = False
                suggestion = ""
                
                if response_text.upper().startswith("CORRECT"):
                    is_correct = True
                elif response_text.upper().startswith("INCORRECT:"):
                    is_correct = False
                    # Extract suggestion directly from the structured response
                    parts = response_text.split(":", 1)
                    if len(parts) > 1:
                        suggestion = parts[1].strip()
                else:
                    # Fallback to previous logic for unstructured responses
                    if 'correct' in response_text.lower() and 'incorrect' not in response_text.lower():
                        is_correct = True
                    elif 'incorrect' in response_text.lower():
                        is_correct = False
                        
                    # Extract suggestion if available using patterns
                    if not is_correct and not suggestion:
                        suggestion_patterns = [
                            r"correct spelling is[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"correct spelling[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"should be[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"correct form is[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"spelled as[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"spelled correctly as[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"correct version is[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"correct version[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"correction[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"correctly spelled[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"suggestion[:\s]+['\"]*([^'\".,\n\r]+)",
                            r"->\s*([^'\".,\n\r]+)"
                        ]
                        found = False
                        for pattern in suggestion_patterns:
                            match = re.search(pattern, response_text, re.IGNORECASE)
                            if match:
                                suggestion = match.group(1).strip()
                                found = True
                                break
                        # If not found, try to extract the first word after a colon or an arrow
                        if not found:
                            # Special case: response like 'incorrect: পণ্য'
                            if response_text.strip().lower().startswith('incorrect:'):
                                possible = response_text.split(':', 1)[1].strip().split()[0]
                                if possible and possible.lower() not in ['incorrect', 'correct']:
                                    suggestion = possible
                            elif ":" in response_text:
                                parts = response_text.split(":", 1)
                                if len(parts) > 1:
                                    possible = parts[1].strip().split()[0]
                                    if possible.lower() not in ['incorrect', 'correct']:
                                        suggestion = possible
                            elif "->" in response_text:
                                parts = response_text.split("->", 1)
                                if len(parts) > 1:
                                    possible = parts[1].strip().split()[0]
                                    if possible.lower() not in ['incorrect', 'correct']:
                                        suggestion = possible
                
                results.append({
                    'word': word,
                    'is_correct': is_correct,
                    'suggestion': suggestion,
                    'full_response': response_text
                })
                
                # Add a small delay to avoid hitting rate limits too quickly
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error checking word '{word}': {e}")
                error_msg = str(e)
                
                # Check if we hit the API quota
                if "429" in error_msg or "quota" in error_msg.lower():
                    logger.warning("API quota exceeded, switching to fallback spell checker")
                    api_quota_exceeded = True
                    
                    # Use fallback for this word
                    is_correct, suggestion = basic_spell_check(word)
                    results.append({
                        'word': word,
                        'is_correct': is_correct,
                        'suggestion': suggestion,
                        'full_response': "Using fallback spell checker due to API quota exceeded"
                    })
                else:
                    results.append({
                        'word': word,
                        'is_correct': False,
                        'suggestion': '',
                        'full_response': f"Error checking this word: {error_msg}"
                    })
        
        logger.info("Spelling check completed successfully")
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in check_spelling: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
