FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# REMOVER GUNICORN SE EXISTIR
RUN pip uninstall -y gunicorn || true

COPY . .

# FORÇAR A PORTA 8080 NO FLASK
ENV PORT=8080

# COMANDO QUE SUBSTITUI O GUNICORN
CMD ["python", "-c", "from app import app; import os; app.run(host='0.0.0.0', port=8080, debug=False)"]
