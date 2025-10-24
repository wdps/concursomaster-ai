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

# Configuração simplificada para deploy
GEMINI_AVAILABLE = False

# Configuração simplificada para deploy
GEMINI_AVAILABLE = False

# --- CONFIGURAÃ‡ÃƒO DO GEMINI AI ---
def configurar_gemini():
    global GEMINI_AVAILABLE
    if not GEMINI_AVAILABLE:
        logger.warning("âŒ Google Generative AI nÃ£o disponÃ­vel")
        return
        
    try:
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            logger.warning("âŒ GEMINI_API_KEY nÃ£o encontrada")
            GEMINI_AVAILABLE = False
            return
            
        genai.configure(api_key=GEMINI_API_KEY)
        modelos = genai.list_models()
        modelo_encontrado = any('gemini-pro' in model.name for model in modelos)
        GEMINI_AVAILABLE = modelo_encontrado
        
        if GEMINI_AVAILABLE:
            logger.info("âœ… Google Gemini AI configurado com sucesso")
        else:
            logger.warning("âŒ Modelo Gemini Pro nÃ£o disponÃ­vel")
            
    except Exception as e:
        logger.error(f"âŒ Erro na configuraÃ§Ã£o do Gemini: {e}")
        GEMINI_AVAILABLE = False

# --- CONFIGURAÃ‡ÃƒO DO FASTAPI ---
global_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ðŸš€ ConcursoMaster AI Premium - Inicializando...")
    
    configurar_gemini()
    
    global_state["all_disciplines"] = []
    global_state["all_ids_by_discipline"] = {}
    
    if not os.path.exists(DB_NAME):
        logger.error(f"âŒ ERRO: Banco '{DB_NAME}' nÃ£o encontrado.")
        logger.info("ðŸ’¡ Execute primeiro: python criar_banco.py")
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
            
        logger.info(f"âœ… Sistema carregado: {global_state['total_questoes']} questÃµes em {len(disciplines)} disciplinas")
        
    except Exception as e:
        logger.error(f"âŒ Erro na inicializaÃ§Ã£o: {e}")
        exit()
    
    yield 

    logger.info("ðŸ”´ ConcursoMaster AI - Finalizando...")
    global_state["engine"].dispose()



# Configuração simplificada para deploy
GEMINI_AVAILABLE = False



# Configuração simplificada para deploy
GEMINI_AVAILABLE = False

app = FastAPI(
    title="ConcursoMaster AI API",
    description="API Premium para sistema de estudos de concursos pÃºblicos",
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

# --- FUNÃ‡Ã•ES AUXILIARES ---
async def get_questao_com_cache(questao_id: int):
    """ObtÃ©m questÃ£o com sistema de cache melhorado"""
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
    """Valida se a redaÃ§Ã£o tem conteÃºdo significativo"""
    palavras = texto.strip().split()
    
    if len(palavras) < 100:
        return {"valido": False, "erro": "RedaÃ§Ã£o muito curta. MÃ­nimo 100 palavras."}
    
    palavras_unicas = set(palavras)
    taxa_repeticao = len(palavras_unicas) / len(palavras)
    
    if taxa_repeticao < 0.3:
        return {"valido": False, "erro": "Texto com repetiÃ§Ã£o excessiva."}
    
    paragrafos = [p.strip() for p in texto.split('\n\n') if p.strip()]
    if len(paragrafos) < 3:
        return {"valido": False, "erro": "Estrutura insuficiente (mÃ­nimo 3 parÃ¡grafos)."}
    
    return {"valido": True}

def selecionar_questoes_simulado(quantidade: int, disciplinas_filtro: List[str] = None):
    """Seleciona questÃµes para simulado com filtro opcional"""
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
        # DistribuiÃ§Ã£o padrÃ£o por porcentagem
        for disc, percent in SIMULADO_DISTRIBUTION_PERCENT.items():
            qtd_necessaria = ceil(quantidade * percent)
            all_ids = total_ids_disponiveis.get(disc, [])
            
            if all_ids and qtd_necessaria > 0:
                random.shuffle(all_ids)
                selected_ids = all_ids[:min(qtd_necessaria, len(all_ids))] 
                simulado_list.extend(selected_ids)

    # Preencher com questÃµes restantes se necessÃ¡rio
    if len(simulado_list) < quantidade:
        all_db_ids = [item for sublist in total_ids_disponiveis.values() for item in sublist]
        remaining_pool = list(set(all_db_ids) - set(simulado_list))
        
        if remaining_pool:
            random.shuffle(remaining_pool)
            needed = quantidade - len(simulado_list)
            simulado_list.extend(remaining_pool[:needed])

    random.shuffle(simulado_list)
    return simulado_list[:quantidade]

# --- FUNÃ‡Ã•ES DO GEMINI AI ---
async def corrigir_redacao_com_gemini(redacao: RedacaoRequest):
    """CorreÃ§Ã£o de redaÃ§Ã£o usando Google Gemini AI"""
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        VocÃª Ã© um corretor especializado em redaÃ§Ãµes de concursos pÃºblicos brasileiros. 
        Analise a redaÃ§Ã£o abaixo seguindo RIGOROSAMENTE os critÃ©rios do ENEM e concursos pÃºblicos.

        **TEMA DA REDAÃ‡ÃƒO**: {redacao.tema}
        **TIPO DE PROVA**: {redacao.tipo_prova}

        **TEXTO DO CANDIDATO**:
        {redacao.texto}

        **CRITÃ‰RIOS DE CORREÃ‡ÃƒO (0-200 pontos cada)**:
        1. DOMÃNIO DA NORMA CULTA (200 pontos)
        2. COMPREENSÃƒO DO TEMA (200 pontos)
        3. ORGANIZAÃ‡ÃƒO TEXTUAL (200 pontos)
        4. COESÃƒO E COERÃŠNCIA (200 pontos)
        5. PROPOSTA DE INTERVENÃ‡ÃƒO (200 pontos)

        ForneÃ§a uma anÃ¡lise detalhada em HTML com:
        - PontuaÃ§Ã£o total (0-1000 pontos)
        - AnÃ¡lise individual de cada competÃªncia
        - SugestÃµes especÃ­ficas de melhoria
        - ComentÃ¡rios gerais

        Use uma linguagem profissional mas acessÃ­vel, com emojis para melhor visualizaÃ§Ã£o.
        Estruture bem o HTML com classes CSS para formataÃ§Ã£o.
        """
        
        response = await model.generate_content_async(prompt)
        
        if response.text:
            # Extrair pontuaÃ§Ã£o do texto de resposta
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
        logger.error(f"âŒ Erro na correÃ§Ã£o com Gemini: {e}")
        return await corrigir_redacao_simulada(redacao)

async def corrigir_redacao_simulada(redacao: RedacaoRequest):
    """CorreÃ§Ã£o simulada quando Gemini nÃ£o estÃ¡ disponÃ­vel"""
    palavras = len(redacao.texto.split())
    paragrafos = redacao.texto.count('\n\n') + 1
    
    # Base score com base em mÃ©tricas textuais
    base_score = min(500 + (palavras // 3) + (paragrafos * 25), 850)
    variacao = random.randint(-50, 100)
    pontuacao_final = min(base_score + variacao, 1000)
    
    # HTML de correÃ§Ã£o simulada
    correcao_html = f"""
    <div class="correcao-resultado">
        <div class="pontuacao-total">
            <h3>ðŸ“Š PontuaÃ§Ã£o Final: {pontuacao_final}/1000</h3>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">DomÃ­nio da Norma Culta</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.18):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Bom domÃ­nio da norma padrÃ£o, com poucos desvios.</p>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">CompreensÃ£o do Tema</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.20):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Tema compreendido adequadamente.</p>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">OrganizaÃ§Ã£o Textual</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.20):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Estrutura adequada com introduÃ§Ã£o, desenvolvimento e conclusÃ£o.</p>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">CoesÃ£o e CoerÃªncia</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.21):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Boa articulaÃ§Ã£o entre as ideias.</p>
        </div>
        
        <div class="competencia-item">
            <div class="competencia-header">
                <span class="competencia-titulo">Proposta de IntervenÃ§Ã£o</span>
                <span class="competencia-pontos">{(pontuacao_final * 0.21):.0f}/200</span>
            </div>
            <p class="competencia-descricao">Proposta apresentada de forma clara e viÃ¡vel.</p>
        </div>
        
        <div class="sugestoes-melhoria">
            <strong>ðŸ’¡ SugestÃµes de Melhoria:</strong>
            <p>â€¢ Desenvolva mais os argumentos com exemplos concretos</p>
            <p>â€¢ AtenÃ§Ã£o Ã  pontuaÃ§Ã£o e concordÃ¢ncia verbal</p>
            <p>â€¢ EnriqueÃ§a o vocabulÃ¡rio com sinÃ´nimos</p>
            <p>â€¢ Revise a estrutura dos parÃ¡grafos</p>
        </div>
        
        <div class="analise-geral">
            <strong>ðŸ“ˆ AnÃ¡lise Geral:</strong>
            <p>RedaÃ§Ã£o com bom potencial! Continue praticando para melhorar ainda mais sua performance.</p>
        </div>
    </div>
    """
    
    return {
        "pontuacao_total": pontuacao_final,
        "correcao": correcao_html,
        "tecnologia": "Sistema de CorreÃ§Ã£o Simulada",
        "timestamp": datetime.now().isoformat()
    }

# --- ROTAS DA API ---
@app.get("/")
async def root():
    return {
        "message": "ðŸš€ ConcursoMaster AI API Premium v2.0",
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
            # Testar conexÃ£o com o banco
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
    """CorreÃ§Ã£o avanÃ§ada de redaÃ§Ã£o com validaÃ§Ãµes"""
    # ValidaÃ§Ãµes iniciais
    if len(redacao.texto.strip()) < 500:
        raise HTTPException(
            status_code=400, 
            detail="Texto muito curto. MÃ­nimo 500 caracteres."
        )
    
    validacao = validar_redacao_sentido(redacao.texto)
    if not validacao["valido"]:
        raise HTTPException(status_code=400, detail=validacao["erro"])
    
    # Registrar tentativa de correÃ§Ã£o
    logger.info(f"ðŸ“ CorreÃ§Ã£o de redaÃ§Ã£o solicitada - Tema: {redacao.tema}")
    
    try:
        if GEMINI_AVAILABLE:
            resultado = await corrigir_redacao_com_gemini(redacao)
        else:
            resultado = await corrigir_redacao_simulada(redacao)
            
        logger.info(f"âœ… RedaÃ§Ã£o corrigida - PontuaÃ§Ã£o: {resultado['pontuacao_total']}/1000")
        return resultado
        
    except Exception as e:
        logger.error(f"âŒ Erro na correÃ§Ã£o de redaÃ§Ã£o: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno durante a correÃ§Ã£o da redaÃ§Ã£o"
        )

@app.get("/questao/{questao_id}")
async def obter_questao(questao_id: int):
    """ObtÃ©m uma questÃ£o especÃ­fica com cache"""
    try:
        result = await get_questao_com_cache(questao_id)
        
        if not result:
            raise HTTPException(
                status_code=404, 
                detail=f"QuestÃ£o ID {questao_id} nÃ£o encontrada"
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
        logger.error(f"âŒ Erro ao obter questÃ£o {questao_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno do servidor"
        )

@app.get("/disciplinas")
def listar_disciplinas():
    """Lista todas as disciplinas disponÃ­veis"""
    return {
        "disciplinas": global_state.get("all_disciplines", []),
        "total": len(global_state.get("all_disciplines", []))
    }

@app.get("/simulado/iniciar/{quantidade}")
async def iniciar_simulado_filtrado(
    quantidade: int, 
    disciplinas: Optional[str] = Query(None, description="Lista de disciplinas separadas por vÃ­rgula")
):
    """Inicia um simulado com filtros opcionais"""
    if quantidade <= 0:
        raise HTTPException(
            status_code=400, 
            detail="âŒ A quantidade deve ser maior que zero"
        )
    
    max_questoes = global_state.get("total_questoes", 295)
    if quantidade > max_questoes:
        raise HTTPException(
            status_code=400, 
            detail=f"âŒ Quantidade mÃ¡xima permitida Ã© {max_questoes} questÃµes"
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
                detail="âŒ Nenhuma disciplina vÃ¡lida fornecida"
            )
        disciplinas_filtro = disciplinas_validas

    try:
        simulado_list_ids = selecionar_questoes_simulado(quantidade, disciplinas_filtro)

        if not simulado_list_ids:
            raise HTTPException(
                status_code=404, 
                detail="âŒ NÃ£o foi possÃ­vel montar o teste com os filtros fornecidos."
            )

        logger.info(f"ðŸŽ¯ Simulado criado: {len(simulado_list_ids)} questÃµes")

        return {
            "simulado_ids": simulado_list_ids,
            "total_simulado": len(simulado_list_ids),
            "disciplinas": disciplinas_filtro or "Todas",
            "message": f"âœ… Simulado montado com {len(simulado_list_ids)} questÃµes",
            "gemini_available": GEMINI_AVAILABLE
        }

    except Exception as e:
        logger.error(f"âŒ Erro ao criar simulado: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao montar o simulado"
        )

@app.post("/questao/responder")
async def registrar_resposta(resposta: RespostaRequest):
    """Registra uma resposta e atualiza estatÃ­sticas"""
    engine = global_state["engine"]
    questoes_table = global_state["questoes_table"]
    estatisticas_table = global_state["estatisticas_table"]
    
    try:
        with engine.connect() as conn:
            questao = await get_questao_com_cache(resposta.questao_id)
            if not questao:
                raise HTTPException(
                    status_code=404, 
                    detail="QuestÃ£o nÃ£o encontrada"
                )
            
            acertou = resposta.alternativa_escolhida.upper() == questao.gabarito.upper()
            disciplina = questao.disciplina
            
            peso = SIMULADO_PESOS_PONTUACAO.get(disciplina, 1.0)
            pontuacao = peso if acertou else 0.0
            
            # Obter justificativas
            justificativa_escolhida = getattr(
                questao, 
                f"just_{resposta.alternativa_escolhida.lower()}", 
                "Justificativa nÃ£o disponÃ­vel."
            )
            justificativa_correta = getattr(
                questao, 
                f"just_{questao.gabarito.lower()}", 
                "Justificativa nÃ£o disponÃ­vel."
            )
            
            # Atualizar estatÃ­sticas
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
            
            # Limpar cache da questÃ£o se existir
            await questao_cache.set(resposta.questao_id, None)
            
            # AnÃ¡lise de desempenho
            analise_desempenho = "âœ… Resposta correta! " + (
                "Excelente!" if resposta.tempo_resposta and resposta.tempo_resposta < 60 else
                "Bom tempo!" if resposta.tempo_resposta and resposta.tempo_resposta < 120 else
                "Tempo um pouco alto, pratique mais!"
            ) if acertou else "âŒ Resposta incorreta. " + (
                "Revise este conteÃºdo!" if resposta.tempo_resposta and resposta.tempo_resposta > 120 else
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
        logger.error(f"âŒ Erro ao registrar resposta: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao processar resposta"
        )

@app.post("/simulado/historico")
async def registrar_historico_simulado(historico: HistoricoRequest):
    """Registra histÃ³rico de simulado completo"""
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
            
            logger.info(f"ðŸ“Š HistÃ³rico registrado: {acertos}/{total_questoes} - {aproveitamento:.1f}%")
            
            return {
                "status": "success", 
                "mensagem": "HistÃ³rico registrado com sucesso",
                "analise": gerar_analise_desempenho(aproveitamento, tempo_medio)
            }
    except Exception as e:
        logger.error(f"âŒ Erro ao registrar histÃ³rico: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao registrar histÃ³rico"
        )

def gerar_analise_desempenho(aproveitamento: float, tempo_medio: float):
    """Gera anÃ¡lise de desempenho baseada em mÃ©tricas"""
    if aproveitamento >= 80:
        nivel = "ðŸŽ–ï¸ Excelente"
        recomendacao = "Continue mantendo este excelente ritmo!"
    elif aproveitamento >= 60:
        nivel = "âœ… Bom"
        recomendacao = "Bom desempenho, continue evoluindo."
    elif aproveitamento >= 40:
        nivel = "ðŸ“š Em Desenvolvimento"
        recomendacao = "Estude os conteÃºdos bÃ¡sicos e pratique mais."
    else:
        nivel = "ðŸŽ¯ Precisa Melhorar"
        recomendacao = "Reveja os conceitos fundamentais e faÃ§a mais exercÃ­cios."
    
    if tempo_medio < 60:
        tempo_analise = "â±ï¸ Ritmo Ã³timo"
    elif tempo_medio < 90:
        tempo_analise = "â±ï¸ Ritmo bom"
    elif tempo_medio < 120:
        tempo_analise = "â±ï¸ Ritmo regular"
    else:
        tempo_analise = "â±ï¸ Pratique para melhorar a velocidade"
    
    return {
        "nivel": nivel,
        "aproveitamento": f"{aproveitamento:.1f}%",
        "tempo_medio_por_questao": f"{tempo_medio:.1f}s",
        "analise_tempo": tempo_analise,
        "recomendacao": recomendacao
    }

@app.get("/dashboard-data")
async def obter_dados_dashboard():
    """ObtÃ©m dados completos para o dashboard"""
    engine = global_state["engine"]
    estatisticas_table = global_state["estatisticas_table"]
    simulados_feitos_table = global_state["simulados_feitos_table"]
    
    try:
        with engine.connect() as conn:
            # EstatÃ­sticas por disciplina
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
                # Formatar pontuaÃ§Ã£o
                pontuacao_formatada = f"{rank.pontuacao_final:.1f}"
                
                # Formatar duraÃ§Ã£o
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
            
            # Calcular mÃ©tricas gerais
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
        logger.error(f"âŒ Erro ao obter dados do dashboard: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao processar dados do dashboard"
        )

@app.get("/estatisticas/resumo")
async def obter_resumo_estatisticas():
    """Endpoint rÃ¡pido para resumo de estatÃ­sticas"""
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
        logger.error(f"âŒ Erro ao obter resumo: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")

@app.get("/questoes/total")
async def obter_total_questoes():
    """Retorna o total de questÃµes disponÃ­veis"""
    return {
        "total_questoes": global_state.get("total_questoes", 0),
        "disciplinas": len(global_state.get("all_disciplines", [])),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    import os
    
    print("\n" + "="*60)
    print("ðŸš€ CONCURSOMASTER AI PREMIUM v2.0 - SERVIDOR INICIANDO")
    print("="*60)
    
    if GEMINI_AVAILABLE:
        print("ðŸ¤– Google Gemini AI: âœ… ATIVADO")
    else:
        print("ðŸ”§ Google Gemini AI: âš ï¸  Configure sua API key para recursos avanÃ§ados")
    
    # CONFIGURAÃ‡Ã•ES PARA PRODUÃ‡ÃƒO (ONLINE)
    host = "0.0.0.0"  # â† MUDAR de "127.0.0.1" para "0.0.0.0"
    port = int(os.environ.get("PORT", 8000))  # â† Usar PORT do ambiente
    
    print(f"ðŸŒ Servidor rodando em: http://{host}:{port}")
    print("ðŸ“š API Documentation: http://127.0.0.1:8000/docs")
    print("ðŸ” Health Check: http://127.0.0.1:8000/health")
    print("="*60 + "\n")
    
    # MUDAR para produÃ§Ã£o:
    uvicorn.run(
        app, 
        host=host,      # â† 0.0.0.0 em vez de 127.0.0.1
        port=port,      # â† Porta do ambiente
        log_level="info"
    )





