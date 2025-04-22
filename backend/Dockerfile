# ─────────────────────────────────────────────
# 📦 Base Image
# ─────────────────────────────────────────────
FROM python:3.12-slim

# ─────────────────────────────────────────────
# 🔧 Environment Configuration
# ─────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# ─────────────────────────────────────────────
# 📁 Working Directory
# ─────────────────────────────────────────────
WORKDIR /app

# ─────────────────────────────────────────────
# 📥 Dependencies
# ─────────────────────────────────────────────
COPY ./requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────
# 📂 App Files
# ─────────────────────────────────────────────
COPY . /app

# ─────────────────────────────────────────────
# 🚀 Startup Command
# ─────────────────────────────────────────────
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
