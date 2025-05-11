# Social Media Banner Spelling Checker

An AI-powered spelling checker application that helps identify and correct spelling mistakes in social media content and images.

## Features

- **Text Spelling Check**: Analyze text input for spelling errors
- **Image Text Extraction**: Extract text from uploaded images
- **Spelling Suggestions**: Get correct spelling suggestions for misspelled words
- **Multi-language Support**: Works with English and Bengali text
- **Smart Filtering**: Automatically skips URLs, email addresses, phone numbers, and product names

## Technologies Used

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **AI Integration**: Google's Gemini AI API
- **Image Processing**: PIL (Python Imaging Library)

## Live Demo
https://spellcheck.parviit.com

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/jonyprachine123/spelling_checker.git
   cd spelling_checker
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your Gemini API key:
   - Get an API key from [Google AI Studio](https://ai.google.dev/)
   - Update the `API_KEY` variable in `app.py`

4. Run the application:
   ```
   python app.py
   ```

5. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

## Usage

### Text Input
1. Enter your text in the input field
2. Click "Check Spelling"
3. Review the results showing any misspelled words and suggestions

### Image Upload
1. Upload an image containing text
2. The AI will extract the text automatically
3. Review the extracted text and spelling analysis

## Rate Limiting

The application includes rate limiting to prevent excessive API calls. If you exceed the rate limit, it will use a fallback spell checker.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Developer

Developed by Shamim MD Jony

---

Feel free to contribute to this project by submitting issues or pull requests!
