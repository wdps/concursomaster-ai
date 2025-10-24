import sqlalchemy as db
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import os 
from contextlib import asynccontextmanager 
import random 
import time 
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from math import ceil
import re

# --- CONFIGURAÇÃO DO GOOGLE GEMINI AI ---
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# --- CONFIGURAÇÕES GERAIS ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_NAME = 'concurso.db'
TB_QUESTOES = 'questoes'
TB_ESTATISTICAS = 'estatisticas'
TB_SIMULADOS_FEITOS = 'simulados_feitos'
NOME_USUARIO_RANKING = "Wanderson de Paula"

# --- PESOS DAS DISCIPLINAS ---
SIMULADO_PESOS_PONTUACAO = {
    "Língua Portuguesa": 1.5,
    "Matemática": 1.0,
    "Raciocínio Lógico": 1.0, 
    "Direito Administrativo": 2.0,
    "Direito Constitucional": 2.0,
    "Psicologia": 1.0,
    "Atualidades": 1.0,
    "Conhecimentos Bancários": 1.5,
    "Informática": 1.0,
    "Matemática Financeira": 1.0,
    "Vendas e Negociação": 1.0,
    "Português e Redação Oficial": 1.5,
    "Legislação": 2.0,
    "Geral": 1.0 
}

SIMULADO_DISTRIBUTION_PERCENT = {
    "Língua Portuguesa": 0.25, 
    "Matemática": 0.10,
    "Raciocínio Lógico": 0.05, 
    "Direito Administrativo": 0.10,
    "Direito Constitucional": 0.10,
    "Informática": 0.05,
    "Conhecimentos Bancários": 0.05,
    "Matemática Financeira": 0.05,
    "Vendas e Negociação": 0.05,
    "Psicologia": 0.05,
    "Atualidades": 0.05,
}

# --- MODELOS PYDANTIC ---
class RedacaoRequest(BaseModel):
    texto: str
    tema: str
    tipo_prova: str = "dissertativa"
    palavras_chave: Optional[List[str]] = []

class QuestaoResponse(BaseModel):
    id: int
    disciplina: str
    assunto: str
    enunciado: str
    alt_a: str
    alt_b: str
    alt_c: str
    alt_d: str
    gabarito: str
    just_a: str
    just_b: str
    just_c: str
    just_d: str
    dica_interpretacao: str
    formula_aplicavel: str
    nivel: str
    peso_pontuacao: float
    total_questoes_geral: int

class RespostaRequest(BaseModel):
    questao_id: int
    alternativa_escolhida: str
    tempo_resposta: Optional[int] = 0

class HistoricoRequest(BaseModel):
    total_questoes: int
    acertos: int
    pontuacao_final: float
    duracao_segundos: int

class EstatisticaDisciplina(BaseModel):
    disciplina: str
    acertos: int
    erros: int
    total_respondidas: int
    score_total: float
    score_medio_ponderado: float
    aproveitamento_nominal: float

# --- SISTEMA DE CACHE MELHORADO ---
class QuestaoCache:
    def __init__(self, max_size=1000):
        self.cache = {}
        self.max_size = max_size
        self.lock = asyncio.Lock()
        self.access_times = {}
    
    async def get(self, questao_id: int):
        async with self.lock:
            if questao_id in self.cache:
                self.access_times[questao_id] = time.time()
                return self.cache[questao_id]
            return None
    
    async def set(self, questao_id: int, data):
        async with self.lock:
            if len(self.cache) >= self.max_size:
                # Remove o menos acessado recentemente
                oldest_id = min(self.access_times.keys(), key=lambda k: self.access_times[k])
                del self.cache[oldest_id]
                del self.access_times[oldest_id]
            
            self.cache[questao_id] = data
            self.access_times[questao_id] = time.time()

questao_cache = QuestaoCache()

# --- CONFIGURAÇÃO DO GEMINI AI ---
def configurar_gemini():
    global GEMINI_AVAILABLE
    if not GEMINI_AVAILABLE:
        logger.warning("❌ Google Generative AI não disponível")
        return
        
    try:
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            logger.warning("❌ GEMINI_API_KEY não encontrada")
            GEMINI_AVAILABLE = False
            return
            
        genai.configure(api_key=GEMINI_API_KEY)
        modelos = genai.list_models()
        modelo_encontrado = any('gemini-pro' in model.name for model in modelos)
        GEMINI_AVAILABLE = modelo_encontrado
        
        if GEMINI_AVAILABLE:
            logger.info("✅ Google Gemini AI configurado com sucesso")
        else:
            logger.warning("❌ Modelo Gemini Pro não disponível")
            
    except Exception as e:
        logger.error(f"❌ Erro na configuração do Gemini: {e}")
        GEMINI_AVAILABLE = False

# --- CONFIGURAÇÃO DO FASTAPI ---
global_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 ConcursoMaster AI Premium - Inicializando...")
    
    configurar_gemini()
    
    global_state["all_disciplines"] = []
    global_state["all_ids_by_discipline"] = {}
    
    if not os.path.exists(DB_NAME):
        logger.error(f"❌ ERRO: Banco '{DB_NAME}' não encontrado.")
        logger.info("💡 Execute primeiro: python criar_banco.py")
        exit()
        
    engine = db.create_engine(f'sqlite:///{DB_NAME}')
    metadata = db.MetaData()
    
    try:
        global_state["engine"] = engine
        global_state["questoes_table"] = db.Table(TB_QUESTOES, metadata, autoload_with=engine)
        global_state["estatisticas_table"] = db.Table(TB_ESTATISTICAS, metadata, autoload_with=engine)
        global_state["simulados_feitos_table"] = db.Table(TB_SIMULADOS_FEITOS, metadata, autoload_with=engine)
        
        with engine.connect() as conn:
            questoes_table = global_state["questoes_table"]
            
            query_disc = db.select(questoes_table.columns.disciplina).distinct()
            disciplines = [r[0] for r in conn.execute(query_disc).fetchall()]
            global_state["all_disciplines"] = disciplines
            
            total_questoes_geral = 0
            for disc in disciplines:
                query_ids = db.select(questoes_table.columns.id).where(questoes_table.columns.disciplina == disc)
                all_ids = [r[0] for r in conn.execute(query_ids).fetchall()]
                global_state["all_ids_by_discipline"][disc] = all_ids
                total_questoes_geral += len(all_ids)

            global_state["total_questoes"] = total_questoes_geral
            
        logger.info(f"✅ Sistema carregado: {global_state['total_questoes']} questões em {len(disciplines)} disciplinas")
        
    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {e}")
        exit()
    
    yield 

    logger.info("🔴 ConcursoMaster AI - Finalizando...")
    global_state["engine"].dispose()

app = FastAPI(
    title="ConcursoMaster AI API",
    description="API Premium para sistema de estudos de concursos públicos",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- FUNÇÕES AUXILIARES ---
async def get_questao_com_cache(questao_id: int):
    """Obtém questão com sistema de cache melhorado"""
    cached = await questao_cache.get(questao_id)
    if cached:
        return cached
    
    engine = global_state["engine"]
    questoes_table = global_state["questoes_table"]
    
    with engine.connect() as conn:
        query = db.select(questoes_table).where(questoes_table.columns.id == questao_id)
        result = conn.execute(query).fetchone()
        
        if result:
            await questao_cache.set(questao_id, result)
        
        return result

def validar_redacao_sentido(texto: str):
    """Valida se a redação tem conteúdo significativo"""
    palavras = texto.strip().split()
    
    if len(palavras) < 100:
        return {"valido": False, "erro": "Redação muito curta. Mínimo 100 palavras."}
    
    palavras_unicas = set(palavras)
    taxa_repeticao = len(palavras_unicas) / len(palavras)
    
    if taxa_repeticao < 0.3:
        return {"valido": False, "erro": "Texto com repetição excessiva."}
    
    paragrafos = [p.strip() for p in texto.split('\n\n') if p.strip()]
    if len(paragrafos) < 3:
        return {"valido": False, "erro": "Estrutura insuficiente (mínimo 3 parágrafos)."}
    
    return {"valido": True}

def selecionar_questoes_simulado(quantidade: int, disciplinas_filtro: List[str] = None):
    """Seleciona questões para simulado com filtro opcional"""
    simulado_list = []
    total_ids_disponiveis = global_state.get("all_ids_by_discipline", {})
    
    if disciplinas_filtro:
        # Usar apenas disciplinas do filtro
        disciplinas_validas = [d for d in disciplinas_filtro if d in total_ids_disponiveis]
        if not disciplinas_validas:
            return []
            
        questoes_por_disciplina = quantidade // len(disciplinas_validas)
        resto = quantidade % len(disciplinas_validas)
        
        for i, disc in enumerate(disciplinas_validas):
            qtd = questoes_por_disciplina + (1 if i < resto else 0)
            all_ids = total_ids_disponiveis.get(disc, [])
            
            if all_ids and qtd > 0:
                random.shuffle(all_ids)
                selected_ids = all_ids[:min(qtd, len(all_ids))] 
                simulado_list.extend(selected_ids)
    else:
        # Distribuição padrão por porcentagem
        for disc, percent in SIMULADO_DISTRIBUTION_PERCENT.items():
            qtd_necessaria = ceil(quantidade * percent)
            all_ids = total_ids_disponiveis.get(disc, [])
            
            if all_ids and qtd_necessaria > 0:
                random.shuffle(all_ids)
                selected_ids = all_ids[:min(qtd_necessaria, len(all_ids))] 
                simulado_list.extend(selected_ids)

    # Preencher com questões restantes se necessário
    if len(simulado_list) < quantidade:
        all_db_ids = [item for sublist in total_ids_disponiveis.values() for item in sublist]
        remaining_pool = list(set(all_db_ids) - set(simulado_list))
        
        if remaining_pool:
            random.shuffle(remaining_pool)
            needed = quantidade - len(simulado_list)
            simulado_list.extend(remaining_pool[:needed])

    random.shuffle(simulado_list)
    return simulado_list[:quantidade]

# --- FUNÇÕES DO GEMINI AI ---
async def corrigir_redacao_com_gemini(redacao: RedacaoRequest):
    """Correção de redação usando Google Gemini AI"""
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Você é um corretor especializado em redações de concursos públicos brasileiros. 
        Analise a redação abaixo seguindo RIGOROSAMENTE os critérios do ENEM e concursos públicos.

        **TEMA DA REDAÇÃO**: {redacao.tema}
        **TIPO DE PROVA**: {redacao.tipo_prova}

        **TEXTO DO CANDIDATO**:
        {redacao.texto}

        **CRITÉRIOS DE CORREÇÃO (0-200 pontos cada)**:
        1. DOMÍNIO DA NORMA CULTA (200 pontos)
        2. COMPREENSÃO DO TEMA (200 pontos)
        3. ORGANIZAÇÃO TEXTUAL (200 pontos)
        4. COESÃO E COERÊNCIA (200 pontos)
        5. PROPOSTA DE INTERVENÇÃO (200 pontos)

        Forneça uma análise detalhada em HTML com:
        - Pontuação total (0-1000 pontos)
        - Análise individual de cada competência
        - Sugestões específicas de melhoria
        - Comentários gerais

        Use uma linguagem profissional mas acessível, com emojis para melhor visualização.
        Estruture bem o HTML com classes CSS para formatação.
        """
        
        response = await model.generate_content_async(prompt)
        
        if response.text:
            # Extrair pontuação do texto de resposta
            pontuacao_match = re.search(r'(\d{1,3})\s*/\s*1000', response.text)
            pontuacao_total = int(pontuacao_match.group(1)) if pontuacao_match else 600
            
            return {
                "pontuacao_total": pontuacao_total,
                "correcao": response.text,
                "tecnologia": "Google Gemini AI",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise Exception("Resposta vazia do Gemini AI")
            
    except Exception as e:
        logger.error(f"❌ Erro na correção com Gemini: {e}")
        return await corrigir_redacao_simulada(redacao)

async def corrigir_redacao_simulada(redacao: RedacaoRequest):
    """Correção simulada quando Gemini não está disponível"""
    palavras = len(redacao.texto.split())
    paragrafos = redacao.texto.count('\n\n') + 1
    
    # Base score com base em métricas textuais
    base_score = min(500 + (palavras // 3) + (paragrafos * 25), 850)
    variacao = random.randint(-50, 100)
    pontuacao_final = min(base_score + variacao, 1000)
    
    # HTML de correção simulada
    correcao_html = f"""
    <div class="correcao-resultado">
        <div class="pontuacao-total">
            <h3>📊 Pontuação Final: {pontuacao_final}/1000</h3>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">Domínio da Norma Culta</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.18):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Bom domínio da norma padrão, com poucos desvios.</p>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">Compreensão do Tema</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.20):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Tema compreendido adequadamente.</p>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">Organização Textual</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.20):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Estrutura adequada com introdução, desenvolvimento e conclusão.</p>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">Coesão e Coerência</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.21):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Boa articulação entre as ideias.</p>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">Proposta de Intervenção</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.21):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Proposta apresentada de forma clara e viável.</p>
        </div>
        
        <div class="sugestoes-melhoria">
            <strong>💡 Sugestões de Melhoria:</strong>
            <p>• Desenvolva mais os argumentos com exemplos concretos</p>
            <p>• Atenção à pontuação e concordância verbal</p>
            <p>• Enriqueça o vocabulário com sinônimos</p>
            <p>• Revise a estrutura dos parágrafos</p>
        </div>
        
        <div class="analise-geral">
            <strong>📈 Análise Geral:</strong>
            <p>Redação com bom potencial! Continue praticando para melhorar ainda mais sua performance.</p>
        </div>
    </div>
    """
    
    return {
        "pontuacao_total": pontuacao_final,
        "correcao": correcao_html,
        "tecnologia": "Sistema de Correção Simulada",
        "timestamp": datetime.now().isoformat()
    }

# --- ROTAS DA API ---
@app.get("/")
async def root():
    return {
        "message": "🚀 ConcursoMaster AI API Premium v2.0",
        "status": "online",
        "version": "2.0.0",
        "gemini_available": GEMINI_AVAILABLE,
        "total_questoes": global_state.get("total_questoes", 0),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    try:
        with global_state["engine"].connect() as conn:
            # Testar conexão com o banco
            conn.execute(db.text("SELECT 1"))
            
        return {
            "status": "healthy",
            "database": "connected",
            "gemini_ai": "available" if GEMINI_AVAILABLE else "unavailable",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/corrigir-redacao")
async def corrigir_redacao_avancada(redacao: RedacaoRequest):
    """Correção avançada de redação com validações"""
    # Validações iniciais
    if len(redacao.texto.strip()) < 500:
        raise HTTPException(
            status_code=400, 
            detail="Texto muito curto. Mínimo 500 caracteres."
        )
    
    validacao = validar_redacao_sentido(redacao.texto)
    if not validacao["valido"]:
        raise HTTPException(status_code=400, detail=validacao["erro"])
    
    # Registrar tentativa de correção
    logger.info(f"📝 Correção de redação solicitada - Tema: {redacao.tema}")
    
    try:
        if GEMINI_AVAILABLE:
            resultado = await corrigir_redacao_com_gemini(redacao)
        else:
            resultado = await corrigir_redacao_simulada(redacao)
            
        logger.info(f"✅ Redação corrigida - Pontuação: {resultado['pontuacao_total']}/1000")
        return resultado
        
    except Exception as e:
        logger.error(f"❌ Erro na correção de redação: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno durante a correção da redação"
        )

@app.get("/questao/{questao_id}")
async def obter_questao(questao_id: int):
    """Obtém uma questão específica com cache"""
    try:
        result = await get_questao_com_cache(questao_id)
        
        if not result:
            raise HTTPException(
                status_code=404, 
                detail=f"Questão ID {questao_id} não encontrada"
            )
        
        disciplina = result.disciplina
        peso = SIMULADO_PESOS_PONTUACAO.get(disciplina, 1.0)
        
        return QuestaoResponse(
            id=result.id,
            disciplina=disciplina,
            assunto=result.assunto,
            enunciado=result.enunciado,
            alt_a=result.alt_a,
            alt_b=result.alt_b,
            alt_c=result.alt_c,
            alt_d=result.alt_d,
            gabarito=result.gabarito,
            just_a=result.just_a,
            just_b=result.just_b,
            just_c=result.just_c,
            just_d=result.just_d,
            dica_interpretacao=result.dica_interpretacao,
            formula_aplicavel=result.formula_aplicavel,
            nivel=result.nivel,
            peso_pontuacao=peso,
            total_questoes_geral=global_state.get("total_questoes", 0)
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao obter questão {questao_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno do servidor"
        )

@app.get("/disciplinas")
def listar_disciplinas():
    """Lista todas as disciplinas disponíveis"""
    return {
        "disciplinas": global_state.get("all_disciplines", []),
        "total": len(global_state.get("all_disciplines", []))
    }

@app.get("/simulado/iniciar/{quantidade}")
async def iniciar_simulado_filtrado(
    quantidade: int, 
    disciplinas: Optional[str] = Query(None, description="Lista de disciplinas separadas por vírgula")
):
    """Inicia um simulado com filtros opcionais"""
    if quantidade <= 0:
        raise HTTPException(
            status_code=400, 
            detail="❌ A quantidade deve ser maior que zero"
        )
    
    max_questoes = global_state.get("total_questoes", 295)
    if quantidade > max_questoes:
        raise HTTPException(
            status_code=400, 
            detail=f"❌ Quantidade máxima permitida é {max_questoes} questões"
        )

    # Processar disciplinas do filtro
    disciplinas_filtro = None
    if disciplinas and disciplinas.lower() != 'todas':
        disciplinas_filtro = [d.strip() for d in disciplinas.split(',')]
        # Validar disciplinas
        disciplinas_validas = [
            d for d in disciplinas_filtro 
            if d in global_state.get("all_ids_by_discipline", {})
        ]
        if not disciplinas_validas:
            raise HTTPException(
                status_code=400, 
                detail="❌ Nenhuma disciplina válida fornecida"
            )
        disciplinas_filtro = disciplinas_validas

    try:
        simulado_list_ids = selecionar_questoes_simulado(quantidade, disciplinas_filtro)

        if not simulado_list_ids:
            raise HTTPException(
                status_code=404, 
                detail="❌ Não foi possível montar o teste com os filtros fornecidos."
            )

        logger.info(f"🎯 Simulado criado: {len(simulado_list_ids)} questões")

        return {
            "simulado_ids": simulado_list_ids,
            "total_simulado": len(simulado_list_ids),
            "disciplinas": disciplinas_filtro or "Todas",
            "message": f"✅ Simulado montado com {len(simulado_list_ids)} questões",
            "gemini_available": GEMINI_AVAILABLE
        }

    except Exception as e:
        logger.error(f"❌ Erro ao criar simulado: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao montar o simulado"
        )

@app.post("/questao/responder")
async def registrar_resposta(resposta: RespostaRequest):
    """Registra uma resposta e atualiza estatísticas"""
    engine = global_state["engine"]
    questoes_table = global_state["questoes_table"]
    estatisticas_table = global_state["estatisticas_table"]
    
    try:
        with engine.connect() as conn:
            questao = await get_questao_com_cache(resposta.questao_id)
            if not questao:
                raise HTTPException(
                    status_code=404, 
                    detail="Questão não encontrada"
                )
            
            acertou = resposta.alternativa_escolhida.upper() == questao.gabarito.upper()
            disciplina = questao.disciplina
            
            peso = SIMULADO_PESOS_PONTUACAO.get(disciplina, 1.0)
            pontuacao = peso if acertou else 0.0
            
            # Obter justificativas
            justificativa_escolhida = getattr(
                questao, 
                f"just_{resposta.alternativa_escolhida.lower()}", 
                "Justificativa não disponível."
            )
            justificativa_correta = getattr(
                questao, 
                f"just_{questao.gabarito.lower()}", 
                "Justificativa não disponível."
            )
            
            # Atualizar estatísticas
            query_estat = db.select(estatisticas_table).where(
                estatisticas_table.columns.disciplina == disciplina
            )
            estat_existente = conn.execute(query_estat).fetchone()
            
            if estat_existente:
                if acertou:
                    novos_acertos = estat_existente.acertos + 1
                    novo_score = estat_existente.score_total + pontuacao
                    novos_erros = estat_existente.erros
                else:
                    novos_acertos = estat_existente.acertos
                    novo_score = estat_existente.score_total
                    novos_erros = estat_existente.erros + 1
                
                # Calcular nova taxa de acerto
                total_respondidas = novos_acertos + novos_erros
                nova_taxa = (novos_acertos / total_respondidas * 100) if total_respondidas > 0 else 0
                
                update = db.update(estatisticas_table).where(
                    estatisticas_table.columns.disciplina == disciplina
                ).values(
                    acertos=novos_acertos,
                    erros=novos_erros,
                    score_total=novo_score,
                    taxa_acerto=nova_taxa,
                    ultima_atualizacao=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                conn.execute(update)
            else:
                # Primeiro registro para esta disciplina
                taxa_inicial = 100.0 if acertou else 0.0
                insert_data = {
                    "disciplina": disciplina,
                    "acertos": 1 if acertou else 0,
                    "erros": 0 if acertou else 1,
                    "score_total": pontuacao,
                    "taxa_acerto": taxa_inicial,
                    "ultima_atualizacao": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                conn.execute(db.insert(estatisticas_table).values(**insert_data))
            
            conn.commit()
            
            # Limpar cache da questão se existir
            await questao_cache.set(resposta.questao_id, None)
            
            # Análise de desempenho
            analise_desempenho = "✅ Resposta correta! " + (
                "Excelente!" if resposta.tempo_resposta and resposta.tempo_resposta < 60 else
                "Bom tempo!" if resposta.tempo_resposta and resposta.tempo_resposta < 120 else
                "Tempo um pouco alto, pratique mais!"
            ) if acertou else "❌ Resposta incorreta. " + (
                "Revise este conteúdo!" if resposta.tempo_resposta and resposta.tempo_resposta > 120 else
                "Continue praticando!"
            )
            
            return {
                "acertou": acertou,
                "gabarito_correto": questao.gabarito,
                "pontuacao_obtida": pontuacao,
                "justificativa_escolhida": justificativa_escolhida,
                "justificativa_correta": justificativa_correta,
                "dica_interpretacao": questao.dica_interpretacao if not acertou else "",
                "formula_aplicavel": questao.formula_aplicavel,
                "analise_desempenho": analise_desempenho,
                "tempo_resposta": resposta.tempo_resposta or 0
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao registrar resposta: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao processar resposta"
        )

@app.post("/simulado/historico")
async def registrar_historico_simulado(historico: HistoricoRequest):
    """Registra histórico de simulado completo"""
    try:
        with global_state["engine"].connect() as conn:
            total_questoes = max(historico.total_questoes, 1)
            acertos = max(historico.acertos, 0)
            aproveitamento = (acertos / total_questoes) * 100
            tempo_medio = historico.duracao_segundos / total_questoes if total_questoes > 0 else 0
            
            conn.execute(db.insert(global_state["simulados_feitos_table"]).values(
                nome_usuario=NOME_USUARIO_RANKING,
                data_registro=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                total_questoes=total_questoes,
                acertos=acertos,
                pontuacao_final=historico.pontuacao_final,
                duracao_segundos=historico.duracao_segundos,
                aproveitamento=aproveitamento,
                tempo_medio_questao=tempo_medio
            ))
            conn.commit()
            
            logger.info(f"📊 Histórico registrado: {acertos}/{total_questoes} - {aproveitamento:.1f}%")
            
            return {
                "status": "success", 
                "mensagem": "Histórico registrado com sucesso",
                "analise": gerar_analise_desempenho(aproveitamento, tempo_medio)
            }
    except Exception as e:
        logger.error(f"❌ Erro ao registrar histórico: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao registrar histórico"
        )

def gerar_analise_desempenho(aproveitamento: float, tempo_medio: float):
    """Gera análise de desempenho baseada em métricas"""
    if aproveitamento >= 80:
        nivel = "🎖️ Excelente"
        recomendacao = "Continue mantendo este excelente ritmo!"
    elif aproveitamento >= 60:
        nivel = "✅ Bom"
        recomendacao = "Bom desempenho, continue evoluindo."
    elif aproveitamento >= 40:
        nivel = "📚 Em Desenvolvimento"
        recomendacao = "Estude os conteúdos básicos e pratique mais."
    else:
        nivel = "🎯 Precisa Melhorar"
        recomendacao = "Reveja os conceitos fundamentais e faça mais exercícios."
    
    if tempo_medio < 60:
        tempo_analise = "⏱️ Ritmo ótimo"
    elif tempo_medio < 90:
        tempo_analise = "⏱️ Ritmo bom"
    elif tempo_medio < 120:
        tempo_analise = "⏱️ Ritmo regular"
    else:
        tempo_analise = "⏱️ Pratique para melhorar a velocidade"
    
    return {
        "nivel": nivel,
        "aproveitamento": f"{aproveitamento:.1f}%",
        "tempo_medio_por_questao": f"{tempo_medio:.1f}s",
        "analise_tempo": tempo_analise,
        "recomendacao": recomendacao
    }

@app.get("/dashboard-data")
async def obter_dados_dashboard():
    """Obtém dados completos para o dashboard"""
    engine = global_state["engine"]
    estatisticas_table = global_state["estatisticas_table"]
    simulados_feitos_table = global_state["simulados_feitos_table"]
    
    try:
        with engine.connect() as conn:
            # Estatísticas por disciplina
            query_estat = db.select(estatisticas_table)
            estatisticas_raw = conn.execute(query_estat).fetchall()
            
            estatisticas = []
            total_acertos_geral = 0
            total_erros_geral = 0
            pontuacao_total_geral = 0.0
            
            for estat in estatisticas_raw:
                total_respondidas = estat.acertos + estat.erros
                aproveitamento = (estat.acertos / total_respondidas * 100) if total_respondidas > 0 else 0
                score_medio = (estat.score_total / total_respondidas) if total_respondidas > 0 else 0
                
                total_acertos_geral += estat.acertos
                total_erros_geral += estat.erros
                pontuacao_total_geral += estat.score_total
                
                estatisticas.append(EstatisticaDisciplina(
                    disciplina=estat.disciplina,
                    acertos=estat.acertos,
                    erros=estat.erros,
                    total_respondidas=total_respondidas,
                    score_total=estat.score_total,
                    score_medio_ponderado=score_medio,
                    aproveitamento_nominal=aproveitamento
                ))
            
            # Ranking de simulados
            query_ranking = db.select(simulados_feitos_table).order_by(
                db.desc(simulados_feitos_table.columns.pontuacao_final)
            ).limit(10)
            
            ranking_raw = conn.execute(query_ranking).fetchall()
            
            ranking = []
            for rank in ranking_raw:
                # Formatar pontuação
                pontuacao_formatada = f"{rank.pontuacao_final:.1f}"
                
                # Formatar duração
                horas = rank.duracao_segundos // 3600
                minutos = (rank.duracao_segundos % 3600) // 60
                segundos = rank.duracao_segundos % 60
                duracao_formatada = f"{horas:02d}:{minutos:02d}:{segundos:02d}"
                
                ranking.append({
                    "data_registro": rank.data_registro,
                    "total_questoes": rank.total_questoes,
                    "acertos": rank.acertos,
                    "pontuacao_final": rank.pontuacao_final,
                    "pontuacao_formatada": pontuacao_formatada,
                    "duracao_segundos": rank.duracao_segundos,
                    "duracao_formatada": duracao_formatada,
                    "nome_usuario": rank.nome_usuario,
                    "aproveitamento": rank.aproveitamento
                })
            
            # Calcular métricas gerais
            total_respondidas_geral = total_acertos_geral + total_erros_geral
            aproveitamento_geral = (total_acertos_geral / total_respondidas_geral * 100) if total_respondidas_geral > 0 else 0
            
            return {
                "estatisticas": estatisticas,
                "ranking": ranking,
                "metricas_gerais": {
                    "total_questoes_respondidas": total_respondidas_geral,
                    "total_acertos": total_acertos_geral,
                    "total_erros": total_erros_geral,
                    "aproveitamento_geral": aproveitamento_geral,
                    "pontuacao_total": pontuacao_total_geral
                },
                "total_questoes_banco": global_state.get("total_questoes", 0),
                "gemini_available": GEMINI_AVAILABLE,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Erro ao obter dados do dashboard: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao processar dados do dashboard"
        )

@app.get("/estatisticas/resumo")
async def obter_resumo_estatisticas():
    """Endpoint rápido para resumo de estatísticas"""
    try:
        with global_state["engine"].connect() as conn:
            estatisticas_table = global_state["estatisticas_table"]
            
            query = db.select(
                db.func.sum(estatisticas_table.columns.acertos).label('total_acertos'),
                db.func.sum(estatisticas_table.columns.erros).label('total_erros'),
                db.func.sum(estatisticas_table.columns.score_total).label('score_total')
            )
            result = conn.execute(query).fetchone()
            
            total_acertos = result.total_acertos or 0
            total_erros = result.total_erros or 0
            total_respondidas = total_acertos + total_erros
            aproveitamento = (total_acertos / total_respondidas * 100) if total_respondidas > 0 else 0
            
            return {
                "total_respondidas": total_respondidas,
                "aproveitamento": round(aproveitamento, 1),
                "score_total": result.score_total or 0,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Erro ao obter resumo: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")

@app.get("/questoes/total")
async def obter_total_questoes():
    """Retorna o total de questões disponíveis"""
    return {
        "total_questoes": global_state.get("total_questoes", 0),
        "disciplinas": len(global_state.get("all_disciplines", [])),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    import os
    
    print("\n" + "="*60)
    print("🚀 CONCURSOMASTER AI PREMIUM v2.0 - SERVIDOR INICIANDO")
    print("="*60)
    
    if GEMINI_AVAILABLE:
        print("🤖 Google Gemini AI: ✅ ATIVADO")
    else:
        print("🔧 Google Gemini AI: ⚠️  Configure sua API key para recursos avançados")
    
    # CONFIGURAÇÕES PARA PRODUÇÃO (ONLINE)
    host = "0.0.0.0"  # ← MUDAR de "127.0.0.1" para "0.0.0.0"
    port = int(os.environ.get("PORT", 8000))  # ← Usar PORT do ambiente
    
    print(f"🌐 Servidor rodando em: http://{host}:{port}")
    print("📚 API Documentation: http://127.0.0.1:8000/docs")
    print("🔍 Health Check: http://127.0.0.1:8000/health")
    print("="*60 + "\n")
    
    # MUDAR para produção:
    uvicorn.run(
        app, 
        host=host,      # ← 0.0.0.0 em vez de 127.0.0.1
        port=port,      # ← Porta do ambiente
        log_level="info"
    )