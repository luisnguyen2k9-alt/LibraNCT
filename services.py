import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
import os
import base64
import requests
import cloudinary
import cloudinary.api
import cloudinary.uploader
from barcode import Code128
from barcode.writer import ImageWriter
from fpdf import FPDF
from io import BytesIO
import time
from PIL import Image # Thêm thư viện Pillow

load_dotenv()

# --- Email Sending ---
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# --- OCR Processing ---
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")
OCR_SPACE_URL = 'https://api.ocr.space/parse/image'

# --- Cloudinary Configuration ---
def configure_cloudinary():
    try:
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )
        print("Cloudinary configured successfully.")
    except Exception as e:
        print(f"CRITICAL: Failed to configure Cloudinary. Check .env variables. Error: {e}")


def generate_cloudinary_signature():
    try:
        timestamp = int(time.time())
        params_to_sign = {
            'timestamp': timestamp,
            'folder': 'library_cards'
        }
        signature = cloudinary.utils.api_sign_request(
            params_to_sign,
            os.getenv("CLOUDINARY_API_SECRET")
        )
        return {"timestamp": timestamp, "signature": signature}
    except Exception as e:
        print(f"Error generating Cloudinary signature: {e}")
        return None

# --- Service Functions ---

def process_ocr_for_text(base64_image_data):
    """Enhanced OCR processing for book scanning with better accuracy"""
    try:
        # Enhanced payload for better book text recognition
        payload = {
            'apikey': OCR_SPACE_API_KEY, 
            'language': 'vie+eng',  # Support both Vietnamese and English
            'isOverlayRequired': False,
            'base64image': f"data:image/jpeg;base64,{base64_image_data}", 
            'ocrengine': 2,  # Use OCR Engine 2 for better accuracy
            'detectOrientation': True,  # Auto-detect text orientation
            'scale': True,  # Scale image for better recognition
            'OCREngine': 2,
            'filetype': 'JPG',
            'isCreateSearchablePdf': False,
            'isSearchablePdfHideTextLayer': False
        }
        
        response = requests.post(OCR_SPACE_URL, data=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get('IsErroredOnProcessing'):
            raise Exception(f"OCR Error: {result.get('ErrorMessage')}")
        
        if result['ParsedResults']:
            raw_text = result['ParsedResults'][0]['ParsedText']
            
            # Clean and process the text for book recognition
            cleaned_text = clean_book_text(raw_text)
            return cleaned_text
            
        return None
        
    except requests.exceptions.Timeout:
        raise Exception("OCR request timeout. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"OCR service error: {str(e)}")
    except Exception as e:
        raise Exception(f"OCR processing failed: {str(e)}")

def clean_book_text(raw_text):
    """Clean and process OCR text for better book recognition"""
    if not raw_text:
        return ""
    
    # Remove extra whitespace and normalize
    text = ' '.join(raw_text.split())
    
    # Remove common OCR artifacts
    artifacts = [
        '|', '||', '|||', '||||',  # Common OCR artifacts
        '...', '....', '.....',     # Multiple dots
        '---', '----', '-----',     # Multiple dashes
        '___', '____', '_____',     # Multiple underscores
    ]
    
    for artifact in artifacts:
        text = text.replace(artifact, ' ')
    
    # Clean up multiple spaces
    text = ' '.join(text.split())
    
    # Extract potential book information
    lines = text.split('\n')
    book_info = []
    
    for line in lines:
        line = line.strip()
        if len(line) > 2:  # Ignore very short lines
            # Check if line looks like book title or ID
            if (len(line) > 5 and 
                (line.isupper() or  # All caps (common for book IDs)
                 any(char.isdigit() for char in line) or  # Contains numbers
                 len(line.split()) >= 2)):  # Multiple words
                book_info.append(line)
    
    # Return the most relevant text
    if book_info:
        # Prioritize longer text (likely book titles)
        return max(book_info, key=len)
    else:
        # Return first non-empty line
        return text.split('\n')[0].strip() if text else ""

def generate_barcode_image(borrow_code):
    try:
        buffer = BytesIO()
        Code128(borrow_code, writer=ImageWriter()).write(buffer)
        return buffer
    except Exception as e:
        print(f"Error generating barcode: {e}")
        return None

def generate_pdf_receipt(details, barcode_buffer):
    try:
        # --- START FIX ---
        # 1. Dùng Pillow để mở và chuẩn hóa dữ liệu ảnh từ buffer
        barcode_buffer.seek(0)
        img = Image.open(barcode_buffer)

        # 2. Tạo một buffer mới và lưu ảnh đã chuẩn hóa vào đó
        clean_image_buffer = BytesIO()
        img.save(clean_image_buffer, format="PNG")
        clean_image_buffer.seek(0)
        # --- END FIX ---

        pdf = FPDF()
        pdf.add_page()
        pdf.add_font('BeVietnamPro', '', 'fonts/BeVietnamPro-Regular.ttf', uni=True)
        pdf.add_font('BeVietnamPro', 'B', 'fonts/BeVietnamPro-Bold.ttf', uni=True)

        pdf.set_font('BeVietnamPro', 'B', 16)
        pdf.cell(0, 10, 'PHIẾU MƯỢN SÁCH - Thư viện LibraNCT', 0, 1, 'C')
        pdf.ln(10)

        pdf.set_font('BeVietnamPro', '', 12)
        pdf.cell(0, 8, f"Tên sách: {details['book_title']}", 0, 1)
        pdf.cell(0, 8, f"Học sinh: {details['student_name']} - Lớp: {details['student_class']}", 0, 1)
        pdf.cell(0, 8, f"Ngày mượn: {details['borrow_date']}", 0, 1)
        pdf.set_font('BeVietnamPro', 'B', 12)
        pdf.cell(0, 8, f"Hạn trả: {details['return_date']}", 0, 1)
        pdf.ln(5)

        # Sử dụng buffer đã được làm sạch và chuẩn hóa
        pdf.image(clean_image_buffer, x=70, y=pdf.get_y(), w=70, type='PNG')
        pdf.ln(25)

        pdf.set_font('BeVietnamPro', '', 10)
        pdf.cell(0, 8, 'Vui lòng đưa phiếu này cho thủ thư để nhận sách.', 0, 1, 'C')
        pdf.cell(0, 8, 'Cảm ơn bạn đã sử dụng dịch vụ của LibraNCT!', 0, 1, 'C')

        pdf_output_bytes = pdf.output(dest='S')
        pdf_base64 = base64.b64encode(pdf_output_bytes).decode('utf-8')
        return pdf_base64

    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None


def send_borrow_confirmation_email(recipients, details, pdf_base64):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = f"Xác nhận mượn sách thành công - Mã: {details['borrow_code']}"

        body = f"""
        <html><body>
            <h2>Chào {details['student_name']},</h2>
            <p>Bạn đã mượn thành công cuốn sách <b>{details['book_title']}</b>.</p>
            <p>Mã mượn sách của bạn là: <b>{details['borrow_code']}</b></p>
            <p>Vui lòng trả sách trước hoặc trong ngày: <b>{details['return_date']}</b>.</p>
            <p>Phiếu mượn sách chi tiết đã được đính kèm trong email này.</p>
            <br>
            <p>Cảm ơn bạn,</p>
            <p><b>Thư viện LibraNCT</b></p>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))

        pdf_attachment = MIMEApplication(base64.b64decode(pdf_base64), _subtype="pdf")
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=f"phieu-muon-{details['borrow_code']}.pdf")
        msg.attach(pdf_attachment)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send confirmation email: {e}")
        return False

