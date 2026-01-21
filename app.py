from flask import Flask, request, session, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key_here"


# ================= DATABASE =================

def get_db_connection():
    conn = sqlite3.connect('library.db')
    conn.row_factory = sqlite3.Row
    return conn


# ================= HOME =================

@app.route('/')
def home():
    return redirect('/login')


# ================= REGISTER =================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form['username']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, password, role)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "Username already exists"
    conn.close()

    return redirect('/login')


# ================= LOGIN =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form['username']
    password = request.form['password']

    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()
    conn.close()

    if user is None:
        return "User not found"

    if not check_password_hash(user['password'], password):
        return "Wrong password"

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']

    return redirect('/books')


# ================= LOGOUT =================

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ================= BOOKS LIST =================

@app.route('/books')
def books():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()

    return render_template('books.html', books=books)


# ================= ADD BOOK (ADMIN) =================

@app.route('/add-book', methods=['GET', 'POST'])
def add_book():
    if session.get('role') != 'admin':
        return "Access denied"

    if request.method == 'GET':
        return render_template('add_book.html')

    title = request.form['title']
    author = request.form['author']
    quantity = request.form['quantity']

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)',
        (title, author, quantity)
    )
    conn.commit()
    conn.close()

    return redirect('/books')


# ================= BORROW BOOK =================

@app.route('/borrow/<int:book_id>')
def borrow(book_id):
    if session.get('role') != 'user':
        return "Only users can borrow books"

    user_id = session['user_id']

    conn = get_db_connection()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ?', (book_id,)
    ).fetchone()

    if book is None or book['quantity'] <= 0:
        conn.close()
        return "Book not available"

    conn.execute(
        'UPDATE books SET quantity = quantity - 1 WHERE id = ?', (book_id,)
    )

    conn.execute(
        'INSERT INTO borrowed_books (user_id, book_id, borrow_date) VALUES (?, ?, ?)',
        (user_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )

    conn.commit()
    conn.close()

    return redirect('/books')


# ================= MY BOOKS =================

@app.route('/mybooks')
def mybooks():
    if session.get('role') != 'user':
        return redirect('/login')

    conn = get_db_connection()
    books = conn.execute('''
        SELECT bb.id, b.title, b.author, bb.borrow_date, bb.return_date
        FROM borrowed_books bb
        JOIN books b ON bb.book_id = b.id
        WHERE bb.user_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template('mybooks.html', books=books)


# ================= RETURN BOOK =================

@app.route('/return/<int:borrow_id>')
def return_book(borrow_id):
    conn = get_db_connection()

    borrow = conn.execute(
        'SELECT * FROM borrowed_books WHERE id = ?', (borrow_id,)
    ).fetchone()

    if borrow:
        conn.execute(
            'UPDATE borrowed_books SET return_date = ? WHERE id = ?',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), borrow_id)
        )

        conn.execute(
            'UPDATE books SET quantity = quantity + 1 WHERE id = ?',
            (borrow['book_id'],)
        )

        conn.commit()

    conn.close()
    return redirect('/mybooks')


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)