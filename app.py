import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from functools import lru_cache
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_DRIVER = os.getenv("DB_DRIVER")

@lru_cache(maxsize=1)
def get_engine():
    SQLALCHEMY_DATABASE_URL = (f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?driver={DB_DRIVER}")
    return create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

COORDENACOES_CACHE = {}

def load_coordenacoes_cache():
    engine = get_engine()
    try:
        with engine.connect() as connection:
            sql_query_string = "SELECT * FROM dbo.tb_coordenacao"
            resultado = connection.execute(text(sql_query_string)) 
            global COORDENACOES_CACHE
            for row in resultado.fetchall():
                row_dict = row._asdict()
                COORDENACOES_CACHE[row_dict['codigo']] = row_dict
    except Exception as e:
        raise RuntimeError("Falha ao inicializar a API: Não foi possível carregar dados estáticos.") from e

try:
    load_coordenacoes_cache()
except RuntimeError:
    raise


app = FastAPI(title="API de VISARJ", 
              description="API para gerenciamento e consulta de Ordens de Serviço (OS) e Inspeção.", 
              version="1.0.0")

@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(request, exc):
    if isinstance(exc, ProgrammingError):
        detail_msg = f"Erro de sintaxe SQL ou esquema inválido: {exc.orig.args[1]}"
    else:
        detail_msg = "Erro interno ao acessar o banco de dados."
    return HTTPException(status_code=500, detail=detail_msg)

@app.get("/ordem_servico/{ordem_servico}")
def get_ordem_servico(ordem_servico: str, db=Depends(get_db)):
    "Retorna dados da Ordem de Serviço"
    query = text("SELECT TOP 1 * FROM os WHERE codigo = :ordem_servico")
    resultado_dict = db.execute(query, {"ordem_servico": ordem_servico}).first()
    if resultado_dict is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    resultado_dict = resultado_dict._asdict()
    resultado_dict['coordenacao_descricao'] = COORDENACOES_CACHE[resultado_dict['coordenacao']]['nome']
    equipe_query = text("""select oe.lider, oe.usuario, u.matricula, u.nome, u.telefone from os_equipe oe inner join usuarios u on u.codigo = oe.usuario where oe.os = :ordem_servico""")     
    resultado = db.execute(equipe_query, {"ordem_servico": ordem_servico})
    resultado_dict['equipe'] = [row._asdict() for row in resultado.fetchall()]
    return resultado_dict

@app.get("/inspecao/{codigo_inspecao}")
def get_inspecao(codigo_inspecao: str, db=Depends(get_db)):
    "Retorna dados da Inspeção"
    query = text("SELECT TOP 1 * FROM inspecao WHERE codigo = :codigo_inspecao")
    resultado_dict = db.execute(query, {"codigo_inspecao": codigo_inspecao}).first()
    if resultado_dict is None:
        raise HTTPException(status_code=404, detail="Inspeção não encontrada")
    resultado_dict = resultado_dict._asdict()
    resultado_dict['coordenacao_descricao'] = COORDENACOES_CACHE[resultado_dict['coordenacao']]['nome']
    campos_remover = ['token_acesso']
    for campo in campos_remover:
        if campo in resultado_dict:
            del resultado_dict[campo]
    return resultado_dict

@app.get("/usuario/{numero_usuario}")
def get_usuario(numero_usuario: str, db=Depends(get_db)):
    "Retorna dados do usuário"
    usuario_query = text("SELECT TOP 1 * FROM usuarios WHERE codigo = :numero_usuario")
    resultado_funcionario = db.execute(usuario_query, {"numero_usuario": numero_usuario}).first()
    if resultado_funcionario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    resultado_dict = resultado_funcionario._asdict()
    campos_remover = ['assinatura', 'senha', 'senha_site']
    for campo in campos_remover:
        if campo in resultado_dict:
            del resultado_dict[campo]
    return resultado_dict

@app.get("/lista_inspecao")
def get_lista_inspecao(rows:int = 10, offset:int = 0, db=Depends(get_db)):
    "Listagem das inspeções"
    sql_query_string = "SELECT codigo, os, data_cadastro, coordenacao, divisao, situacao FROM dbo.inspecao ORDER BY codigo DESC OFFSET :offset ROWS FETCH NEXT :rows ROWS ONLY"
    resultado = db.execute(text(sql_query_string), {"rows": min(100,rows), "offset": offset}) 
    return [row._asdict() for row in resultado.fetchall()]

@app.get("/lista_ordem_servico")
def get_lista_ordem_servico(rows:int = 10, offset:int = 0, db=Depends(get_db)):
    "Listagem das ordens de serviço"
    sql_query_string = "SELECT codigo, data_cadastro, coordenacao, situacao FROM dbo.os ORDER BY codigo DESC OFFSET :offset ROWS FETCH NEXT :rows ROWS ONLY"
    resultado = db.execute(text(sql_query_string), {"rows": min(100,rows), "offset": offset})  
    return [row._asdict() for row in resultado.fetchall()]

@app.get("/health")
def get_lista_ordem_servico(db=Depends(get_db)):
    "Verifica a disponibilidade da API"
    return {"status":"OK"}