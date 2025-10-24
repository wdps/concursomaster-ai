from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlalchemy as db
import os
from datetime import datetime
import logging
import csv
import io

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

# ROTA PARA IMPORTAR QUESTÕES - COM NOMES CORRETOS
@app.route("/importar-questoes", methods=["POST"])
def importar_questoes():
    if not engine:
        return jsonify({"error": "Banco indisponível"}), 500
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Nome de arquivo vazio"}), 400
        
        if file and file.filename.endswith('.csv'):
            # Ler CSV
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream, delimiter=';')
            
            questões_table = metadata.tables['questoes']
            questões = []
            
            for row in csv_input:
                questao = {
                    'disciplina': row.get('disciplina', 'geral'),
                    'assunto': row.get('assunto', ''),
                    'enunciado': row.get('enunciado', ''),
                    'alt_a': row.get('alt_a', ''),
                    'alt_b': row.get('alt_b', ''),
                    'alt_c': row.get('alt_c', ''),
                    'alt_d': row.get('alt_d', ''),
                    'gabarito': row.get('gabarito', '').upper(),
                    'just_a': row.get('just_a', ''),
                    'just_b': row.get('just_b', ''),
                    'just_c': row.get('just_c', ''),
                    'just_d': row.get('just_d', ''),
                    'dica_interpretacao': row.get('dica_interpretacao', ''),
                    'formula_aplicavel': row.get('formula_aplicavel', ''),
                    'nivel': row.get('dificuldade', 'Médio'),
                    'data_criacao': datetime.now().isoformat(),
                    'ativo': True
                }
                questões.append(questao)
            
            # Inserir no banco
            with engine.connect() as conn:
                conn.execute(questões_table.insert(), questões)
                conn.commit()
            
            return jsonify({
                "message": f"✅ {len(questões)} questões importadas com sucesso!",
                "quantidade": len(questões),
                "materias_importadas": list(set([q['disciplina'] for q in questões]))
            })
        else:
            return jsonify({"error": "Arquivo deve ser CSV"}), 400
            
    except Exception as e:
        return jsonify({"error": f"Erro na importação: {str(e)}"}), 500

# ATUALIZAR ROTAS PARA USAR OS NOMES CORRETOS
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
                # Formatar para o frontend
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
            
            # Questões por disciplina
            disciplinas_query = db.select([
                questoes_table.c.disciplina, 
                db.func.count()
            ]).group_by(questoes_table.c.disciplina)
            disciplinas_result = conn.execute(disciplinas_query)
            disciplinas_count = {row[0]: row[1] for row in disciplinas_result}
            
            return jsonify({
                "total_questoes": total_questoes,
                "questoes_por_materia": disciplinas_count,
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
            query = db.select([questoes_table.c.disciplina]).distinct()
            result = conn.execute(query)
            materias = [row[0] for row in result]
            return jsonify({"materias": materias})
    except Exception as e:
        return jsonify({"materias": []})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 ConcursoMaster Flask - Porta: {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
