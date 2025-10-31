import os
import json
import uuid
import base64 
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import services
import firebase_admin
from firebase_admin import credentials, auth
from functools import wraps

# --- Firebase Admin Initialization ---
# IMPORTANT: Create a 'serviceAccountKey.json' file in your project root
# and add its path to your .env file as FIREBASE_SERVICE_ACCOUNT_KEY_PATH
load_dotenv()
try:
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH")
    cred_json_env = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_JSON")

    if cred_json_env:
        # Prefer JSON from env if provided (Render-friendly, no files committed)
        try:
            service_account_info = json.loads(cred_json_env)
        except json.JSONDecodeError:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_KEY_JSON is not valid JSON")
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT_KEY_JSON.")
    elif cred_path:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT_KEY_PATH.")
    else:
        raise ValueError("Set FIREBASE_SERVICE_ACCOUNT_KEY_JSON or FIREBASE_SERVICE_ACCOUNT_KEY_PATH in environment")
except Exception as e:
    print(f"CRITICAL: Failed to initialize Firebase Admin SDK. Admin features will not work. Error: {e}")

if os.getenv("CLOUDINARY_CLOUD_NAME"):
    print(".env file loaded successfully.")
    services.configure_cloudinary()
else:
    print("WARNING: .env file not loaded or variables are missing.")

app = Flask(__name__)

# --- Data directory (supports Render Disk via DATA_DIR) ---
BASE_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))

def _data_path(filename: str) -> str:
    return os.path.join(BASE_DIR, filename)

# Cấu hình CORS bảo mật hơn (đã hỗ trợ frontend domain)
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
CORS(
    app,
    supports_credentials=True,
    resources={r"/*": {"origins": ALLOWED_ORIGINS}},
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)


# --- Authentication Decorator ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"status": "error", "message": "Missing or invalid Authorization header."}), 401
        
        id_token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = auth.verify_id_token(id_token)
            email = decoded_token.get('email')
            
            # --- The core security check ---
            # Cho phép cấu hình nhiều email admin qua biến môi trường ADMIN_EMAILS
            admin_emails_env = os.getenv('ADMIN_EMAILS', 'admin@libranct.us.to')
            admin_emails = {e.strip().lower() for e in admin_emails_env.split(',') if e.strip()}

            if not email or email.lower() not in admin_emails:
                return jsonify({"status": "error", "message": "Admin privileges required."}), 403
            
        except auth.InvalidIdTokenError:
            return jsonify({"status": "error", "message": "Invalid ID token."}), 403
        except Exception as e:
            return jsonify({"status": "error", "message": f"Token verification failed: {str(e)}"}), 401
        
        return f(*args, **kwargs)
    return decorated_function

# --- Database Helper Functions ---
def read_json_db(filepath):
    try:
        with open(_data_path(filepath), 'r', encoding='utf-8') as f:
            content = f.read()
            if not content: return []
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def write_json_db(filepath, data):
    os.makedirs(os.path.dirname(_data_path(filepath)), exist_ok=True) if os.path.dirname(_data_path(filepath)) else None
    with open(_data_path(filepath), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- USER-FACING API ROUTES ---

@app.route('/dashboard-data/<email>', methods=['GET'])
def get_dashboard_data(email):
    if not email:
        return jsonify({"status": "error", "message": "Email is required"}), 400
    try:
        borrowers = read_json_db('borrowers.json')
        user_borrows = [b for b in borrowers if b.get('original_email') == email]
        books_db = read_json_db('database.json')
        borrowed_books_list = []
        due_soon_books_list = []
        today = datetime.now().date()
        for borrow_record in user_borrows:
            book_info = next((book for book in books_db if book['book_id'] == borrow_record['book_id']), None)
            if book_info and book_info.get('is_borrowed'):
                return_date_str = book_info.get('return_date')
                borrowed_books_list.append({"book_title": borrow_record['book_title'], "return_date": return_date_str})
                if return_date_str:
                    return_date = datetime.strptime(return_date_str, '%d/%m/%Y').date()
                    days_left = (return_date - today).days
                    if 0 <= days_left <= 3:
                        due_soon_books_list.append({"title": borrow_record['book_title'], "days_left": days_left})
        due_soon_books_list.sort(key=lambda x: x['days_left'])
        borrowed_ids = {b['book_id'] for b in user_borrows}
        recommendations_list = [book for book in books_db if book['book_id'] not in borrowed_ids and not book.get('is_borrowed')][:6]
        return jsonify({
            "status": "success", "borrowed_books": borrowed_books_list,
            "due_soon_books": due_soon_books_list, "recommendations": recommendations_list
        })
    except Exception as e:
        print(f"Error fetching dashboard data for {email}: {e}")
        return jsonify({"status": "error", "message": f"Could not fetch dashboard information: {str(e)}"}), 500

@app.route('/search-books', methods=['GET'])
def search_books():
    query = request.args.get('q', '').lower()
    books_db = read_json_db('database.json')
    results = [{"id": book["book_id"], "title": book["book_name"], "quantity": book["quantity"], "status": "Hết sách" if book["is_borrowed"] or book["quantity"] == 0 else "Có sẵn"} for book in books_db if query in book["book_name"].lower() or query in book["book_id"].lower()]
    return jsonify(results)

@app.route('/ocr-book-cover', methods=['POST'])
def ocr_book_cover():
    data = request.json
    if not data or 'image_data' not in data:
        return jsonify({"status": "error", "message": "No image data."}), 400
    try:
        text = services.process_ocr_for_text(data['image_data'])
        return jsonify({"status": "success", "text": text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/generate-cloudinary-signature', methods=['GET'])
def get_cloudinary_signature():
    try:
        result = services.generate_cloudinary_signature()
        if result:
            return jsonify({"status": "success", "signature": result["signature"], "timestamp": result["timestamp"], "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME"), "api_key": os.getenv("CLOUDINARY_API_KEY")})
        else:
            raise Exception("Signature generation failed.")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/process-borrow-request', methods=['POST'])
def process_borrow_request():
    data = request.json
    book_info, form_info, user_email = data.get('book'), data.get('form'), data.get('userEmail')
    try:
        books_db = read_json_db('database.json')
        book_to_update = next((book for book in books_db if book['book_id'] == book_info['id'] and not book.get('is_borrowed')), None)
        if not book_to_update:
            return jsonify({"status": "error", "message": "Sách không có sẵn hoặc đã được mượn."}), 409
        
        duration_days = int(form_info.get('borrow_duration', 7))
        return_date = datetime.now() + timedelta(days=duration_days)
        if return_date.weekday() == 5: return_date -= timedelta(days=1)
        elif return_date.weekday() == 6: return_date += timedelta(days=1)
        book_to_update['is_borrowed'] = True
        book_to_update['return_date'] = return_date.strftime('%d/%m/%Y')
        write_json_db('database.json', books_db)

        borrow_code = f"M{datetime.now().strftime('%y%m%d%H%M%S')}"
        borrowers_db = read_json_db('borrowers.json')
        new_borrower = {
            "borrow_code": borrow_code, "book_id": book_info['id'], "book_title": book_info['title'],
            "student_name": form_info.get('name'), "student_class": form_info.get('class'),
            "contact_email": form_info.get('email'), "original_email": user_email,
            "library_card_url": form_info.get('library_card_url'),
            "borrow_date": datetime.now().strftime('%d/%m/%Y'), "return_date": book_to_update['return_date']
        }
        borrowers_db.append(new_borrower)
        write_json_db('borrowers.json', borrowers_db)
        
        email_details = {'borrow_code': borrow_code, 'book_title': book_info['title'], 'student_name': form_info.get('name'), 'student_class': form_info.get('class'), 'borrow_date': datetime.now().strftime('%d/%m/%Y'), 'return_date': book_to_update['return_date']}
        barcode_buffer = services.generate_barcode_image(borrow_code)
        pdf_base64 = services.generate_pdf_receipt(email_details, barcode_buffer)
        recipients = [user_email, form_info.get('email')]
        services.send_borrow_confirmation_email(list(set(recipients)), email_details, pdf_base64)
        return jsonify({"status": "success", "message": "Borrow request processed and email sent successfully."})
    except Exception as e:
        print(f"Lỗi trong quá trình xử lý mượn sách: {e}")
        return jsonify({"status": "error", "message": f"Server error: {e}"}), 500

@app.route('/user-borrowed-books', methods=['GET'])
def get_user_borrowed_books():
    user_email = request.args.get('email')
    if not user_email: return jsonify({"error": "Email is required"}), 400
    try:
        borrowers, books_db = read_json_db('borrowers.json'), read_json_db('database.json')
        user_borrow_records = [b for b in borrowers if b.get('original_email') == user_email]
        user_borrowed_list = []
        for record in user_borrow_records:
            book_info = next((book for book in books_db if book['book_id'] == record['book_id']), None)
            if book_info and book_info.get('is_borrowed'):
                user_borrowed_list.append({"id": record['book_id'], "title": record['book_title'], "return_date": record.get('return_date')})
        return jsonify(user_borrowed_list)
    except Exception as e:
        print(f"Error fetching user borrowed books: {e}")
        return jsonify({"error": f"Could not fetch borrowed books: {e}"}), 500

@app.route('/process-return-request', methods=['POST'])
def process_return_request():
    data = request.json
    book_id = data.get('book_id')
    if not book_id: return jsonify({"status": "error", "message": "Book ID is required."}), 400
    try:
        books_db = read_json_db('database.json')
        book_to_return = next((book for book in books_db if book['book_id'] == book_id), None)
        if not book_to_return:
            return jsonify({"status": "error", "message": "Không tìm thấy sách với ID này."}), 404
        if not book_to_return.get('is_borrowed'):
            return jsonify({"status": "error", "message": "Sách này đã được trả."}), 409
        book_to_return['is_borrowed'] = False
        if 'return_date' in book_to_return:
            del book_to_return['return_date']
        write_json_db('database.json', books_db)
        return jsonify({"status": "success", "message": "Sách đã được trả thành công."})
    except Exception as e:
        print(f"Lỗi trong quá trình xử lý trả sách: {e}")
        return jsonify({"status": "error", "message": f"Server error: {e}"}), 500


# --- ADMIN API ROUTES (NOW SECURED) ---

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def get_admin_stats():
    books = read_json_db('database.json')
    borrowals = read_json_db('borrowers.json')
    total_books = len(books)
    borrowed_count = sum(1 for book in books if book.get('is_borrowed'))
    overdue_count = 0
    today = datetime.now().date()
    for book in books:
        if book.get('is_borrowed') and 'return_date' in book:
            try:
                return_date = datetime.strptime(book['return_date'], '%d/%m/%Y').date()
                if return_date < today:
                    overdue_count += 1
            except (ValueError, TypeError):
                continue
    recent_borrowals = sorted(borrowals, key=lambda x: x['borrow_code'], reverse=True)[:5]
    stats = {
        "total_books": total_books,
        "available_books": total_books - borrowed_count,
        "borrowed_books": borrowed_count,
        "overdue_count": overdue_count,
        "recent_borrowals": recent_borrowals
    }
    return jsonify(stats)

@app.route('/api/admin/all-books', methods=['GET'])
@admin_required
def get_all_books():
    books = read_json_db('database.json')
    return jsonify(books)

@app.route('/api/admin/all-borrowals', methods=['GET'])
@admin_required
def get_all_borrowals():
    borrowals = read_json_db('borrowers.json')
    books = read_json_db('database.json')
    books_dict = {book['book_id']: book for book in books}
    for b in borrowals:
        book_status = books_dict.get(b['book_id'], {})
        b['is_returned'] = not book_status.get('is_borrowed', True)
    return jsonify(borrowals)

@app.route('/api/admin/books/add', methods=['POST'])
@admin_required
def add_book():
    data = request.json
    if not data or 'book_name' not in data or 'quantity' not in data:
        return jsonify({"status": "error", "message": "Thiếu thông tin sách."}), 400
    books = read_json_db('database.json')
    new_book = {
        "book_id": f"B{int(datetime.now().timestamp())}",
        "book_name": data['book_name'],
        "author": data.get('author', 'Chưa rõ'),
        "quantity": int(data['quantity']),
        "is_borrowed": False
    }
    books.append(new_book)
    write_json_db('database.json', books)
    return jsonify({"status": "success", "message": "Sách đã được thêm thành công."})

@app.route('/api/admin/books/update', methods=['POST'])
@admin_required
def update_book():
    data = request.json
    book_id = data.get('book_id')
    if not book_id:
        return jsonify({"status": "error", "message": "Cần có ID sách."}), 400
    books = read_json_db('database.json')
    book_to_update = next((book for book in books if book['book_id'] == book_id), None)
    if not book_to_update:
        return jsonify({"status": "error", "message": "Không tìm thấy sách."}), 404
    book_to_update['book_name'] = data.get('book_name', book_to_update['book_name'])
    book_to_update['author'] = data.get('author', book_to_update['author'])
    book_to_update['quantity'] = int(data.get('quantity', book_to_update['quantity']))
    write_json_db('database.json', books)
    return jsonify({"status": "success", "message": "Sách đã được cập nhật."})

@app.route('/api/admin/books/delete', methods=['POST'])
@admin_required
def delete_book():
    data = request.json
    book_id = data.get('book_id')
    if not book_id:
        return jsonify({"status": "error", "message": "Cần có ID sách."}), 400
    books = read_json_db('database.json')
    book_to_delete = next((book for book in books if book['book_id'] == book_id), None)
    if not book_to_delete:
        return jsonify({"status": "error", "message": "Không tìm thấy sách."}), 404
    if book_to_delete.get('is_borrowed'):
        return jsonify({"status": "error", "message": "Không thể xóa sách đang được mượn."}), 409
    books = [book for book in books if book['book_id'] != book_id]
    write_json_db('database.json', books)
    return jsonify({"status": "success", "message": "Sách đã được xóa."})


if __name__ == '__main__':
    # Local/dev run: no SSL; Render terminates TLS at the edge
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '5001'))
    print(f"Starting server on http://{HOST}:{PORT} (TLS terminated by hosting provider if any)")
    app.run(host=HOST, port=PORT)
