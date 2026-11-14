import unittest
from backend.messages import draft_message, search_message, item_message, image_message, currency


class MessageTests(unittest.TestCase):
    def setUp(self):
        self.item=dict(id='NM-EXAMPLE',title='Ghế làm việc',price_vnd=500000,condition='Dùng 6 tháng, không hỏng')
    def test_draft_has_complete_fields_and_one_clear_next_action(self):
        text=draft_message(self.item)
        for field in ['Tên món: Ghế làm việc','Giá: 500.000 đ','Tình trạng: Dùng 6 tháng, không hỏng','Mã món đồ:\nNM-EXAMPLE','xác nhận']:
            self.assertIn(field,text)
        self.assertNotIn('**',text)
        self.assertEqual(currency(0),'0 đ')
    def test_search_separates_items_and_uses_actual_codes(self):
        other={**self.item,'id':'NM-OTHER','title':'Bàn học'}
        text=search_message([self.item,other])
        self.assertIn('1. Ghế làm việc',text);self.assertIn('2. Bàn học',text)
        self.assertIn('\n\n2.',text)
        self.assertIn('NM-EXAMPLE',text);self.assertIn('NM-OTHER',text)
        self.assertIn('Tình trạng:',text)
    def test_long_results_keep_complete_cards_in_message_budget(self):
        rows=[{**self.item,'id':f'NM-{i}','title':'A'*250,'condition':'B'*500} for i in range(5)]
        text=search_message(rows)
        self.assertLessEqual(len(text),2000)
        self.assertIn('B'*500,text)
    def test_image_reply_is_not_an_authenticity_claim(self):
        text=image_message('NM-EXAMPLE','clear')
        self.assertIn('Mã món đồ:\nNM-EXAMPLE',text)
        self.assertIn('Chưa phát hiện',text)
        self.assertNotIn('ảnh thật',text.lower())
        self.assertIn('BQL',image_message('NM-EXAMPLE','flagged'))
    def test_lookup_has_status_and_no_invented_fields(self):
        text=item_message(self.item,'Đang bán')
        self.assertIn('Trạng thái: Đang bán',text)
        self.assertNotIn('Thương hiệu',text)
