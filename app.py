from flask import Flask, jsonify, send_from_directory, request
import os
import sqlite3
from pathlib import Path

app = Flask(__name__)

# ROTA PRINCIPAL
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# SERVIR ARQUIVOS ESTÁTICOS
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# API HEALTH CHECK
@app.route('/api/health')
def health():
    return jsonify({
        "status": "online", 
        "message": "ConcursoMaster AI Premium",
        "version": "2.0"
    })

# API MATÉRIAS
@app.route('/api/materias')
def materias():
    try:
        conn = sqlite3.connect('concurso.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT disciplina FROM questões")
        materias = cursor.fetchall()
        
        materias_lista = [row['disciplina'] for row in materias]
        conn.close()
        
        return jsonify({"materias": materias_lista})
    except Exception as e:
        return jsonify({"materias": [
            "Direito Administrativo", "Direito Constitucional", "Português",
            "Raciocínio Lógico", "Informática", "Direito Penal"
        ]})

# API DASHBOARD
@app.route('/api/dashboard-data')
def dashboard():
    try:
        conn = sqlite3.connect('concurso.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Total de questões
        cursor.execute("SELECT COUNT(*) as total FROM questões")
        total = cursor.fetchone()['total']
        
        # Questões por matéria
        cursor.execute('''
            SELECT disciplina, COUNT(*) as count 
            FROM questões 
            GROUP BY disciplina
        ''')
        materias_data = cursor.fetchall()
        
        materias_dict = {row['disciplina']: row['count'] for row in materias_data}
        conn.close()
        
        return jsonify({
            "total_questoes": total,
            "questoes_por_materia": materias_dict
        })
    except Exception as e:
        return jsonify({
            "total_questoes": 295,
            "questoes_por_materia": {
                "Direito Administrativo": 33, "Direito Constitucional": 29,
                "Português": 27, "Raciocínio Lógico": 24
            }
        })

# API QUESTÕES
@app.route('/api/questoes/<disciplina>')
def questao(disciplina):
    try:
        limit = request.args.get('limit', 10, type=int)
        
        conn = sqlite3.connect('concurso.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, disciplina, enunciado, alt_a, alt_b, alt_c, alt_d, gabarito
            FROM questões 
            WHERE disciplina = ? 
            LIMIT ?
        ''', (disciplina, limit))
        
        questões = cursor.fetchall()
        conn.close()
        
        questões_lista = []
        for row in questões:
            questões_lista.append({
                "id": row['id'],
                "materia": row['disciplina'],
                "enunciado": row['enunciado'],
                "alternativa_a": row['alt_a'],
                "alternativa_b": row['alt_b'],
                "alternativa_c": row['alt_c'],
                "alternativa_d": row['alt_d'],
                "resposta_correta": row['gabarito']
            })
        
        return jsonify({
            "disciplina": disciplina,
            "quantidade": len(questões_lista),
            "questoes": questões_lista
        })
    except Exception as e:
        return jsonify({
            "disciplina": disciplina,
            "quantidade": 2,
            "questoes": [
                {
                    "id": 1,
                    "materia": disciplina,
                    "enunciado": f"Questão de exemplo para {disciplina} - De acordo com a doutrina majoritária...",
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
    print(f"🚀 ConcursoMaster AI iniciando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
