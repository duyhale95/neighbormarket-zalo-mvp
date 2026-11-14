"""Compact Vietnamese copy adapted from main messages.py; no invented status."""


def currency(value: int) -> str:
    return f'{value:,}'.replace(',','.')+'đ'


def item_message(row, status: str) -> str:
    return (f"Sản phẩm: {row['title']}\nGiá: {currency(row['price_vnd'])}\n"
            f"Tình trạng: {row['condition']}\nTrạng thái: {status}\n\nMã tin: {row['id']}")


def draft_message(row) -> str:
    return f"Bản nháp {row['id']}:\n\n"+item_message(row,'Bản nháp — chưa gửi duyệt')+'\n\nNhắn xác nhận hoặc ok để gửi BQL. Sửa giá, sửa tiêu đề hoặc hủy nháp trước khi xác nhận.'


def transition_message(row, status: str) -> str:
    if status=='pending':
        return item_message(row,'Chờ BQL duyệt')+'\n\nBQL phải duyệt trước khi tin vào hàng chờ xuất bản. Chưa đăng lên nhóm.'
    return item_message(row,'Đã bán')+'\n\nTin đã ngừng xuất hiện trong tìm kiếm. Nếu bài gốc có receipt, thông báo đã bán được đưa vào outbox; chưa phải xác nhận gửi nhóm.'


def search_message(rows) -> str:
    if not rows: return 'Chưa có tin phù hợp đã được duyệt và còn bán. Thử từ khóa ngắn hơn, ví dụ: tìm ghế.'
    return '\n\n'.join(item_message(row,'Đã được BQL duyệt · kiểm tra còn bán trước khi giao dịch') for row in rows)+'\n\nGửi lại một mã tin để xem chi tiết. Trạng thái duyệt không đồng nghĩa đã đăng nhóm.'
