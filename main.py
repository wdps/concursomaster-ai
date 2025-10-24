import sqlalchemy as db
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uvicorn

# Configuração simplificada para deploy
GEMINI_AVAILABLE = False

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ConcursoMaster AI Premium",
    description="Sistema inteligente de estudos para concursos públicos",
    version="2.0"
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexão com o banco de dados
try:
    engine = db.create_engine("sqlite:///concurso.db")
    metadata = db.MetaData()
    metadata.reflect(bind=engine)
    logger.info("✅ Banco de dados conectado com sucesso")
except Exception as e:
    logger.error(f"❌ Erro ao conectar com banco de dados: {e}")
    engine = None

# Modelos Pydantic
class Questao(BaseModel):
    id: int
    materia: str
    enunciado: str
    alternativa_a: str
    alternativa_b: str
    alternativa_c: str
    alternativa_d: str
    alternativa_e: str
    resposta_correta: str
    explicacao: Optional[str] = None

class SimuladoRequest(BaseModel):
    materia: str
    quantidade: int = 10

# Rotas básicas
@app.get("/")
async def root():
    return {"message": "ConcursoMaster AI Premium - Sistema Online", "version": "2.0.0"}

@app.get("/health")
async def health_check():
    db_status = "connected" if engine else "disconnected"
    return {
        "status": "healthy", 
        "service": "ConcursoMaster AI",
        "database": db_status,
        "gemini_ai": "unavailable",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/questoes/{materia}")
async def get_questoes(materia: str, limit: int = 10):
    if not engine:
        raise HTTPException(status_code=500, detail="Banco de dados não disponível")
    
    try:
        with engine.connect() as conn:
            questoes_table = metadata.tables['questoes']
            query = db.select(questoes_table).where(questoes_table.c.materia == materia).limit(limit)
            result = conn.execute(query)
            questões = [dict(row._mapping) for row in result]
            
            return {
                "materia": materia,
                "quantidade": len(questões),
                "questoes": questões,
                "gemini_available": GEMINI_AVAILABLE
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar questões: {str(e)}")

@app.get("/dashboard-data")
async def get_dashboard_data():
    if not engine:
        return {"error": "Banco de dados não disponível"}
    
    try:
        with engine.connect() as conn:
            # Contar questões por matéria
            questoes_table = metadata.tables['questoes']
            query = db.select([questoes_table.c.materia, db.func.count()]).group_by(questoes_table.c.materia)
            result = conn.execute(query)
            materias_count = {row[0]: row[1] for row in result}
            
            # Total de questões
            total_query = db.select([db.func.count()]).select_from(questoes_table)
            total_result = conn.execute(total_query)
            total_questoes = total_result.scalar()
            
            return {
                "total_questoes": total_questoes,
                "questoes_por_materia": materias_count,
                "gemini_available": GEMINI_AVAILABLE,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {"error": f"Erro ao buscar dados do dashboard: {str(e)}"}

@app.get("/materias")
async def get_materias():
    if not engine:
        return {"materias": []}
    
    try:
        with engine.connect() as conn:
            questoes_table = metadata.tables['questoes']
            query = db.select([questoes_table.c.materia]).distinct()
            result = conn.execute(query)
            materias = [row[0] for row in result]
            
            return {"materias": materias}
    except Exception as e:
        return {"materias": []}

if __name__ == "__main__":
    import uvicorn
    import os
    
    print("\n" + "="*60)
    print("🚀 CONCURSOMASTER AI PREMIUM v2.0 - SERVIDOR INICIANDO")
    print("="*60)
    print("🔧 Google Gemini AI: ❌ DESATIVADO (modo simplificado)")
    
    # CONFIGURAÇÕES PARA PRODUÇÃO
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8000))
    
    print(f"🌐 Servidor rodando em: http://{host}:{port}")
    print("📚 API Documentation: /docs")
    print("🔍 Health Check: /health")
    print("="*60 + "\n")
    
    uvicorn.run(
        app, 
        host=host,
        port=port,
        log_level="info"
    )
