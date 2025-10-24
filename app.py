from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlalchemy as db
import os
import logging

# Configuração para produção
app = Flask(__name__)
CORS(app)

# Configurar logging
if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

# Conexão com banco
def get_db_connection():
    try:
        engine = db.create_engine("sqlite:///concurso.db")
        metadata = db.MetaData()
        metadata.reflect(bind=engine)
        app.logger.info("✅ Banco de dados conectado")
        return engine, metadata
    except Exception as e:
        app.logger.error(f"❌ Erro no banco: {e}")
        return None, None

engine, metadata = get_db_connection()

@app.route("/")
def root():
    return jsonify({
        "message": "ConcursoMaster AI Premium - ONLINE",
        "version": "2.0",
        "status": "success",
        "questoes_total": 295
    })

@app.route("/health")
def health_check():
    db_status = "connected" if engine else "disconnected"
    return jsonify({
        "status": "healthy",
        "database": db_status,
        "service": "ConcursoMaster API"
    })

@app.route("/materias")
def get_materias():
    if not engine:
        return jsonify({"materias": []})
    
    try:
        with engine.connect() as conn:
            questoes_table = metadata.tables['questoes']
            query = db.select([questoes_table.c.disciplina]).distinct()
            result = conn.execute(query)
            materias = [row[0] for row in result]
            return jsonify({"materias": materias})
    except Exception as e:
        app.logger.error(f"Erro em /materias: {e}")
        return jsonify({"materias": []})

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
            
            # Questões por disciplina
            disciplinas_query = db.select([
                questoes_table.c.disciplina,
                db.func.count()
            ]).group_by(questoes_table.c.disciplina)
            disciplinas_result = conn.execute(disciplinas_query)
            disciplinas_count = {row[0]: row[1] for row in disciplinas_result}
            
            return jsonify({
                "total_questoes": total_questoes,
                "questoes_por_materia": disciplinas_count
            })
    except Exception as e:
        app.logger.error(f"Erro em /dashboard-data: {e}")
        return jsonify({"error": str(e)})

@app.route("/questoes/<disciplina>")
def get_questoes(disciplina):
    if not engine:
        return jsonify({"error": "Banco indisponível"}), 500
    
    try:
        limit = request.args.get('limit', 10, type=int)
        with engine.connect() as conn:
            questoes_table = metadata.tables['questoes']
            query = db.select(questoes_table).where(
                questoes_table.c.disciplina == disciplina
            ).limit(limit)
            result = conn.execute(query)
            
            # Converter para formato padronizado
            questões = []
            for row in result:
                questao_dict = dict(row._mapping)
                questao_formatada = {
                    'id': questao_dict.get('id'),
                    'materia': questao_dict.get('disciplina'),
                    'assunto': questao_dict.get('assunto'),
                    'enunciado': questao_dict.get('enunciado'),
                    'alternativa_a': questao_dict.get('alt_a'),
                    'alternativa_b': questao_dict.get('alt_b'),
                    'alternativa_c': questao_dict.get('alt_c'),
                    'alternativa_d': questao_dict.get('alt_d'),
                    'alternativa_e': '',
                    'resposta_correta': questao_dict.get('gabarito'),
                    'explicacao': f"Dificuldade: {questao_dict.get('nivel', 'N/A')}. {questao_dict.get('dica_interpretacao', '')}"
                }
                questões.append(questao_formatada)
            
            return jsonify({
                "disciplina": disciplina,
                "quantidade": len(questões),
                "questoes": questões
            })
    except Exception as e:
        app.logger.error(f"Erro em /questoes: {e}")
        return jsonify({"error": str(e)}), 500

# Inicialização para desenvolvimento
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.logger.info(f"🚀 ConcursoMaster Flask - Porta: {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
