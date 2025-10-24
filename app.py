from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/api/health')
def health():
    return jsonify({"status": "online", "message": "ConcursoMaster AI"})

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# NÃO PRECISA DO if __name__ == '__main__' - o Dockerfile cuida disso
