import csv
import sqlalchemy as db
import os
from datetime import datetime

def importar_questoes():
    try:
        # Conectar ao banco
        engine = db.create_engine("sqlite:///concurso.db")
        metadata = db.MetaData()
        metadata.reflect(bind=engine)
        questões_table = metadata.tables['questoes']
        
        print("📊 Colunas da tabela:", [col.name for col in questões_table.columns])
        
        # Ler arquivo CSV
        with open('questoes.csv', 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file, delimiter=';')
            questões = []
            
            for row in csv_reader:
                # USAR OS NOMES EXATOS DA TABELA
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
            
            print(f"✅ {len(questões)} questões importadas com sucesso!")
            
    except Exception as e:
        print(f"❌ Erro na importação: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    importar_questoes()
