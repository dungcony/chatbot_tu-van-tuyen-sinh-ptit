import unicodedata
import re
from thefuzz import process, fuzz

# 1. Hàm chuẩn hóa văn bản (xóa dấu tiếng Việt, xử lý chữ kéo dài)
def normalize_text(text):
    text = text.lower()
    # Chuẩn hóa Unicode NFD để tách các dấu thanh ra khỏi chữ cái
    text = unicodedata.normalize('NFD', text)
    # Xóa các ký tự dấu (combining characters)
    text = re.sub(r'[\u0300-\u036f]', '', text)
    # Xử lý chữ 'đ'
    text = text.replace('đ', 'd')
    
    # [MỚI] Thu gọn chữ lặp lại nhiều lần (ví dụ: okkkkk -> ok)
    # Tìm các ký tự lặp lại từ 3 lần trở lên và thay bằng 1 ký tự 
    # (Dùng 3 lần để tránh ảnh hưởng các chữ vốn có 2 âm tiết lặp như "hello")
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    
    # Loại bỏ khoảng trắng thừa
    text = " ".join(text.split())
    return text

# 2. Tập từ khóa - Dạng List để thư viện thefuzz xử lý mượt hơn

GREETINGS = [
    "xin chao", "hello", "hi", "chao", "hey", "alo", "helo", "hellu",
    "chao ban", "chao shop", "chao ad", "eii", "admin oi", "shop oi"
]

CONFIRMS = [
    "co", "co a", "dung", "dung roi", "ok", "ok em", "yes", "vang", "vang a",
    "uh", "uhm", "muon", "dong y", "duoc", "oke", "okie", "oki", "okela",
    "dc", "uk", "ukm", "um", "chot", "trien", "duyet", "da", "da co",
    "da vang", "chinh xac", "chuan"
]
# "chuan" (chuẩn): với fuzz.ratio, "chuẩn"→100%, "điểm chuẩn"→~50% (chuỗi dài hơn)

NONSENSE = [
    "asdf", "qwerty", "hjkl", "abc", "xyz", "fgh", "asd", "zxc",
    "haha", "hihi", "kaka", "hoho", "huhu", "hehe", "keke",
    "lol", "lmao", "bruh", "wtf", "omg", "dkm", "vl", "dm",
    "ahihi", "kakaka", "hahaha", "hihihi", "hehehehe",
    "test", "testing", "thu", "thu xem", "thu thoi",
    "hmm", "zzz", "...", "???", "!!!",
    "aaa", "bbb", "ccc", "ddd", "eee", "fff",
    "123", "1234", "blah", "blah blah", "giberish",
    "abc xyz", "nothing", "khong biet", "gi do",
    "dsadsa", "fdsf", "ghfgh", "jkljkl", "tyuty",
]

# Từ khóa câu hỏi: nếu có → UNKNOWN (tránh "chỉ có 3 ngành thôi à" match "thu thoi" trong NONSENSE)
QUESTION_HINTS = ["nganh", "ngành", "diem", "điểm", "chi tieu", "hoc phi", "truong", "trường"]

# 3. Hàm kiểm tra ý định (Intent) của người dùng - Dùng thefuzz
def check_intent(user_message):
    """
    Phân loại intent của user bằng thefuzz:
      - GREETING: Chào hỏi
      - CONFIRM: Xác nhận (có, đúng, ok...) - dùng ratio (so toàn câu), không partial
      - NONSENSE: Câu vô nghĩa / spam / test (asdf, haha, lol...)
      - UNKNOWN: Câu hỏi thật sự → chuyển vào RAG pipeline
    """
    normalized_msg = normalize_text(user_message)

    # Chứa từ khóa câu hỏi → UNKNOWN (vd: "chỉ có 3 ngành thôi à" có "ngành")
    for kw in QUESTION_HINTS:
        if kw in normalized_msg:
            print(f"[INTENT] '{user_message}' -> UNKNOWN (có từ khóa: {kw})")
            return "UNKNOWN"

    # Câu quá ngắn (1-2 ký tự) → nonsense
    if len(normalized_msg.strip()) <= 1:
        print(f"[INTENT] '{user_message}' -> NONSENSE (quá ngắn)")
        return "NONSENSE"
    
    # Tìm từ giống nhất trong từng danh sách
    best_greeting, greeting_score = process.extractOne(normalized_msg, GREETINGS)
    # CONFIRM: dùng ratio (so toàn câu) - "điểm chuẩn" không match "co"/"dung"
    best_confirm, confirm_score = process.extractOne(normalized_msg, CONFIRMS, scorer=fuzz.ratio)
    best_nonsense, nonsense_score = process.extractOne(normalized_msg, NONSENSE)
    
    print(f"[INTENT] '{user_message}' -> Chuẩn hóa: '{normalized_msg}'")
    print(f"   => GREETING : '{best_greeting}' ({greeting_score}%)")
    print(f"   => CONFIRM  : '{best_confirm}' ({confirm_score}%)")
    print(f"   => NONSENSE : '{best_nonsense}' ({nonsense_score}%)")
    
    # Ngưỡng chấp nhận (Threshold)
    THRESHOLD = 80
    NONSENSE_THRESHOLD = 85  # Cao hơn để tránh false positive
    
    # Ưu tiên: Greeting > Confirm > Nonsense
    if greeting_score >= THRESHOLD and greeting_score >= confirm_score and greeting_score >= nonsense_score:
        return "GREETING"
    elif confirm_score >= THRESHOLD and confirm_score >= nonsense_score:
        return "CONFIRM"
    elif nonsense_score >= NONSENSE_THRESHOLD:
        return "NONSENSE"
    
    # Kiểm tra thêm: Chuỗi toàn ký tự đặc biệt / số
    if re.match(r'^[\W\d\s]+$', normalized_msg):
        print(f"   => NONSENSE (toàn ký tự đặc biệt/số)")
        return "NONSENSE"
    
    return "UNKNOWN"