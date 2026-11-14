"""Compact Vietnamese copy adapted from main messages.py; no invented status."""


def currency(value: int) -> str:
    return f'{value:,}'.replace(',','.')+'đ'


def item_message(row, status: str) -> str:
    return (f"Sản phẩm: {row['title']}\nGiá: {currency(row['price_vnd'])}\n"
            f"Tình trạng: {row['condition']}\nTrạng thái: {status}\n\nMã tin: {row['id']}")


def draft_message(row) -> str:
    return (f"Dạ, mình đã soạn bản nháp {row['id']}.\n"
            f"{row['title']} · {currency(row['price_vnd'])}\n"
            f"Tình trạng: {row['condition']}\n"
            "Bạn có thể gửi ảnh rồi nhắn xác nhận để gửi BQL ạ.")


def transition_message(row, status: str) -> str:
    if status=='pending':
        return f"Dạ, tin {row['id']} đang chờ BQL duyệt."
    return f"Dạ, tin {row['id']} đã được đánh dấu đã bán."


def search_message(rows) -> str:
    if not rows: return 'Dạ, chưa có món phù hợp. Bạn thử từ khóa ngắn hơn nhé.'
    items = [f"{row['title']} · {currency(row['price_vnd'])} · {row['id']}" for row in rows]
    return 'Dạ, mình tìm được:\n' + '\n'.join(items) + '\nNhắn mã tin để xem chi tiết ạ.'
