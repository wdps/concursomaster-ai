from flask import Flask, jsonify, send_from_directory
import os
import sqlite3

app = Flask(__name__)

# Rota principal - servir o frontend
@app.route("/")
def home():
    return send_from_directory('.', 'index.html')

# Rota para arquivos estáticos
@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory('.', filename)

# API SIMPLES - SEM BANCO COMPLEXO
@app.route("/api/health")
def health():
    return jsonify({"status": "online", "message": "ConcursoMaster AI Funcionando!"})

@app.route("/api/materias")
def materias():
    return jsonify({
        "materias": [
            "Direito Administrativo",
            "Direito Constitucional", 
            "Português",
            "Raciocínio Lógico",
            "Informática",
            "Direito Penal",
            "Direito Processual Penal",
            "Legislação Especial",
            "Direito Humanos",
            "Administração Pública",
            "Controle Externo",
            "Ética",
            "Matemática",
            "Realidade Brasileira"
        ]
    })

@app.route("/api/dashboard-data")
def dashboard():
    return jsonify({
        "total_questoes": 295,
        "questoes_por_materia": {
            "Direito Administrativo": 33,
            "Direito Constitucional": 29,
            "Português": 27,
            "Raciocínio Lógico": 24,
            "Informática": 22,
            "Direito Penal": 21,
            "Direito Processual Penal": 19,
            "Legislação Especial": 18,
            "Direito Humanos": 17,
            "Administração Pública": 16,
            "Controle Externo": 15,
            "Ética": 14,
            "Matemática": 13,
            "Realidade Brasileira": 12
        }
    })

@app.route("/api/questoes/<materia>")
def questões(materia):
    # Questões de exemplo para demonstração
    questões_exemplo = [
        {
            "id": 1,
            "materia": materia,
            "enunciado": "De acordo com a Constituição Federal, a administração pública direta e indireta obedecerá aos princípios de:",
            "alternativa_a": "legalidade, impessoalidade, moralidade, publicidade e eficiência",
            "alternativa_b": "legalidade, legitimidade, moralidade, publicidade e economicidade", 
            "alternativa_c": "legalidade, impessoalidade, moralidade, publicidade e economicidade",
            "alternativa_d": "legalidade, legitimidade, moralidade, publicidade e eficiência",
            "resposta_correta": "A"
        },
        {
            "id": 2, 
            "materia": materia,
            "enunciado": "O ato administrativo que extingue um cargo público declarado desnecessário é classificado como:",
            "alternativa_a": "ato administrativo normativo",
            "alternativa_b": "ato administrativo ordinatório",
            "alternativa_c": "ato administrativo negocial",
            "alternativa_d": "ato administrativo punitivo",
            "resposta_correta": "B"
        }
    ]
    return jsonify({
        "disciplina": materia,
        "quantidade": len(questões_exemplo),
        "questoes": questões_exemplo
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Servidor iniciado na porta {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
