# OCR Setup

OCR reads text shown inside images and scanned PDFs.

The app can find images and PDFs in a folder, but it needs local OCR tools on this computer to read text inside those files.

## Tools Used

- Tesseract: OCR engine
- tesseract-lang: language data such as Japanese
- Poppler: converts PDF pages into images for OCR

## Setup on Mac

Press "Set up OCR" in the plugin screen. The app uses Homebrew to install the required tools.

The first setup downloads data. The rough size is 50-200 MB, depending on your environment and language data.

After setup finishes, press "Recheck". OCR is ready when the screen shows "OCR: Tesseract".

## What It Can Do

- Read text from image files
- Read a few pages from scanned or image-only PDFs
- Use extracted text as local evidence in chat

## Limits

- Handwriting may not be accurate
- Low-quality scans may be incomplete
- Password-protected PDFs are not supported

## Note

OCR is not a language model. It is a local reading tool managed separately from Gemma, Qwen, and other LLMs.

Windows support is planned for a later version.
