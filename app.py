import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import boto3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "kunci_rahasia_si_banksa_uts" # Wajib untuk session

# ==========================================
# KONFIGURASI AWS S3 (MENGGUNAKAN ENV VARIABLES)
# ==========================================
S3_BUCKET = "sibanksa-bucket" # Nama bucket boleh tetap di sini
S3_REGION = "us-east-1" 

# MENGAMBIL KUNCI DARI ENVIRONMENT SECARA AMAN
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

s3_client = boto3.client(
    's3',
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# ==========================================
# DATABASE DUMMY (List Python)
# ==========================================
db_setoran = [] 
db_iuran = []   
id_iuran_counter = 1

def upload_to_s3(file_obj):
    if file_obj and file_obj.filename != '':
        filename = secure_filename(file_obj.filename)
        try:
            s3_client.upload_fileobj(
                file_obj,
                S3_BUCKET,
                filename,
                ExtraArgs={"ContentType": file_obj.content_type}
            )
            return f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{filename}"
        except Exception as e:
            print("Error S3:", e)
            return None
    return None

# ==========================================
# ROUTING APLIKASI
# ==========================================

# --- FITUR LOGIN & LOGOUT ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Hardcode login untuk keperluan UTS
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
    session.clear() # Hapus sesi saat logout
    return redirect(url_for('login'))

# --- FITUR 3: Dashboard Transparansi ---
@app.route('/')
def dashboard():
    # Cek apakah user sudah login
    if 'role' not in session:
        return redirect(url_for('login'))

    total_kas_sampah = sum(s['berat'] * 2000 for s in db_setoran)
    total_iuran = len(db_iuran) * 25000

    leaderboard_dict = {}
    for s in db_setoran:
        nama = s['nama']
        leaderboard_dict[nama] = leaderboard_dict.get(nama, 0) + s['berat']
    
    leaderboard = sorted(leaderboard_dict.items(), key=lambda x: x[1], reverse=True)

    return render_template('dashboard.html', 
                           kas_sampah=total_kas_sampah, 
                           kas_iuran=total_iuran, 
                           leaderboard=leaderboard,
                           setoran=db_setoran,
                           iuran=db_iuran)

# --- FITUR 1: Form Setoran (HANYA ADMIN) ---
@app.route('/setor', methods=['GET', 'POST'])
def setor():
    if 'role' not in session or session['role'] != 'admin':
        return "Akses Ditolak! Hanya Pengurus RT (Admin) yang bisa mencatat setoran."

    if request.method == 'POST':
        nama = request.form['nama']
        jenis = request.form['jenis']
        berat = float(request.form['berat'])
        foto = request.files['foto']

        foto_url = upload_to_s3(foto) or ""

        db_setoran.append({
            'nama': nama,
            'jenis': jenis,
            'berat': berat,
            'saldo_didapat': berat * 2000,
            'foto_url': foto_url
        })
        return redirect(url_for('dashboard'))

    return render_template('setor.html')

# --- FITUR 2: Bayar Iuran (HANYA WARGA) ---
# UPDATE: Tambahkan ID saat menyimpan data
@app.route('/iuran', methods=['GET', 'POST'])
def iuran():
    global id_iuran_counter # Gunakan variabel global
    
    if 'role' not in session or session['role'] != 'warga':
        return "Akses Ditolak! Form ini khusus untuk Warga."

    if request.method == 'POST':
        nama = session['nama']
        bulan = request.form['bulan']
        bukti = request.files['bukti']

        bukti_url = upload_to_s3(bukti) or ""

        db_iuran.append({
            'id': id_iuran_counter, # Sistem mencatat ID unik
            'nama': nama,
            'bulan': bulan,
            'bukti_url': bukti_url,
            'status': 'Menunggu Validasi Admin'
        })
        id_iuran_counter += 1 # Tambah counter untuk iuran berikutnya
        return redirect(url_for('dashboard'))

    return render_template('iuran.html')

# --- FITUR BARU: Validasi Iuran (HANYA ADMIN) ---
@app.route('/validasi_iuran/<int:iuran_id>', methods=['POST'])
def validasi_iuran(iuran_id):
    # Pastikan hanya admin yang bisa memvalidasi
    if 'role' not in session or session['role'] != 'admin':
        return "Akses Ditolak!"

    # Cari data iuran berdasarkan ID, lalu ubah statusnya
    for i in db_iuran:
        if i.get('id') == iuran_id:
            i['status'] = 'Lunas / Tervalidasi'
            break

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=500)