"""Plain-text Zalo copy. No invented fields or unsupported rich-text syntax."""


def currency(value):
    return f'{value:,}'.replace(',', '.')+' đ' if value is not None else 'Chưa cung cấp'


def fields(row):
    return (f"Tên món: {row.get('title') or 'Chưa cung cấp'}\n"
            f"Giá: {currency(row.get('price_vnd'))}\n"
            f"Tình trạng: {row.get('condition') or 'Chưa cung cấp'}")


def item_message(row, status, heading='🛍 Thông tin món đồ'):
    return f"{heading}\n\n{fields(row)}\nTrạng thái: {status}\n\nMã món đồ:\n{row['id']}"


def draft_message(row, missing=None, question=None):
    text=item_message(row,'Bản nháp — chưa gửi duyệt','📝 Thông tin đăng bán')
    if missing:
        return text+f'\n\nThông tin cần bổ sung:\n{question}'
    return text+'\n\nBạn kiểm tra thông tin trước khi gửi.\n• Gửi BQL duyệt: nhắn xác nhận\n• Bỏ bản nháp: nhắn hủy nháp'


def pending_message(row):
    return item_message(row,'Chờ BQL duyệt','✅ Đã gửi tin cho BQL')+'\n\nTin chỉ xuất hiện trong tìm kiếm sau khi được duyệt.'


def sold_message(row, group=False):
    heading='✅ ĐÃ BÁN' if group else '✅ Đã ghi nhận bán xong'
    return item_message(row,'Đã bán',heading)+'\n\nMón này đã ngừng xuất hiện trong tìm kiếm. Vui lòng không gửi yêu cầu mua cho món này.'


def search_message(rows):
    if not rows:
        return '🔎 Kết quả tìm kiếm\n\nChưa có tin phù hợp đã được duyệt và còn bán.\n\nBạn thử từ khóa ngắn gọn hơn, ví dụ:\ntìm ghế'
    blocks=[]
    for row in rows:
        block=f"{len(blocks)+1}. {row['title']}\nGiá: {currency(row['price_vnd'])}\nTình trạng: {row['condition']}\nMã món đồ:\n{row['id']}"
        if blocks and len('\n\n'.join(blocks+[block]))>1650:
            break
        blocks.append(block)
    return f"🔎 Món phù hợp ({len(blocks)} kết quả)\n\n"+'\n\n'.join(blocks)+'\n\nXem chi tiết và kiểm tra còn bán:\nSao chép một mã ở trên rồi gửi lại cho Meo Meo.'


def image_message(code, status):
    labels={'clear':'Chưa phát hiện nội dung bị gắn cờ', 'flagged':'Cần BQL xem xét nội dung',
            'unavailable':'Chưa kiểm tra tự động được', 'error':'Kiểm tra tự động chưa thành công',
            'pending':'Đang kiểm tra', 'stale':'Mô tả đã thay đổi; cần kiểm tra lại'}
    return (f"📷 Đã lưu ảnh vào bản nháp\n\nMã món đồ:\n{code}\n\n"
            f"Kiểm duyệt an toàn: {labels.get(status,'Cần BQL kiểm tra')}\n"
            "BQL vẫn cần xem và duyệt tin trước khi đăng.\n\n"
            "Bước tiếp theo:\n• Bổ sung thông tin nếu bot đang hỏi thêm.\n• Nếu bản nháp đầy đủ, nhắn xác nhận.")


def help_message(natural=True):
    example='Mình muốn thanh lý ghế 500k, dùng 6 tháng.' if natural else 'ban Ghế | 500000 | Đã dùng 6 tháng'
    return ('👋 Meo Meo — Trợ lý chợ cư dân\n\n'
            f'Đăng bán:\n{example}\n\n'
            'Tìm mua:\ntìm ghế\n\n'
            'Xem một món:\nGửi mã NM-…\n\n'
            'Gửi bản nháp cho BQL:\nxác nhận\n\n'
            'Báo bán xong:\nđã bán MÃ_TIN\n\n'
            'Bỏ bản nháp đang mở:\nhủy nháp')


def group_message(row):
    return ('🛍 TIN ĐÃ ĐƯỢC BQL DUYỆT\n\n'+fields(row)+
            f"\nTrạng thái: Đang bán\n\n🔖 MÃ MÓN ĐỒ\n━━━━━━━━━━━━━━━━\n{row['id']}\n━━━━━━━━━━━━━━━━\n\n"
            'Xem chi tiết và kiểm tra còn bán:\nSao chép mã rồi nhắn riêng Meo Meo.\n\n'
            'Mã được gửi thêm trong một tin riêng để dễ sao chép. Không chuyển tiền chỉ dựa vào bài đăng.')


def error_message(message):
    return '⚠ Chưa thực hiện được\n\n'+message
