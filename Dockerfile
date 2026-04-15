# Gunakan image Python versi ringan
FROM python:3.9-slim

# Set working directory di dalam container
WORKDIR /app

# Copy file requirements.txt ke dalam container
COPY requirements.txt .

# Install semua library yang dibutuhkan
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh file aplikasi ke dalam container
COPY . .

# Ekspos port 5000 agar bisa diakses dari luar container
EXPOSE 5000

# Perintah untuk menjalankan aplikasi
CMD ["python", "app.py"]