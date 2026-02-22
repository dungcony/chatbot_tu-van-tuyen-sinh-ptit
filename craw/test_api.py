import time
from google import genai

# Khởi tạo client với API Key của bạn
client = genai.Client(api_key="AIzaSyB4yn9gUK3QcPc_K2XWK6DE2ZJSkuQ1eCw")

# SỬA LỖI 404 Ở ĐÂY: Dùng model chuẩn, ổn định nhất hiện tại thay vì bản preview
MODEL_ID = "gemini-2.5-flash-lite"

for m in client.models.list():
    print("-", m.name)
    
print("="*50)
print("BƯỚC 1: KIỂM TRA LỖI 404 (SAI TÊN MODEL HOẶC KEY)")
print("="*50)
try:
    response = client.models.generate_content(
        model=MODEL_ID,
        contents="Xin chào, trả lời tôi bằng 1 câu ngắn gọn nhé."
    )
    print("✅ BƯỚC 1 THÀNH CÔNG! API Key hợp lệ và Model tồn tại.")
    print("🤖 Bot trả lời:", response.text.strip())
except Exception as e:
    print("❌ BƯỚC 1 THẤT BẠI. Chi tiết lỗi:")
    print(e)
    print("\n=> CHUẨN ĐOÁN: Nếu bạn thấy lỗi 404, tức là tên Model bị sai. Nếu lỗi 401, tức là API Key chưa đúng.")
    exit() # Dừng chương trình luôn nếu lỗi ở đây


print("\n" + "="*50)
print("BƯỚC 2: KIỂM TRA LỖI 429 (QUÁ TẢI QUOTA / RATE LIMIT)")
print("="*50)
print("Bắt đầu gửi 5 request liên tục...")
print("Danh sách các model khả dụng:")

for i in range(1, 6):
    print(f"\n[Request {i}] Đang gửi lên server...")
    try:
        start_time = time.time()
        
        res = client.models.generate_content(
            model=MODEL_ID,
            contents=f"Kể tên 1 loại quả bắt đầu bằng chữ cái ngẫu nhiên. (Lần {i})"
        )
        
        elapsed_time = time.time() - start_time
        print(f"✅ Thành công (Mất {elapsed_time:.2f} giây): {res.text.strip()}")
        
        # --- BỘ PHANH HÃM (CHỐNG LỖI 429) ---
        # Hãy thử comment (thêm dấu # ở đầu) dòng time.sleep(4) dưới đây. 
        # Nếu không có dòng này, code chạy vèo vèo và bạn sẽ lập tức ăn lỗi 429.
        print("⏳ Đang nghỉ 4 giây để chống lỗi Rate Limit...")
        time.sleep(4)

    except Exception as e:
        print(f"❌ THẤT BẠI ở Request thứ {i}:")
        print(e)
        print("\n=> CHUẨN ĐOÁN: Lỗi 429 Too Many Requests! Bạn đã gọi API quá nhanh. Hãy mở lại dòng time.sleep(4) nhé.")
        break