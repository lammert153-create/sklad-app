import sqlite3
import os
from datetime import datetime
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.carousel import Carousel
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp

Window.softinput_mode = 'below_target'

# ==============================================================================
# 1. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И КОНСТАНТЫ
# ==============================================================================

def get_current_date_str():
    return datetime.now().strftime("%Y-%m-%d")

def num_to_words_ru(num):
    if num == 0:
        return "ноль"
    
    units = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
    teens = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", 
             "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
    tens = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
    hundreds = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]
    
    def _convert_thousands(n):
        res = []
        h, t, u = n // 100, (n % 100) // 10, n % 10
        if h > 0: res.append(hundreds[h])
        if t == 1: res.append(teens[u])
        else:
            if t > 1: res.append(tens[t])
            if u > 0: res.append("одна" if u == 1 else ("две" if u == 2 else units[u]))
        return " ".join(res)

    def _convert_simple(n):
        res = []
        h, t, u = n // 100, (n % 100) // 10, n % 10
        if h > 0: res.append(hundreds[h])
        if t == 1: res.append(teens[u])
        else:
            if t > 1: res.append(tens[t])
            if u > 0: res.append(units[u])
        return " ".join(res)

    parts = []
    millions = num // 1000000
    if millions > 0:
        m_str = _convert_simple(millions)
        m_last, m_last100 = millions % 10, millions % 100
        word = "миллионов" if m_last100 in [11, 12, 13, 14] else ("миллион" if m_last == 1 else ("миллиона" if m_last in [2, 3, 4] else "миллионов"))
        parts.append(f"{m_str} {word}")
    
    thousands = (num % 1000000) // 1000
    if thousands > 0:
        th_str = _convert_thousands(thousands)
        th_last, th_last100 = thousands % 10, thousands % 100
        word = "тысяч" if th_last100 in [11, 12, 13, 14] else ("тысяча" if th_last == 1 else ("тысячи" if th_last in [2, 3, 4] else "тысяч"))
        parts.append(f"{th_str} {word}")
        
    rest = num % 1000
    if rest > 0 or not parts:
        r_str = _convert_simple(rest)
        if r_str: parts.append(r_str)
            
    return " ".join(parts).strip()

def mass_to_words(kg, grams):
    kg_words = num_to_words_ru(int(kg))
    gr_words = num_to_words_ru(int(grams))
    return f"{kg} кг {grams} гр ({kg_words} килограммов {gr_words} граммов)"

def parse_bag_numbers(text):
    result = []
    for part in text.replace(' ', '').split(','):
        if not part: continue
        if '-' in part:
            sub = part.split('-')
            if len(sub) == 2 and sub[0].isdigit() and sub[1].isdigit():
                s, e = int(sub[0]), int(sub[1])
                if s <= e: result.extend(list(range(s, e + 1)))
        elif part.isdigit():
            result.append(int(part))
    return sorted(list(set(result)))

RECIPE = {
    'Лактозы моногидрат (Сахар молочный)': 350.0,
    'Маннитол': 100.0,
    'Глицин': 47.3,
    'Натрия сахаринат': 1.12,
    'Повидон (Повидон К25)': 10.0,
    'Натрий двууглекислый': 30.0,
    'Кислота лимонная': 23.0,
    'Ароматизатор мятный': 8.0,
    'Магния стеарат': 4.88
}

STD_25KG_RAW = [
    'Лактозы моногидрат (Сахар молочный)',
    'Маннитол',
    'Глицин',
    'Натрий двууглекислый'
]

# ==============================================================================
# 2. БАЗА ДАННЫХ SQLite
# ==============================================================================

class Database:
    def __init__(self, db_name="warehouse.db"):
        self.db_name = os.path.join(os.path.dirname(__file__), db_name)
        self.conn = sqlite3.connect(self.db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, raw_name TEXT, al_num TEXT,
            series_num TEXT, total_weight REAL, income_date TEXT, status TEXT DEFAULT 'В работе')''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS bags (
            id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER, bag_num INTEGER, weight REAL,
            FOREIGN KEY (batch_id) REFERENCES batches (id) ON DELETE CASCADE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS deductions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, raw_name TEXT, series_num TEXT, deduct_weight REAL, deduct_date TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS deducted_bags (
            id INTEGER PRIMARY KEY AUTOINCREMENT, deduction_id INTEGER, bag_num INTEGER,
            taken_weight REAL, remaining_in_bag REAL, is_transitional INTEGER DEFAULT 0,
            FOREIGN KEY (deduction_id) REFERENCES deductions (id) ON DELETE CASCADE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS income_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, raw_name TEXT, al_num TEXT,
            series_num TEXT, weight REAL, bags_str TEXT, income_date TEXT, batch_id INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS last_input_cache (
            key TEXT PRIMARY KEY, value TEXT)''')
        self.conn.commit()

    def get_cached_value_for_raw(self, raw_name, key_type, default=""):
        key = f"{key_type}_{raw_name}"
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM last_input_cache WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def save_cached_value_for_raw(self, raw_name, key_type, value):
        key = f"{key_type}_{raw_name}"
        cursor = self.conn.cursor()
        cursor.execute('''INSERT INTO last_input_cache (key, value) VALUES (?, ?)
                          ON CONFLICT(key) DO UPDATE SET value = excluded.value''', (key, value))
        self.conn.commit()

    def add_income(self, raw_name, al_num, series_num, income_weight, bag_numbers, income_date):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM batches WHERE raw_name = ? AND al_num = ? AND series_num = ?', (raw_name, al_num, series_num))
        existing = cursor.fetchone()

        if existing:
            batch_id = existing[0]
            cursor.execute('SELECT bag_num FROM bags WHERE batch_id = ?', (batch_id,))
            existing_bags = [row[0] for row in cursor.fetchall()]
            bags_to_add = [b for b in bag_numbers if b not in existing_bags]
        else:
            cursor.execute('INSERT INTO batches (raw_name, al_num, series_num, total_weight, income_date) VALUES (?, ?, ?, ?, ?)',
                           (raw_name, al_num, series_num, 0.0, income_date))
            batch_id = cursor.lastrowid
            bags_to_add = bag_numbers

        added_bags_list = []
        if bags_to_add:
            num_bags = len(bags_to_add)
            weights = []
            
            if raw_name in STD_25KG_RAW:
                rem_weight = income_weight
                for i in range(num_bags):
                    if i == num_bags - 1:
                        weights.append(round(rem_weight, 3))
                    else:
                        w = 25.0 if rem_weight >= 25.0 else round(rem_weight, 3)
                        weights.append(w)
                        rem_weight = max(0.0, rem_weight - w)
            else:
                rem_weight = income_weight
                base_w = round(income_weight / num_bags, 3)
                for i in range(num_bags):
                    if i == num_bags - 1:
                        weights.append(round(rem_weight, 3))
                    else:
                        weights.append(base_w)
                        rem_weight -= base_w

            for b_num, b_w in zip(bags_to_add, weights):
                cursor.execute('INSERT INTO bags (batch_id, bag_num, weight) VALUES (?, ?, ?)', (batch_id, b_num, b_w))
                added_bags_list.append(str(b_num))

        self.recalculate_batch_total_weight(batch_id)

        bags_str = ", ".join(added_bags_list) if added_bags_list else ", ".join(map(str, bag_numbers))
        cursor.execute('''INSERT INTO income_log (raw_name, al_num, series_num, weight, bags_str, income_date, batch_id)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (raw_name, al_num, series_num, income_weight, bags_str, income_date, batch_id))
        self.conn.commit()

    def add_single_bag(self, batch_id, bag_num, weight):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO bags (batch_id, bag_num, weight) VALUES (?, ?, ?)', (batch_id, bag_num, weight))
        self.conn.commit()
        self.recalculate_batch_total_weight(batch_id)

    def get_income_log(self, raw_name=None):
        cursor = self.conn.cursor()
        if raw_name:
            cursor.execute('SELECT id, raw_name, al_num, series_num, weight, bags_str, income_date, batch_id FROM income_log WHERE raw_name = ? ORDER BY id DESC', (raw_name,))
        else:
            cursor.execute('SELECT id, raw_name, al_num, series_num, weight, bags_str, income_date, batch_id FROM income_log ORDER BY id DESC')
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                'id': r[0], 'raw_name': r[1], 'al': r[2], 'series': r[3],
                'weight': r[4], 'bags_str': r[5], 'income_date': r[6], 'batch_id': r[7]
            })
        return result

    def update_income_log_date(self, log_id, new_date):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE income_log SET income_date = ? WHERE id = ?', (new_date, log_id))
        cursor.execute('SELECT batch_id FROM income_log WHERE id = ?', (log_id,))
        res = cursor.fetchone()
        if res and res[0]:
            cursor.execute('UPDATE batches SET income_date = ? WHERE id = ?', (new_date, res[0]))
        self.conn.commit()

    def delete_income_log_entry(self, log_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT batch_id, bags_str FROM income_log WHERE id = ?', (log_id,))
        res = cursor.fetchone()
        if res:
            batch_id, bags_str = res[0], res[1]
            if bags_str:
                bag_nums = parse_bag_numbers(bags_str)
                for b_num in bag_nums:
                    cursor.execute('DELETE FROM bags WHERE batch_id = ? AND bag_num = ?', (batch_id, b_num))
                self.recalculate_batch_total_weight(batch_id)
                cursor.execute('SELECT COUNT(*) FROM bags WHERE batch_id = ?', (batch_id,))
                if cursor.fetchone()[0] == 0:
                    self.delete_batch(batch_id)
        cursor.execute('DELETE FROM income_log WHERE id = ?', (log_id,))
        self.conn.commit()

    def recalculate_batch_total_weight(self, batch_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT SUM(weight) FROM bags WHERE batch_id = ?', (batch_id,))
        res = cursor.fetchone()[0]
        cursor.execute('UPDATE batches SET total_weight = ? WHERE id = ?', (res if res else 0.0, batch_id))
        self.conn.commit()

    def update_batch_header(self, batch_id, new_al, new_series, new_date):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE batches SET al_num = ?, series_num = ?, income_date = ? WHERE id = ?', (new_al, new_series, new_date, batch_id))
        self.conn.commit()

    def delete_bag(self, bag_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT batch_id FROM bags WHERE id = ?', (bag_id,))
        res = cursor.fetchone()
        batch_id = res[0] if res else None
        cursor.execute('DELETE FROM bags WHERE id = ?', (bag_id,))
        if batch_id:
            self.recalculate_batch_total_weight(batch_id)
            cursor.execute('SELECT COUNT(*) FROM bags WHERE batch_id = ?', (batch_id,))
            if cursor.fetchone()[0] == 0:
                self.delete_batch(batch_id)
        self.conn.commit()

    def delete_batch(self, batch_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM bags WHERE batch_id = ?', (batch_id,))
        cursor.execute('DELETE FROM batches WHERE id = ?', (batch_id,))
        self.conn.commit()

    def get_raw_batches(self, raw_name):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, al_num, series_num, total_weight, income_date, status FROM batches WHERE raw_name = ?', (raw_name,))
        batches = cursor.fetchall()
        result = []
        for b in batches:
            b_id, al, ser, total_w, inc_date, status = b
            cursor.execute('SELECT id, bag_num, weight FROM bags WHERE batch_id = ? ORDER BY bag_num', (b_id,))
            bags = cursor.fetchall()
            real_total = sum([bag[2] for bag in bags])
            result.append({'id': b_id, 'al': al, 'series': ser, 'total_weight': real_total, 'income_date': inc_date or 'Н/Д', 'status': status, 'bags': bags})
        return result

    def deduct_from_batch(self, batch_id, weight_to_deduct, deduct_date=None):
        if not deduct_date: deduct_date = get_current_date_str()
        cursor = self.conn.cursor()
        cursor.execute('SELECT raw_name, series_num FROM batches WHERE id = ?', (batch_id,))
        b_info = cursor.fetchone()
        if not b_info: return
        raw_name, series_num = b_info[0], b_info[1]

        cursor.execute('INSERT INTO deductions (raw_name, series_num, deduct_weight, deduct_date) VALUES (?, ?, ?, ?)',
                       (raw_name, series_num, weight_to_deduct, deduct_date))
        deduction_id = cursor.lastrowid

        cursor.execute('SELECT id, bag_num, weight FROM bags WHERE batch_id = ? ORDER BY bag_num', (batch_id,))
        bags = cursor.fetchall()
        remains = weight_to_deduct

        for bag_db_id, bag_num, bag_w in bags:
            if remains <= 1e-6: break
            if bag_w <= remains + 1e-6:
                taken = bag_w
                remains -= bag_w
                cursor.execute('DELETE FROM bags WHERE id = ?', (bag_db_id,))
                cursor.execute('INSERT INTO deducted_bags (deduction_id, bag_num, taken_weight, remaining_in_bag, is_transitional) VALUES (?, ?, ?, 0.0, 0)',
                               (deduction_id, bag_num, taken))
            else:
                taken = remains
                rem_in_bag = round(bag_w - remains, 3)
                remains = 0
                cursor.execute('UPDATE bags SET weight = ? WHERE id = ?', (rem_in_bag, bag_db_id))
                cursor.execute('INSERT INTO deducted_bags (deduction_id, bag_num, taken_weight, remaining_in_bag, is_transitional) VALUES (?, ?, ?, ?, 1)',
                               (deduction_id, bag_num, taken, rem_in_bag))

        self.recalculate_batch_total_weight(batch_id)
        cursor.execute('SELECT COUNT(*) FROM bags WHERE batch_id = ?', (batch_id,))
        if cursor.fetchone()[0] == 0:
            self.delete_batch(batch_id)

    def deduct_raw_fifo(self, raw_name, weight_needed, deduct_date=None):
        if not deduct_date: deduct_date = get_current_date_str()
        batches = self.get_raw_batches(raw_name)
        total_avail = sum([b['total_weight'] for b in batches])
        if total_avail < weight_needed - 1e-6:
            return False, total_avail

        remains = weight_needed
        for b in batches:
            if remains <= 1e-6: break
            to_ded = min(remains, b['total_weight'])
            self.deduct_from_batch(b['id'], to_ded, deduct_date)
            remains -= to_ded
        return True, 0

    def get_monthly_deductions_detailed(self, raw_name):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, series_num, deduct_weight, deduct_date FROM deductions WHERE raw_name = ? ORDER BY id DESC', (raw_name,))
        deductions = cursor.fetchall()
        result = []
        for d in deductions:
            d_id, d_ser, d_w, d_date = d
            cursor.execute('SELECT bag_num, taken_weight, remaining_in_bag, is_transitional FROM deducted_bags WHERE deduction_id = ? ORDER BY bag_num', (d_id,))
            bags_detail = cursor.fetchall()
            result.append({
                'id': d_id, 'series': d_ser, 'weight': d_w, 'date': d_date,
                'fully_removed_bags': [str(b[0]) for b in bags_detail if b[3] == 0],
                'transitional_bag': [b for b in bags_detail if b[3] == 1][0] if [b for b in bags_detail if b[3] == 1] else None
            })
        return result

    def update_deduction_date(self, deduction_id, new_date):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE deductions SET deduct_date = ? WHERE id = ?', (new_date, deduction_id))
        self.conn.commit()

    def delete_single_deduction(self, deduct_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM deducted_bags WHERE deduction_id = ?', (deduct_id,))
        cursor.execute('DELETE FROM deductions WHERE id = ?', (deduct_id,))
        self.conn.commit()

    def clear_all_deductions(self):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM deducted_bags')
        cursor.execute('DELETE FROM deductions')
        self.conn.commit()

# ==============================================================================
# 3. ИНТЕРФЕЙС KIVY UI
# ==============================================================================

class RawCard(BoxLayout):
    def __init__(self, raw_name, db, **kwargs):
        super().__init__(orientation='vertical', padding=10, spacing=10, **kwargs)
        self.raw_name = raw_name
        self.db = db
        self.scroll = ScrollView(size_hint=(1, 1))
        self.content_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        self.content_layout.bind(minimum_height=self.content_layout.setter('height'))
        self.scroll.add_widget(self.content_layout)
        self.add_widget(self.scroll)
        self.refresh_card()

    def refresh_card(self):
        self.content_layout.clear_widgets()
        norm = RECIPE[self.raw_name]
        batches = self.db.get_raw_batches(self.raw_name)
        total_w = sum([b['total_weight'] for b in batches])
        kg = int(total_w)
        gr = int(round((total_w - kg) * 1000))

        lbl_title = Label(
            text=f"[size=20sp][b]{self.raw_name}[/b][/size]\n[color=cccccc]Норма по рецепту: {norm} кг[/color]",
            markup=True, size_hint_y=None, halign='center'
        )
        lbl_title.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
        lbl_title.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 10))
        self.content_layout.add_widget(lbl_title)

        lbl_total = Label(
            text=f"[color=33ff33][b]ОБЩИЙ ОСТАТОК: {total_w:.3f} кг[/b]\n({mass_to_words(kg, gr)})[/color]",
            markup=True, size_hint_y=None, halign='center'
        )
        lbl_total.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
        lbl_total.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 10))
        self.content_layout.add_widget(lbl_total)

        if not batches:
            self.content_layout.add_widget(Label(text="[color=888888]Сырье отсутствует на складе[/color]", markup=True, size_hint_y=None, height=dp(30)))
        else:
            for b in batches:
                b_kg = int(b['total_weight'])
                b_gr = int(round((b['total_weight'] - b_kg) * 1000))
                bags_details = ", ".join([f"№{bag[1]} ({bag[2]:.3f}кг)" for bag in b['bags']])
                lbl = Label(
                    text=f"[b]Серия: {b['series']}[/b] | № АЛ: {b['al']} | Дата: {b['income_date']}\n"
                         f"Масса серии: [color=33ffff]{b['total_weight']:.3f} кг[/color] ({b_kg} кг {b_gr} гр)\n"
                         f"Мешки в наличии: {bags_details}",
                    markup=True, size_hint_y=None, halign='left', valign='top'
                )
                lbl.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
                lbl.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 15))
                self.content_layout.add_widget(lbl)

        self.content_layout.add_widget(Label(text="[b][color=ff9933]ИСТОРИЯ СПИСАНИЙ ЗА МЕСЯЦ:[/color][/b]", markup=True, size_hint_y=None, height=dp(30)))
        deductions = self.db.get_monthly_deductions_detailed(self.raw_name)
        if not deductions:
            self.content_layout.add_widget(Label(text="[color=888888]Списаний в этом месяце не было[/color]", markup=True, size_hint_y=None, height=dp(25)))
        else:
            total_ded_w = sum([d['weight'] for d in deductions])
            self.content_layout.add_widget(Label(text=f"[b]Всего списано: [color=ff6666]{total_ded_w:.3f} кг[/color][/b]", markup=True, size_hint_y=None, height=dp(25)))
            for d in deductions:
                ded_text = f"• {d['date']} — Серия [b]{d['series']}[/b]: [color=ff6666]{d['weight']:.3f} кг[/color]\n"
                if d['fully_removed_bags']:
                    ded_text += f"   └ Ушли мешки: № {', '.join(d['fully_removed_bags'])}\n"
                if d['transitional_bag']:
                    tb = d['transitional_bag']
                    ded_text += f"   └ [color=ffcc00]Переходной мешок №{tb[0]}:[/color] взято {tb[1]:.3f} кг | [color=33ff33]остаток: {tb[2]:.3f} кг[/color]\n"
                lbl_ded = Label(text=ded_text, markup=True, size_hint_y=None, halign='left', valign='top')
                lbl_ded.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
                lbl_ded.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 10))
                self.content_layout.add_widget(lbl_ded)


class WarehouseApp(App):
    def build(self):
        self.db = Database()
        self.raw_names = list(RECIPE.keys())
        self.cards = {}

        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        self.lbl_indicator = Label(text="", size_hint_y=None, markup=True, halign='center')
        self.lbl_indicator.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
        self.lbl_indicator.bind(texture_size=lambda s, t: setattr(s, 'height', max(dp(35), t[1] + 5)))
        main_layout.add_widget(self.lbl_indicator)

        self.carousel = Carousel(direction='right', size_hint=(1, 1))
        for raw in self.raw_names:
            card = RawCard(raw_name=raw, db=self.db)
            self.cards[raw] = card
            self.carousel.add_widget(card)

        main_layout.add_widget(self.carousel)

        btn_grid = GridLayout(cols=3, spacing=6, size_hint_y=None, height=dp(130))
        
        btn_income = Button(text='Приход\nсырья', background_color=(0.2, 0.7, 0.3, 1), halign='center')
        btn_income.bind(on_press=self.show_income_popup)
        
        btn_income_log = Button(text='Журнал\nприхода', background_color=(0.1, 0.6, 0.6, 1), halign='center')
        btn_income_log.bind(on_press=lambda inst: self.show_income_log_popup())

        btn_deduct = Button(text='Списание\nОКК', background_color=(0.7, 0.3, 0.7, 1), halign='center')
        btn_deduct.bind(on_press=self.show_deduct_popup)

        btn_recipe = Button(text='ОТВЕСИТЬ\nРЕЦЕПТ', background_color=(0.9, 0.5, 0.1, 1), halign='center')
        btn_recipe.bind(on_press=self.deduct_recipe)
        
        btn_edit = Button(text='Редактировать', background_color=(0.8, 0.2, 0.2, 1), halign='center')
        btn_edit.bind(on_press=self.show_edit_popup)
        
        btn_report = Button(text='Отчет\n(месяц)', background_color=(0.2, 0.5, 0.8, 1), halign='center')
        btn_report.bind(on_press=self.show_report_popup)

        btn_grid.add_widget(btn_income)
        btn_grid.add_widget(btn_income_log)
        btn_grid.add_widget(btn_deduct)
        btn_grid.add_widget(btn_recipe)
        btn_grid.add_widget(btn_edit)
        btn_grid.add_widget(btn_report)
        
        main_layout.add_widget(btn_grid)

        self.carousel.bind(current_slide=self.on_slide_change)
        self.update_indicator()

        return main_layout

    def get_current_raw_name(self):
        if self.carousel.current_slide and hasattr(self.carousel.current_slide, 'raw_name'):
            return self.carousel.current_slide.raw_name
        return self.raw_names[0]

    def on_slide_change(self, carousel, value):
        self.update_indicator()

    def update_indicator(self):
        if hasattr(self, 'carousel') and self.carousel.current_slide:
            idx = self.carousel.index + 1
            total = len(self.raw_names)
            current_raw = self.get_current_raw_name()
            self.lbl_indicator.text = f"[color=33ffff]◄ Свайп ({idx}/{total}) ►[/color]\n[b]{current_raw}[/b]"

    def refresh_all_cards(self):
        for card in self.cards.values():
            card.refresh_card()

    def show_income_popup(self, instance):
        current_raw = self.get_current_raw_name()
        scroll = ScrollView(size_hint=(1, 1))
        content = BoxLayout(orientation='vertical', spacing=10, padding=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        # Берем индивидуальный кэш конкретно для текущего сырья
        cached_al = self.db.get_cached_value_for_raw(current_raw, 'last_al', '')
        cached_ser = self.db.get_cached_value_for_raw(current_raw, 'last_series', '')

        inp_date = TextInput(text=get_current_date_str(), hint_text='Дата (ГГГГ-ММ-ДД)', multiline=False, size_hint_y=None, height=dp(45))
        inp_al = TextInput(text=cached_al, hint_text='№ Аналитического листа (АЛ)', multiline=False, size_hint_y=None, height=dp(45))
        inp_ser = TextInput(text=cached_ser, hint_text='№ Серии', multiline=False, size_hint_y=None, height=dp(45))
        inp_weight = TextInput(hint_text='Масса прихода (кг)', multiline=False, input_filter='float', size_hint_y=None, height=dp(45))
        inp_bags = TextInput(hint_text='Тарные места (например: 1-5)', multiline=False, size_hint_y=None, height=dp(45))

        lbl_inc_title = Label(text=f"[b]Приход:[/b] {current_raw}", markup=True, size_hint_y=None)
        lbl_inc_title.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
        lbl_inc_title.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 5))

        content.add_widget(lbl_inc_title)
        content.add_widget(Label(text="Дата поступления:", size_hint_y=None, height=dp(20)))
        content.add_widget(inp_date)
        content.add_widget(inp_al)
        content.add_widget(inp_ser)
        content.add_widget(inp_weight)
        content.add_widget(inp_bags)

        btn_save = Button(text='Сохранить приход', size_hint_y=None, height=dp(50), background_color=(0.2, 0.7, 0.3, 1))
        content.add_widget(btn_save)

        scroll.add_widget(content)
        popup = Popup(title='Внесение прихода', content=scroll, size_hint=(0.9, 0.85))

        def save_income(inst):
            try:
                inc_date = inp_date.text.strip() or get_current_date_str()
                al, ser = inp_al.text.strip(), inp_ser.text.strip()
                w = float(inp_weight.text.replace(',', '.'))
                bags = parse_bag_numbers(inp_bags.text)
                
                if not al or not ser or w <= 0 or not bags: return
                self.db.add_income(current_raw, al, ser, w, bags, inc_date)
                
                # Сохраняем индивидуально для этого сырья
                self.db.save_cached_value_for_raw(current_raw, 'last_al', al)
                self.db.save_cached_value_for_raw(current_raw, 'last_series', ser)

                self.refresh_all_cards()
                popup.dismiss()
            except ValueError:
                pass

        btn_save.bind(on_press=save_income)
        popup.open()

    def show_income_log_popup(self):
        current_raw = self.get_current_raw_name()
        scroll = ScrollView()
        content = BoxLayout(orientation='vertical', spacing=10, padding=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        lbl_log_title = Label(text=f"[b]ЖУРНАЛ ПРИХОДА ({current_raw}):[/b]", markup=True, size_hint_y=None)
        lbl_log_title.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
        lbl_log_title.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 5))
        content.add_widget(lbl_log_title)
        
        logs = self.db.get_income_log(current_raw)
        popup = Popup(title='Журнал прихода сырья', content=scroll, size_hint=(0.95, 0.85))

        if not logs:
            content.add_widget(Label(text='Записи о приходах отсутствуют', size_hint_y=None, height=dp(30)))
        else:
            for entry in logs:
                box = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None)
                
                lbl_info = Label(
                    text=f"Серия: [b]{entry['series']}[/b] | АЛ: {entry['al']} | [color=33ff33]{entry['weight']:.3f} кг[/color]\nМешки: № {entry['bags_str']}",
                    markup=True, size_hint_y=None, halign='left'
                )
                lbl_info.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
                lbl_info.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 5))
                
                row_btns = BoxLayout(orientation='horizontal', spacing=5, size_hint_y=None, height=dp(40))
                inp_date = TextInput(text=entry['income_date'], multiline=False, size_hint_x=0.4)
                btn_update_date = Button(text='Изм. дату', size_hint_x=0.3, background_color=(0.2, 0.6, 0.8, 1))
                btn_del = Button(text='Удалить', size_hint_x=0.3, background_color=(0.9, 0.3, 0.3, 1))

                def make_update_date_func(log_id, text_input):
                    return lambda inst: (self.db.update_income_log_date(log_id, text_input.text.strip()), self.refresh_all_cards(), popup.dismiss(), self.show_income_log_popup())

                def make_delete_func(log_id):
                    return lambda inst: (self.db.delete_income_log_entry(log_id), self.refresh_all_cards(), popup.dismiss(), self.show_income_log_popup())

                btn_update_date.bind(on_press=make_update_date_func(entry['id'], inp_date))
                btn_del.bind(on_press=make_delete_func(entry['id']))

                row_btns.add_widget(inp_date)
                row_btns.add_widget(btn_update_date)
                row_btns.add_widget(btn_del)

                box.add_widget(lbl_info)
                box.add_widget(row_btns)
                
                box.bind(minimum_height=box.setter('height'))
                box.height = lbl_info.height + row_btns.height + 10
                
                content.add_widget(box)

        scroll.add_widget(content)
        popup.open()

    def show_deduct_popup(self, instance):
        current_raw = self.get_current_raw_name()
        batches = self.db.get_raw_batches(current_raw)
        
        if not batches:
            Popup(title='Информация', content=Label(text='Нет серий для списания!'), size_hint=(0.8, 0.4)).open()
            return

        scroll = ScrollView()
        content = BoxLayout(orientation='vertical', spacing=10, padding=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        
        lbl_ded_title = Label(text=f"Списание / Передача: [b]{current_raw}[/b]", markup=True, size_hint_y=None)
        lbl_ded_title.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
        lbl_ded_title.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 5))
        content.add_widget(lbl_ded_title)

        popup = Popup(title='Списание из серии', content=scroll, size_hint=(0.9, 0.8))

        for b in batches:
            btn_b = Button(text=f"Серия: {b['series']} | Остаток: {b['total_weight']:.3f} кг", size_hint_y=None, height=dp(45), background_color=(0.7, 0.3, 0.7, 1))
            btn_b.bind(on_press=lambda inst, batch_data=b: self.open_batch_deduct_dialog(batch_data, popup))
            content.add_widget(btn_b)

        scroll.add_widget(content)
        popup.open()

    def open_batch_deduct_dialog(self, batch, parent_popup):
        parent_popup.dismiss()
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        inp_date = TextInput(text=get_current_date_str(), hint_text='Дата списания (ГГГГ-ММ-ДД)', multiline=False, size_hint_y=None, height=dp(45))
        inp_deduct_weight = TextInput(hint_text='Масса для списания (кг)', multiline=False, input_filter='float', size_hint_y=None, height=dp(45))
        
        content.add_widget(Label(text=f"Серия: [b]{batch['series']}[/b]\nДоступно: {batch['total_weight']:.3f} кг", markup=True, size_hint_y=None, height=dp(40)))
        content.add_widget(Label(text="Дата списания (можно изменить):", size_hint_y=None, height=dp(20)))
        content.add_widget(inp_date)
        content.add_widget(inp_deduct_weight)

        btn_confirm = Button(text='Подтвердить списание', size_hint_y=None, height=dp(45), background_color=(0.2, 0.7, 0.3, 1))
        content.add_widget(btn_confirm)
        deduct_popup = Popup(title='Ввод массы списания', content=content, size_hint=(0.85, 0.6))

        def confirm_deduct(inst):
            try:
                d_date = inp_date.text.strip() or get_current_date_str()
                w_deduct = float(inp_deduct_weight.text.replace(',', '.'))
                if 0 < w_deduct <= batch['total_weight']:
                    self.db.deduct_from_batch(batch['id'], w_deduct, d_date)
                    self.refresh_all_cards()
                    deduct_popup.dismiss()
            except ValueError:
                pass

        btn_confirm.bind(on_press=confirm_deduct)
        deduct_popup.open()

    def show_edit_popup(self, instance):
        current_raw = self.get_current_raw_name()
        batches = self.db.get_raw_batches(current_raw)
        
        scroll = ScrollView()
        content = BoxLayout(orientation='vertical', spacing=10, padding=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        content.add_widget(Label(text=f"Редактирование {current_raw}:", size_hint_y=None, height=dp(30)))
        popup = Popup(title='Редактирование сырья', content=scroll, size_hint=(0.9, 0.8))

        if batches:
            for b in batches:
                btn_b = Button(text=f"Серия: {b['series']} | АЛ: {b['al']} | Вес: {b['total_weight']:.3f}кг", size_hint_y=None, height=dp(45), background_color=(0.2, 0.5, 0.8, 1))
                btn_b.bind(on_press=lambda inst, batch_data=b: self.open_single_batch_editor(batch_data, popup))
                content.add_widget(btn_b)

        content.add_widget(Label(text="[b]Корректировка списаний:[/b]", markup=True, size_hint_y=None, height=dp(25)))
        btn_manage_ded = Button(text='Управление списаниями (даты/удаление)', size_hint_y=None, height=dp(45), background_color=(0.7, 0.4, 0.2, 1))
        btn_manage_ded.bind(on_press=lambda inst: (popup.dismiss(), self.show_deductions_manager(current_raw)))
        content.add_widget(btn_manage_ded)

        scroll.add_widget(content)
        popup.open()

    def show_deductions_manager(self, raw_name):
        scroll = ScrollView()
        content = BoxLayout(orientation='vertical', spacing=10, padding=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        deductions = self.db.get_monthly_deductions_detailed(raw_name)
        popup = Popup(title='История списаний (редактирование)', content=scroll, size_hint=(0.95, 0.8))

        if not deductions:
            content.add_widget(Label(text='Записи о списаниях отсутствуют'))
        else:
            for d in deductions:
                box = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None, height=dp(80))
                lbl_info = Label(text=f"Сер: [b]{d['series']}[/b] | Масса: [color=ff6666]{d['weight']:.3f} кг[/color]", markup=True)
                
                row_btns = BoxLayout(orientation='horizontal', spacing=5)
                inp_date = TextInput(text=d['date'], multiline=False, size_hint_x=0.4)
                btn_update_date = Button(text='Изм. дату', size_hint_x=0.3, background_color=(0.2, 0.6, 0.8, 1))
                btn_del = Button(text='Удалить', size_hint_x=0.3, background_color=(0.9, 0.3, 0.3, 1))

                def make_update_date_func(ded_id, text_input):
                    return lambda inst: (self.db.update_deduction_date(ded_id, text_input.text.strip()), self.refresh_all_cards(), popup.dismiss(), self.show_deductions_manager(raw_name))

                def make_delete_func(ded_id):
                    return lambda inst: (self.db.delete_single_deduction(ded_id), self.refresh_all_cards(), popup.dismiss(), self.show_deductions_manager(raw_name))

                btn_update_date.bind(on_press=make_update_date_func(d['id'], inp_date))
                btn_del.bind(on_press=make_delete_func(d['id']))

                row_btns.add_widget(inp_date)
                row_btns.add_widget(btn_update_date)
                row_btns.add_widget(btn_del)

                box.add_widget(lbl_info)
                box.add_widget(row_btns)
                content.add_widget(box)

        scroll.add_widget(content)
        popup.open()

    def open_single_batch_editor(self, batch, parent_popup):
        parent_popup.dismiss()
        scroll = ScrollView()
        content = BoxLayout(orientation='vertical', spacing=10, padding=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        inp_date = TextInput(text=str(batch['income_date']), multiline=False, size_hint_y=None, height=dp(40))
        inp_al = TextInput(text=str(batch['al']), multiline=False, size_hint_y=None, height=dp(40))
        inp_ser = TextInput(text=str(batch['series']), multiline=False, size_hint_y=None, height=dp(40))

        content.add_widget(Label(text=f"[b]Редактирование серии:[/b] {batch['series']}", markup=True, size_hint_y=None, height=dp(25)))
        content.add_widget(Label(text="Дата поступления:", size_hint_y=None, height=dp(20)))
        content.add_widget(inp_date)
        content.add_widget(Label(text="№ АЛ:", size_hint_y=None, height=dp(20)))
        content.add_widget(inp_al)
        content.add_widget(Label(text="№ Серии:", size_hint_y=None, height=dp(20)))
        content.add_widget(inp_ser)
        content.add_widget(Label(text="[b]Тарные места серии:[/b]", markup=True, size_hint_y=None, height=dp(30)))

        edit_popup = Popup(title='Редактирование серии', content=scroll, size_hint=(0.95, 0.9))
        bag_inputs = {}

        for bag in batch['bags']:
            bag_db_id, bag_num, bag_w = bag
            row = BoxLayout(orientation='horizontal', spacing=5, size_hint_y=None, height=dp(40))
            lbl_num = Label(text=f"№{bag_num}", size_hint_x=0.2)
            inp_w = TextInput(text=str(round(bag_w, 3)), multiline=False, input_filter='float', size_hint_x=0.4)
            btn_del_bag = Button(text='✕', size_hint_x=0.2, background_color=(0.9, 0.3, 0.3, 1))

            def make_del_bag_func(b_id):
                return lambda inst: (self.db.delete_bag(b_id), self.refresh_all_cards(), edit_popup.dismiss())
            btn_del_bag.bind(on_press=make_del_bag_func(bag_db_id))

            row.add_widget(lbl_num)
            row.add_widget(inp_w)
            row.add_widget(btn_del_bag)
            content.add_widget(row)
            bag_inputs[bag_db_id] = inp_w

        btn_add_bag = Button(text='+ Добавить тарное место', size_hint_y=None, height=dp(40), background_color=(0.2, 0.6, 0.8, 1))
        
        def show_add_bag_dialog(inst):
            add_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
            inp_new_num = TextInput(hint_text='Номер мешка (например: 4)', multiline=False, input_filter='int', size_hint_y=None, height=dp(40))
            inp_new_w = TextInput(hint_text='Вес мешка (кг)', multiline=False, input_filter='float', size_hint_y=None, height=dp(40))
            btn_confirm_add = Button(text='Добавить', size_hint_y=None, height=dp(40), background_color=(0.2, 0.7, 0.3, 1))
            
            add_content.add_widget(Label(text="[b]Добавление нового мешка[/b]", markup=True, size_hint_y=None, height=dp(25)))
            add_content.add_widget(inp_new_num)
            add_content.add_widget(inp_new_w)
            add_content.add_widget(btn_confirm_add)
            
            add_popup = Popup(title='Новый мешок', content=add_content, size_hint=(0.8, 0.5))
            
            def save_new_bag(i):
                try:
                    num = int(inp_new_num.text.strip())
                    w = float(inp_new_w.text.replace(',', '.'))
                    if num > 0 and w > 0:
                        self.db.add_single_bag(batch['id'], num, w)
                        self.refresh_all_cards()
                        add_popup.dismiss()
                        edit_popup.dismiss()
                except ValueError:
                    pass
            
            btn_confirm_add.bind(on_press=save_new_bag)
            add_popup.open()

        btn_add_bag.bind(on_press=show_add_bag_dialog)
        content.add_widget(btn_add_bag)

        btn_save = Button(text='Сохранить изменения', size_hint_y=None, height=dp(45), background_color=(0.2, 0.7, 0.3, 1))
        btn_delete_all = Button(text='Удалить ВСЮ серию', size_hint_y=None, height=dp(45), background_color=(0.8, 0.2, 0.2, 1))

        content.add_widget(btn_save)
        content.add_widget(btn_delete_all)
        scroll.add_widget(content)

        def save_changes(inst):
            try:
                new_date, new_al, new_ser = inp_date.text.strip(), inp_al.text.strip(), inp_ser.text.strip()
                if new_al and new_ser:
                    self.db.update_batch_header(batch['id'], new_al, new_ser, new_date)
                    for bag_db_id, inp_w in bag_inputs.items():
                        new_w = float(inp_w.text.replace(',', '.'))
                        if new_w > 0:
                            cursor = self.db.conn.cursor()
                            cursor.execute('UPDATE bags SET weight = ? WHERE id = ?', (new_w, bag_db_id))
                        else:
                            self.db.delete_bag(bag_db_id)
                    self.db.recalculate_batch_total_weight(batch['id'])
                    self.refresh_all_cards()
                    edit_popup.dismiss()
            except ValueError:
                pass

        btn_save.bind(on_press=save_changes)
        btn_delete_all.bind(on_press=lambda inst: (self.db.delete_batch(batch['id']), self.refresh_all_cards(), edit_popup.dismiss()))
        edit_popup.open()

    def deduct_recipe(self, instance):
        missing = []
        for raw, norm in RECIPE.items():
            batches = self.db.get_raw_batches(raw)
            avail = sum([b['total_weight'] for b in batches])
            if avail < norm - 1e-6:
                missing.append(f"• {raw}: не хватает {norm - avail:.2f} кг!")

        if missing:
            msg = "[color=ff3333][b]ОТВЕСИВАНИЕ НЕВОЗМОЖНО![/b]\nНедостаточно сырья:[/color]\n\n" + "\n".join(missing)
            Popup(title='Ошибка отвешивания', content=Label(text=msg, markup=True, halign='center'), size_hint=(0.9, 0.7)).open()
            return

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text="Укажите дату отвешивания рецепта:", size_hint_y=None, height=dp(30)))
        
        inp_recipe_date = TextInput(text=get_current_date_str(), hint_text='ГГГГ-ММ-ДД', multiline=False, size_hint_y=None, height=dp(45))
        content.add_widget(inp_recipe_date)

        btn_confirm = Button(text='Подтвердить отвешивание', size_hint_y=None, height=dp(50), background_color=(0.9, 0.5, 0.1, 1))
        content.add_widget(btn_confirm)

        recipe_popup = Popup(title='Выбор даты отвешивания', content=content, size_hint=(0.85, 0.5))

        def confirm_recipe_deduction(inst):
            selected_date = inp_recipe_date.text.strip() or get_current_date_str()
            for raw, norm in RECIPE.items():
                self.db.deduct_raw_fifo(raw, norm, selected_date)
            self.refresh_all_cards()
            recipe_popup.dismiss()
            Popup(title='Успех', content=Label(text=f'[color=33ff33][b]РЕЦЕПТ УСПЕШНО ОТВЕШЕН!\nДата: {selected_date}[/b][/color]', markup=True, halign='center'), size_hint=(0.7, 0.4)).open()

        btn_confirm.bind(on_press=confirm_recipe_deduction)
        recipe_popup.open()

    def show_report_popup(self, instance):
        scroll = ScrollView()
        report_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=12, padding=10)
        report_layout.bind(minimum_height=report_layout.setter('height'))

        report_layout.add_widget(Label(text="[b]ОСТАТКИ СЫРЬЯ И СЕРИЙ[/b]", markup=True, size_hint_y=None, height=dp(35), halign='center'))

        for raw in RECIPE.keys():
            batches = self.db.get_raw_batches(raw)
            raw_text = f"[b]• {raw}[/b]\n"
            if not batches:
                raw_text += "  [color=888888]Остаток: 0.000 кг (нет серий)[/color]\n"
            else:
                for b in batches:
                    b_kg = int(b['total_weight'])
                    b_gr = int(round((b['total_weight'] - b_kg) * 1000))
                    raw_text += f"  [color=33ffff]Серия: {b['series']}[/color] (№ АЛ: {b['al']}, Дата: {b['income_date']}): {b['total_weight']:.3f} кг\n  └ {mass_to_words(b_kg, b_gr)}\n"

            lbl = Label(text=raw_text, markup=True, size_hint_y=None, halign='left', valign='top')
            lbl.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
            lbl.bind(texture_size=lambda s, t: setattr(s, 'height', t[1] + 10))
            report_layout.add_widget(lbl)

        btn_clear_deductions = Button(text='Сбросить историю списаний', size_hint_y=None, height=dp(50), background_color=(0.8, 0.2, 0.2, 1))
        popup = Popup(title='Ежемесячный отчет по сериям', content=scroll, size_hint=(0.95, 0.85))

        btn_clear_deductions.bind(on_press=lambda inst: (self.db.clear_all_deductions(), self.refresh_all_cards(), popup.dismiss()))
        report_layout.add_widget(btn_clear_deductions)

        scroll.add_widget(report_layout)
        popup.open()

if __name__ == '__main__':
    WarehouseApp().run()
