$appFinal = @'
from flask import Flask, jsonify, send_from_directory, request
import os
import sqlite3

app = Flask(__name__)

# ROTA PRINCIPAL
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# SERVIR ARQUIVOS ESTÁTICOS
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# API SIMPLES E FUNCIONAL
@app.route('/api/health')
def health():
    return jsonify({"status": "online", "message": "ConcursoMaster AI"})

@app.route('/api/materias')
def materias():
    return jsonify({
        "materias": [
            "Direito Administrativo", "Direito Constitucional", 
            "Português", "Raciocínio Lógico", "Informática"
        ]
    })

@app.route('/api/dashboard-data')
def dashboard():
    return jsonify({
        "total_questoes": 295,
        "questoes_por_materia": {
            "Direito Administrativo": 33,
            "Direito Constitucional": 29,
            "Português": 27,
            "Raciocínio Lógico": 24,
            "Informática": 22
        }
    })

@app.route('/api/questoes/<materia>')
def questões(materia):
    return jsonify({
        "disciplina": materia,
        "quantidade": 2,
        "questoes": [
            {
                "id": 1,
                "materia": materia,
                "enunciado": f"Questão de exemplo sobre {materia} - Princípios fundamentais:",
                "alternativa_a": "Alternativa A correta",
                "alternativa_b": "Alternativa B incorreta",
                "alternativa_c": "Alternativa C incorreta",
                "alternativa_d": "Alternativa D incorreta",
                "resposta_correta": "A"
            }
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 Servidor iniciado na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
'@

$appFinal | Out-File -FilePath "app.py" -Encoding utf8 -Force
Write-Host "✅ App.py simplificado e funcional!" -ForegroundColor Green
