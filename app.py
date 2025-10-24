from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlalchemy as db
import os
from datetime import datetime
import logging

app = Flask(__name__)
CORS(app)

# Configuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conexão com o banco de dados
try:
    engine = db.create_engine("sqlite:///concurso.db")
    metadata = db.MetaData()
    metadata.reflect(bind=engine)
    logger.info("✅ Banco de dados conectado")
except Exception as e:
    logger.error(f"❌ Erro no banco: {e}")
    engine = None

@app.route("/")
def root():
    return jsonify({
        "message": "ConcursoMaster AI Premium - ONLINE",
        "version": "2.0",
        "status": "success"
    })

@app.route("/health")
def health_check():
    db_status = "connected" if engine else "disconnected"
    return jsonify({
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/questoes/<materia>")
def get_questoes(materia):
    if not engine:
        return jsonify({"error": "Banco indisponível"}), 500
    
    try:
        limit = request.args.get('limit', 10, type=int)
        with engine.connect() as conn:
            questoes_table = metadata.tables['questoes']
            query = db.select(questoes_table).where(
                questoes_table.c.materia == materia
            ).limit(limit)
            result = conn.execute(query)
            questões = [dict(row._mapping) for row in result]
            
            return jsonify({
                "materia": materia,
                "quantidade": len(questões),
                "questoes": questões
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/dashboard-data")
def dashboard_data():
    if not engine:
        return jsonify({"error": "Banco indisponível"})
    
    try:
        with engine.connect() as conn:
            questoes_table = metadata.tables['questoes']
            
            # Total de questões
            total_query = db.select([db.func.count()]).select_from(questoes_table)
            total_questoes = conn.execute(total_query).scalar()
            
            # Questões por matéria
            materias_query = db.select([
                questoes_table.c.materia, 
                db.func.count()
            ]).group_by(questoes_table.c.materia)
            materias_result = conn.execute(materias_query)
            materias_count = {row[0]: row[1] for row in materias_result}
            
            return jsonify({
                "total_questoes": total_questoes,
                "questoes_por_materia": materias_count,
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/materias")
def get_materias():
    if not engine:
        return jsonify({"materias": []})
    
    try:
        with engine.connect() as conn:
            questoes_table = metadata.tables['questoes']
            query = db.select([questoes_table.c.materia]).distinct()
            result = conn.execute(query)
            materias = [row[0] for row in result]
            return jsonify({"materias": materias})
    except Exception as e:
        return jsonify({"materias": []})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 ConcursoMaster Flask - Porta: {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
