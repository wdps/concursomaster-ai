from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlalchemy as db
import os

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Conexão com banco
def conectar_banco():
    try:
        engine = db.create_engine("sqlite:///concurso.db")
        metadata = db.MetaData()
        metadata.reflect(bind=engine)
        print("✅ Banco de dados conectado")
        return engine, metadata
    except Exception as e:
        print(f"❌ Erro no banco: {e}")
        return None, None

engine, metadata = conectar_banco()

# ROTA PRINCIPAL - SERVIR ARQUIVOS ESTÁTICOS
@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory('.', path)

# API ROUTES
@app.route("/api/health")
def health():
    return jsonify({"status": "healthy", "message": "ConcursoMaster AI Online"})

@app.route("/api/materias")
def materias():
    if not engine:
        return jsonify({"materias": []})
    
    try:
        with engine.connect() as conn:
            tabela = metadata.tables['questoes']
            query = db.select([tabela.c.disciplina]).distinct()
            result = conn.execute(query)
            materias_lista = [row[0] for row in result]
            return jsonify({"materias": materias_lista})
    except Exception as e:
        return jsonify({"materias": [], "error": str(e)})

@app.route("/api/dashboard-data")
def dashboard():
    if not engine:
        return jsonify({"error": "Banco indisponível"})
    
    try:
        with engine.connect() as conn:
            tabela = metadata.tables['questoes']
            
            # Total de questões
            total = conn.execute(db.select([db.func.count()]).select_from(tabela)).scalar()
            
            # Por disciplina
            query = db.select([tabela.c.disciplina, db.func.count()]).group_by(tabela.c.disciplina)
            result = conn.execute(query)
            por_materia = {row[0]: row[1] for row in result}
            
            return jsonify({
                "total_questoes": total,
                "questoes_por_materia": por_materia
            })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/questoes/<disciplina>")
def questao(disciplina):
    if not engine:
        return jsonify({"error": "Banco indisponível"})
    
    try:
        limit = request.args.get('limit', 10, type=int)
        with engine.connect() as conn:
            tabela = metadata.tables['questoes']
            query = db.select(tabela).where(tabela.c.disciplina == disciplina).limit(limit)
            result = conn.execute(query)
            
            questoes = []
            for row in result:
                questoes.append({
                    'id': row.id,
                    'materia': row.disciplina,
                    'enunciado': row.enunciado,
                    'alternativa_a': row.alt_a,
                    'alternativa_b': row.alt_b,
                    'alternativa_c': row.alt_c,
                    'alternativa_d': row.alt_d,
                    'resposta_correta': row.gabarito
                })
            
            return jsonify({
                "disciplina": disciplina,
                "quantidade": len(questoes),
                "questoes": questoes
            })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Iniciando servidor na porta {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
