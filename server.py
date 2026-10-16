#!/usr/bin/env python3
"""Thư viện trường học - backend (Python stdlib + SQLite). Chạy: python server.py  ->  http://localhost:8000"""
import sqlite3, hashlib, os, json, secrets, re, datetime as dt
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

D = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(D, 'library.db')
FINE, DAYS, MAXLOAN = 5000, 14, 5          # phạt/ngày quá hạn, số ngày mượn, tối đa số sách đang mượn
ACTIVE = "('Chờ duyệt','Đã duyệt','Đang mượn')"
SES = {}

def hp(p, s=None):  # PBKDF2-SHA256 + salt riêng, 100.000 vòng (giống dự án mẫu)
    s = s or secrets.token_hex(16)
    return s + '$' + hashlib.pbkdf2_hmac('sha256', p.encode(), s.encode(), 100000).hex()
def vp(p, h): return secrets.compare_digest(hp(p, h.split('$')[0]), h)
def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; c.execute('pragma foreign_keys=on'); return c
class E(Exception): pass
today = lambda: dt.date.today().isoformat()

SCHEMA = """
create table users(id integer primary key, username text not null unique, pw text not null,
  role text not null default 'student' check(role in('student','admin')), full_name text not null,
  student_code text unique, class text, email text unique, phone text, created text default(datetime('now','localtime')));
create table categories(id integer primary key, name text not null unique);
create table books(id integer primary key, code text not null unique, title text not null, author text not null,
  cat_id integer references categories(id), qty integer not null check(qty>=0), cover text, descr text,
  featured integer default 0, created text default(datetime('now','localtime')));
create table loans(id integer primary key, user_id integer not null references users(id), book_id integer not null references books(id),
  status text not null default 'Chờ duyệt' check(status in('Chờ duyệt','Đã duyệt','Đang mượn','Đã trả','Từ chối','Đã hủy')),
  req_date text default(date('now','localtime')), borrow_date text, due_date text, return_date text,
  fine integer default 0, fine_paid integer default 0);
create table anns(id integer primary key, title text not null, body text not null, created text default(datetime('now','localtime')));
"""
def init():
    if os.path.exists(DB): return
    c = db(); c.executescript(SCHEMA)
    c.execute("insert into users(username,pw,role,full_name,email) values('thuthu',?, 'admin','Nguyễn Thị Thủ Thư','thuthu@truong.edu.vn')", (hp('admin123'),))
    for i, (u, n, cl) in enumerate([('sv001', 'Lâm Hoàng Tuấn', 'CNTT01'), ('sv002', 'Trần Minh Anh', 'CNTT02')], 1):
        c.execute("insert into users(username,pw,full_name,student_code,class,email,phone) values(?,?,?,?,?,?,?)",
                  (u, hp('123456'), n, 'SV00%d' % i, cl, u + '@sv.edu.vn', '09000000%02d' % i))
    cats = ['Công nghệ thông tin', 'Văn học', 'Khoa học', 'Kinh tế', 'Ngoại ngữ']
    for n in cats: c.execute("insert into categories(name) values(?)", (n,))
    bks = [('CNTT001', 'Lập trình C# cơ bản', 'Phạm Hữu Khang', 1, 5, 1), ('CNTT002', 'Cơ sở dữ liệu SQL Server', 'Nguyễn Văn Ba', 1, 3, 1),
           ('CNTT003', 'Python cho người mới bắt đầu', 'Trần Quốc Việt', 1, 4, 0), ('VH001', 'Dế Mèn phiêu lưu ký', 'Tô Hoài', 2, 6, 1),
           ('VH002', 'Số đỏ', 'Vũ Trọng Phụng', 2, 2, 0), ('VH003', 'Truyện Kiều', 'Nguyễn Du', 2, 3, 0),
           ('KH001', 'Lược sử thời gian', 'Stephen Hawking', 3, 3, 1), ('KH002', 'Vật lý đại cương', 'Lương Duyên Bình', 3, 4, 0),
           ('KT001', 'Kinh tế vi mô', 'N. Gregory Mankiw', 4, 3, 0), ('KT002', 'Nguyên lý Marketing', 'Philip Kotler', 4, 2, 1),
           ('NN001', 'English Grammar in Use', 'Raymond Murphy', 5, 5, 0), ('NN002', 'Giáo trình Hán ngữ', 'Dương Ký Châu', 5, 2, 0)]
    for b in bks: c.execute("insert into books(code,title,author,cat_id,qty,featured,descr) values(?,?,?,?,?,?,'Sách tham khảo dành cho sinh viên.')", b)
    d = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    c.executemany("insert into loans(user_id,book_id,status,req_date,borrow_date,due_date,return_date,fine) values(?,?,?,?,?,?,?,?)", [
        (2, 1, 'Đang mượn', d(-20), d(-19), d(-5), None, 0),   # quá hạn 5 ngày
        (2, 4, 'Đang mượn', d(-3), d(-2), d(12), None, 0),
        (3, 2, 'Chờ duyệt', d(0), None, None, None, 0),
        (3, 7, 'Đã duyệt', d(-1), None, None, None, 0),
        (2, 3, 'Đã trả', d(-30), d(-29), d(-15), d(-16), 0),
        (3, 1, 'Đã trả', d(-40), d(-39), d(-25), d(-20), 25000)])
    c.executemany("insert into anns(title,body) values(?,?)", [('Lịch mở cửa thư viện', 'Thư viện mở cửa từ 7h30 đến 17h, thứ Hai đến thứ Bảy.'),
                  ('Quy định mượn sách', 'Mỗi bạn mượn tối đa %d cuốn, thời hạn %d ngày. Trả trễ phạt %d đồng/ngày.' % (MAXLOAN, DAYS, FINE))])
    c.commit(); c.close()

# ---------- truy vấn dùng chung ----------
BQ = ("select b.*,c.name cat,b.qty-(select count(*) from loans l where l.book_id=b.id and l.status in('Đã duyệt','Đang mượn')) avail "
      "from books b left join categories c on c.id=b.cat_id")
LQ = ("select l.*,b.title,b.code,u.full_name,u.student_code from loans l join books b on b.id=l.book_id join users u on u.id=l.user_id")
def rows(c, sql, a=()): return [dict(r) for r in c.execute(sql, a)]
def dec(rs):  # tính số ngày trễ và tiền phạt tạm tính cho sách đang mượn
    t = dt.date.today()
    for r in rs:
        r['late'] = 0; r['fine_now'] = r['fine']
        if r['status'] == 'Đang mượn':
            n = (t - dt.date.fromisoformat(r['due_date'])).days
            if n > 0: r['late'], r['fine_now'] = n, n * FINE
    return rs
def need(d, *ks):
    for k in ks:
        if not str(d.get(k, '')).strip(): raise E('Vui lòng nhập đầy đủ thông tin bắt buộc.')
def chk_user(d, pw=True):
    need(d, 'full_name', 'email')
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', d['email'].strip()): raise E('Email không đúng định dạng.')
    if d.get('phone') and not re.fullmatch(r'0\d{9}', d['phone'].strip()): raise E('Số điện thoại phải gồm 10 số, bắt đầu bằng 0.')
    if pw and len(d.get('password', '')) < 6: raise E('Mật khẩu phải có ít nhất 6 ký tự.')

A = {}
def act(f): A[f.__name__] = f; return f

# ---------- tài khoản ----------
@act
def register(c, u, d, s):
    need(d, 'student_code', 'class', 'username'); chk_user(d)
    if d['password'] != d.get('password2'): raise E('Mật khẩu xác nhận không khớp.')
    c.execute("insert into users(username,pw,full_name,student_code,class,email,phone) values(?,?,?,?,?,?,?)",
              (d['username'].strip(), hp(d['password']), d['full_name'].strip(), d['student_code'].strip(), d['class'].strip(),
               d['email'].strip().lower(), d.get('phone', '').strip()))   # luôn là student
    return {}
@act
def login(c, u, d, s):
    r = c.execute("select * from users where username=? or student_code=?", (d.get('username', '').strip(),) * 2).fetchone()
    if not r or not vp(d.get('password', ''), r['pw']): raise E('Sai tên đăng nhập hoặc mật khẩu.')
    sid = secrets.token_hex(24); SES[sid] = r['id']; s.ck = 'sid=%s; Path=/; HttpOnly; SameSite=Lax' % sid
    return {'role': r['role']}
@act
def logout(c, u, d, s):
    SES.pop(s.sid, None); s.ck = 'sid=; Path=/; Max-Age=0'; return {}
@act
def me(c, u, d, s):
    if not u: raise E('Chưa đăng nhập')
    return {'user': {k: u[k] for k in ('id', 'username', 'role', 'full_name', 'student_code', 'class', 'email', 'phone')}}
@act
def forgot(c, u, d, s):  # demo: xác minh bằng tên đăng nhập + email
    r = c.execute("select id from users where username=? and email=?", (d.get('username', '').strip(), d.get('email', '').strip().lower())).fetchone()
    if not r: raise E('Tên đăng nhập và email không khớp.')
    if len(d.get('password', '')) < 6: raise E('Mật khẩu phải có ít nhất 6 ký tự.')
    c.execute("update users set pw=? where id=?", (hp(d['password']), r['id'])); return {}
@act
def change_pw(c, u, d, s):
    if not vp(d.get('old', ''), u['pw']): raise E('Mật khẩu hiện tại không đúng.')
    if len(d.get('new', '')) < 6: raise E('Mật khẩu mới phải có ít nhất 6 ký tự.')
    c.execute("update users set pw=? where id=?", (hp(d['new']), u['id'])); return {}
@act
def profile(c, u, d, s):
    chk_user(d, False)
    c.execute("update users set full_name=?,class=?,email=?,phone=? where id=?",
              (d['full_name'].strip(), d.get('class', '').strip(), d['email'].strip().lower(), d.get('phone', '').strip(), u['id'])); return {}

# ---------- học sinh / sinh viên ----------
@act
def home(c, u, d, s):
    return {'new': rows(c, BQ + " order by b.id desc limit 8"), 'featured': rows(c, BQ + " where b.featured=1 limit 8"),
            'anns': rows(c, "select * from anns order by id desc limit 5")}
@act
def cats(c, u, d, s): return {'cats': rows(c, "select c.*,(select count(*) from books where cat_id=c.id) n from categories c order by name")}
@act
def books(c, u, d, s):
    q = '%' + d.get('q', '').strip() + '%'
    sql, a = BQ + " where (b.title like ? or b.author like ? or b.code like ? or c.name like ?)", [q] * 4
    if d.get('cat'): sql += " and b.cat_id=?"; a.append(d['cat'])
    return {'books': rows(c, sql + " order by b.id desc", a)}
@act
def book(c, u, d, s):
    r = rows(c, BQ + " where b.id=?", (d['id'],))
    if not r: raise E('Sách không tồn tại.')
    return {'book': r[0]}
@act
def request_loan(c, u, d, s):
    b = rows(c, BQ + " where b.id=?", (d['book_id'],))
    if not b: raise E('Sách không tồn tại.')
    if b[0]['avail'] < 1: raise E('Sách đã hết, vui lòng quay lại sau.')
    if c.execute("select 1 from loans where user_id=? and book_id=? and status in " + ACTIVE, (u['id'], d['book_id'])).fetchone():
        raise E('Bạn đã có yêu cầu hoặc đang mượn cuốn này.')
    if c.execute("select count(*) from loans where user_id=? and status in " + ACTIVE, (u['id'],)).fetchone()[0] >= MAXLOAN:
        raise E('Bạn đã đạt giới hạn %d cuốn.' % MAXLOAN)
    c.execute("insert into loans(user_id,book_id) values(?,?)", (u['id'], d['book_id'])); return {}
@act
def my_loans(c, u, d, s): return {'loans': dec(rows(c, LQ + " where l.user_id=? order by l.id desc", (u['id'],)))}
@act
def cancel_loan(c, u, d, s):
    if not c.execute("update loans set status='Đã hủy' where id=? and user_id=? and status='Chờ duyệt'", (d['id'], u['id'])).rowcount:
        raise E('Chỉ hủy được yêu cầu đang chờ duyệt.')
    return {}

# ---------- thủ thư ----------
@act
def a_stats(c, u, d, s):
    g = lambda q: c.execute(q).fetchone()[0]
    return {'titles': g("select count(*) from books"), 'copies': g("select coalesce(sum(qty),0) from books"),
            'readers': g("select count(*) from users where role='student'"), 'borrowing': g("select count(*) from loans where status='Đang mượn'"),
            'pending': g("select count(*) from loans where status='Chờ duyệt'"),
            'overdue': g("select count(*) from loans where status='Đang mượn' and due_date<date('now','localtime')")}
@act
def a_book_save(c, u, d, s):
    need(d, 'code', 'title', 'author')
    try: q = int(d.get('qty'))
    except (TypeError, ValueError): raise E('Số lượng phải là số nguyên.')
    if q < 0: raise E('Số lượng không được âm.')
    v = (d['code'].strip(), d['title'].strip(), d['author'].strip(), d.get('cat_id') or None, q, d.get('cover', '').strip(), d.get('descr', ''), int(bool(d.get('featured'))))
    if d.get('id'): c.execute("update books set code=?,title=?,author=?,cat_id=?,qty=?,cover=?,descr=?,featured=? where id=?", v + (d['id'],))
    else: c.execute("insert into books(code,title,author,cat_id,qty,cover,descr,featured) values(?,?,?,?,?,?,?,?)", v)
    return {}
@act
def a_book_del(c, u, d, s): c.execute("delete from books where id=?", (d['id'],)); return {}
@act
def a_cat_save(c, u, d, s):
    need(d, 'name')
    if d.get('id'): c.execute("update categories set name=? where id=?", (d['name'].strip(), d['id']))
    else: c.execute("insert into categories(name) values(?)", (d['name'].strip(),))
    return {}
@act
def a_cat_del(c, u, d, s): c.execute("delete from categories where id=?", (d['id'],)); return {}
@act
def a_users(c, u, d, s):
    q = '%' + d.get('q', '').strip() + '%'
    return {'users': rows(c, "select id,username,role,full_name,student_code,class,email,phone,created,"
                             "(select count(*) from loans where user_id=users.id and status='Đang mượn') borrowing from users "
                             "where full_name like ? or username like ? or student_code like ? or email like ? order by id", [q] * 4)}
@act
def a_user_save(c, u, d, s):
    chk_user(d, not d.get('id')); need(d, 'username')
    role = 'admin' if d.get('role') == 'admin' else 'student'
    if d.get('id'):
        if int(d['id']) == u['id'] and role != 'admin': raise E('Không thể tự hạ quyền chính mình.')
        c.execute("update users set username=?,full_name=?,student_code=?,class=?,email=?,phone=?,role=? where id=?",
                  (d['username'].strip(), d['full_name'].strip(), d.get('student_code', '').strip() or None, d.get('class', ''), d['email'].strip().lower(), d.get('phone', ''), role, d['id']))
    else:
        c.execute("insert into users(username,pw,role,full_name,student_code,class,email,phone) values(?,?,?,?,?,?,?,?)",
                  (d['username'].strip(), hp(d['password']), role, d['full_name'].strip(), d.get('student_code', '').strip() or None, d.get('class', ''), d['email'].strip().lower(), d.get('phone', '')))
    return {}
@act
def a_user_reset(c, u, d, s): c.execute("update users set pw=? where id=?", (hp('123456'), d['id'])); return {}
@act
def a_user_del(c, u, d, s):
    if int(d['id']) == u['id']: raise E('Không thể xóa chính mình.')
    c.execute("delete from users where id=?", (d['id'],)); return {}
@act
def a_loans(c, u, d, s):
    sql, a = LQ, []
    if d.get('status'): sql += " where l.status=?"; a.append(d['status'])
    return {'loans': dec(rows(c, sql + " order by l.id desc", a))}
@act
def a_loan_act(c, u, d, s):
    l = c.execute("select * from loans where id=?", (d['id'],)).fetchone()
    if not l: raise E('Phiếu không tồn tại.')
    st, k = l['status'], d['act']
    if k == 'approve' and st == 'Chờ duyệt':
        if rows(c, BQ + " where b.id=?", (l['book_id'],))[0]['avail'] < 1: raise E('Sách đã hết, không thể duyệt.')
        c.execute("update loans set status='Đã duyệt' where id=?", (l['id'],))
    elif k == 'reject' and st == 'Chờ duyệt': c.execute("update loans set status='Từ chối' where id=?", (l['id'],))
    elif k == 'give' and st == 'Đã duyệt':
        c.execute("update loans set status='Đang mượn',borrow_date=?,due_date=? where id=?", (today(), (dt.date.today() + dt.timedelta(days=DAYS)).isoformat(), l['id']))
    elif k == 'return' and st == 'Đang mượn':
        late = max(0, (dt.date.today() - dt.date.fromisoformat(l['due_date'])).days)
        c.execute("update loans set status='Đã trả',return_date=?,fine=?,fine_paid=? where id=?", (today(), late * FINE, 0 if late else 1, l['id']))
    else: raise E('Thao tác không hợp lệ với trạng thái "%s".' % st)
    return {}
@act
def a_fines(c, u, d, s):
    return {'loans': [r for r in dec(rows(c, LQ + " where l.status in('Đang mượn','Đã trả') order by l.id desc")) if r['late'] > 0 or r['fine'] > 0], 'rate': FINE}
@act
def a_fine_pay(c, u, d, s): c.execute("update loans set fine_paid=1 where id=? and status='Đã trả'", (d['id'],)); return {}
@act
def a_ann_save(c, u, d, s):
    need(d, 'title', 'body')
    if d.get('id'): c.execute("update anns set title=?,body=? where id=?", (d['title'], d['body'], d['id']))
    else: c.execute("insert into anns(title,body) values(?,?)", (d['title'], d['body']))
    return {}
@act
def a_ann_del(c, u, d, s): c.execute("delete from anns where id=?", (d['id'],)); return {}
@act
def a_anns(c, u, d, s): return {'anns': rows(c, "select * from anns order by id desc")}
@act
def a_report(c, u, d, s):
    return {'monthly': rows(c, "select substr(req_date,1,7) m,count(*) n from loans where status not in('Từ chối','Đã hủy') group by m order by m desc limit 6")[::-1],
            'top': rows(c, "select b.title,count(*) n from loans l join books b on b.id=l.book_id where l.status not in('Từ chối','Đã hủy') group by b.id order by n desc,b.title limit 8"),
            'by_status': rows(c, "select status,count(*) n from loans group by status")}

# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    def log_message(s, *a): pass
    def out(s, code, body, ct='application/json'):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        s.send_response(code); s.send_header('Content-Type', ct + '; charset=utf-8'); s.send_header('Content-Length', str(len(b)))
        if getattr(s, 'ck', None): s.send_header('Set-Cookie', s.ck)
        s.end_headers(); s.wfile.write(b)
    def do_GET(s):
        s.out(200, open(os.path.join(D, 'index.html'), 'rb').read(), 'text/html')
    def do_POST(s):
        s.ck = None; a = s.path[5:] if s.path.startswith('/api/') else ''
        m = re.search(r'sid=(\w+)', s.headers.get('Cookie', '')); s.sid = m.group(1) if m else ''
        c = db()
        try:
            d = json.loads(s.rfile.read(int(s.headers.get('Content-Length', 0))) or b'{}')
            u = c.execute("select * from users where id=?", (SES.get(s.sid),)).fetchone()
            if a not in A: return s.out(404, {'error': 'Không tìm thấy'})
            if a not in ('login', 'register', 'forgot', 'me') and not u: return s.out(401, {'error': 'Vui lòng đăng nhập.'})
            if a.startswith('a_') and u['role'] != 'admin': return s.out(403, {'error': 'Bạn không có quyền thực hiện thao tác này.'})
            r = A[a](c, u, d, s); c.commit(); s.out(200, r)
        except E as e: c.rollback(); s.out(401 if a == 'me' else 400, {'error': str(e)})
        except sqlite3.IntegrityError as e:
            c.rollback(); m = str(e)
            names = {'username': 'Tên đăng nhập', 'student_code': 'Mã sinh viên', 'email': 'Email', 'code': 'Mã sách', 'name': 'Tên danh mục'}
            k = m.split('.')[-1] if 'UNIQUE' in m else ''
            s.out(400, {'error': (names.get(k, 'Giá trị') + ' đã tồn tại.') if k else 'Không thể xóa/lưu vì còn dữ liệu liên quan (ví dụ sách còn phiếu mượn).'})
        except Exception as e: c.rollback(); s.out(500, {'error': 'Lỗi hệ thống: %s' % e})
        finally: c.close()

if __name__ == '__main__':
    init(); print('Thư viện chạy tại http://localhost:8000  (Ctrl+C để dừng)')
    ThreadingHTTPServer(('0.0.0.0', 8000), H).serve_forever()
