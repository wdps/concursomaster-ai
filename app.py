from flask import Flask, jsonify, send_from_directory
import os
import sqlite3
from pathlib import Path

app = Flask(__name__)

# CONFIGURAÇÃO CORRETA PARA SERVIR ARQUIVOS ESTÁTICOS
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# CONEXÃO SIMPLES COM BANCO
def get_db_connection():
    try:
        conn = sqlite3.connect('concurso.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"❌ Erro no banco: {e}")
        return None

# API ROTAS - SIMPLES E DIRETAS
@app.route('/api/health')
def health():
    return jsonify({
        "status": "online", 
        "message": "ConcursoMaster AI funcionando!",
        "timestamp": "2024-01-01 12:00:00"
    })

@app.route('/api/materias')
def materias():
    conn = get_db_connection()
    if not conn:
        # Fallback se banco não conectar
        return jsonify({
            "materias": [
                "Direito Administrativo", "Direito Constitucional", "Português",
                "Raciocínio Lógico", "Informática", "Direito Penal",
                "Direito Processual Penal", "Legislação Especial", "Direito Humanos",
                "Administração Pública", "Controle Externo", "Ética",
                "Matemática", "Realidade Brasileira"
            ]
        })
    
    try:
        materias = conn.execute(
            'SELECT DISTINCT disciplina FROM questões ORDER BY disciplina'
        ).fetchall()
        conn.close()
        
        materias_lista = [row['disciplina'] for row in materias]
        return jsonify({"materias": materias_lista})
    except Exception as e:
        conn.close()
        return jsonify({"materias": [], "error": str(e)})

@app.route('/api/dashboard-data')
def dashboard_data():
    conn = get_db_connection()
    if not conn:
        # Fallback com dados estáticos
        return jsonify({
            "total_questoes": 295,
            "questoes_por_materia": {
                "Direito Administrativo": 33, "Direito Constitucional": 29,
                "Português": 27, "Raciocínio Lógico": 24, "Informática": 22,
                "Direito Penal": 21, "Direito Processual Penal": 19,
                "Legislação Especial": 18, "Direito Humanos": 17,
                "Administração Pública": 16, "Controle Externo": 15,
                "Ética": 14, "Matemática": 13, "Realidade Brasileira": 12
            }
        })
    
    try:
        # Total de questões
        total = conn.execute('SELECT COUNT(*) as count FROM questões').fetchone()['count']
        
        # Questões por matéria
        materias_count = conn.execute('''
            SELECT disciplina, COUNT(*) as count 
            FROM questões 
            GROUP BY disciplina 
            ORDER BY count DESC
        ''').fetchall()
        
        conn.close()
        
        questoes_por_materia = {row['disciplina']: row['count'] for row in materias_count}
        
        return jsonify({
            "total_questoes": total,
            "questoes_por_materia": questoes_por_materia
        })
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)})

@app.route('/api/questoes/<disciplina>')
def get_questoes(disciplina):
    conn = get_db_connection()
    if not conn:
        # Fallback com questões de exemplo
        return jsonify({
            "disciplina": disciplina,
            "quantidade": 2,
            "questoes": [
                {
                    "id": 1,
                    "materia": disciplina,
                    "enunciado": "De acordo com a Constituição Federal, a administração pública direta e indireta obedecerá aos princípios de:",
                    "alternativa_a": "legalidade, impessoalidade, moralidade, publicidade e eficiência",
                    "alternativa_b": "legalidade, legitimidade, moralidade, publicidade e economicidade",
                    "alternativa_c": "legalidade, impessoalidade, moralidade, publicidade e economicidade",
                    "alternativa_d": "legalidade, legitimidade, moralidade, publicidade e eficiência",
                    "resposta_correta": "A"
                },
                {
                    "id": 2,
                    "materia": disciplina,
                    "enunciado": "O ato administrativo que extingue um cargo público declarado desnecessário é classificado como:",
                    "alternativa_a": "ato administrativo normativo",
                    "alternativa_b": "ato administrativo ordinatório",
                    "alternativa_c": "ato administrativo negocial",
                    "alternativa_d": "ato administrativo punitivo",
                    "resposta_correta": "B"
                }
            ]
        })
    
    try:
        limit = int(request.args.get('limit', 10))
        questões = conn.execute('''
            SELECT id, disciplina, enunciado, alt_a, alt_b, alt_c, alt_d, gabarito
            FROM questões 
            WHERE disciplina = ? 
            LIMIT ?
        ''', (disciplina, limit)).fetchall()
        
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
        conn.close()
        return jsonify({"error": str(e)})

# IMPORTANTE: Adicionar o import request que estava faltando
from flask import request

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Servidor iniciando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
