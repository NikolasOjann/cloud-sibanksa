import os
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, flash
import boto3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "kunci_rahasia_si_banksa_uts"

# ==========================================
# KONFIGURASI AWS S3
# ==========================================
S3_BUCKET = "sibanksa-bucket" 
S3_REGION = "us-east-1" 
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

s3_client = boto3.client(
    's3', region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# ==========================================
# KONFIGURASI AWS RDS (MYSQL)
# ==========================================
DB_HOST = os.environ.get("DB_HOST")
DB_USER = "admin"
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = "sibanksa_db"

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def upload_to_s3(file_obj):
    if file_obj and file_obj.filename != '':
        filename = secure_filename(file_obj.filename)
        try:
            s3_client.upload_fileobj(
                file_obj, S3_BUCKET, filename,
                ExtraArgs={"ContentType": file_obj.content_type}
            )
            # Format URL khusus untuk us-east-1 agar tidak terkena Redirect
            return f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"
        except Exception as e:
            print("Error S3:", e)
            return None
    return None

# ==========================================
# INISIALISASI TABEL DATABASE OTOMATIS
# ==========================================
@app.before_request
def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Buat tabel setoran
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS setoran (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nama VARCHAR(100), jenis VARCHAR(50),
                    berat FLOAT, saldo_didapat INT, foto_url VARCHAR(255)
                )
            """)
            # Buat tabel iuran
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS iuran (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nama VARCHAR(100), bulan VARCHAR(50),
                    bukti_url VARCHAR(255), status VARCHAR(50)
                )
            """)
        conn.commit()
        conn.close()
        print("Database initialized successfully!")
    except Exception as e:
        print("Gagal inisialisasi database:", e)

# Jalankan inisialisasi setiap kali aplikasi dimulai
init_db()

# ==========================================
# ROUTING APLIKASI
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['role'] = 'admin'
            session['nama'] = 'Pengurus RT (Admin)'
            return redirect(url_for('dashboard'))
        elif username == 'warga' and password == 'warga123':
            session['role'] = 'warga'
            session['nama'] = 'Keluarga Bpk. Budi'
            return redirect(url_for('dashboard'))
        else:
            flash("Username atau Password salah!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    if 'role' not in session: return redirect(url_for('login'))
    
    db_setoran = []
    db_iuran = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM setoran")
            db_setoran = cursor.fetchall()
            cursor.execute("SELECT * FROM iuran")
            db_iuran = cursor.fetchall()
        conn.close()
    except:
        pass # Handle error saat lokal

    total_kas_sampah = sum(s['saldo_didapat'] for s in db_setoran)
    total_iuran = len(db_iuran) * 25000

    leaderboard_dict = {}
    for s in db_setoran:
        nama = s['nama']
        leaderboard_dict[nama] = leaderboard_dict.get(nama, 0) + s['berat']
    leaderboard = sorted(leaderboard_dict.items(), key=lambda x: x[1], reverse=True)

    return render_template('dashboard.html', kas_sampah=total_kas_sampah, 
                           kas_iuran=total_iuran, leaderboard=leaderboard,
                           setoran=db_setoran, iuran=db_iuran)

@app.route('/setor', methods=['GET', 'POST'])
def setor():
    if 'role' not in session or session['role'] != 'admin': return "Akses Ditolak!"
    if request.method == 'POST':
        nama = request.form['nama']
        jenis = request.form['jenis']
        berat = float(request.form['berat'])
        foto = request.files['foto']
        foto_url = upload_to_s3(foto) or ""
        saldo = int(berat * 2000)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO setoran (nama, jenis, berat, saldo_didapat, foto_url) VALUES (%s, %s, %s, %s, %s)",
                (nama, jenis, berat, saldo, foto_url)
            )
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    return render_template('setor.html')

@app.route('/iuran', methods=['GET', 'POST'])
def iuran():
    if 'role' not in session or session['role'] != 'warga': return "Akses Ditolak!"
    if request.method == 'POST':
        nama = session['nama']
        bulan = request.form['bulan']
        bukti = request.files['bukti']
        bukti_url = upload_to_s3(bukti) or ""

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO iuran (nama, bulan, bukti_url, status) VALUES (%s, %s, %s, 'Menunggu Validasi Admin')",
                (nama, bulan, bukti_url)
            )
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    return render_template('iuran.html')

@app.route('/validasi_iuran/<int:iuran_id>', methods=['POST'])
def validasi_iuran(iuran_id):
    if 'role' not in session or session['role'] != 'admin': return "Akses Ditolak!"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE iuran SET status='Lunas / Tervalidasi' WHERE id=%s", (iuran_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)