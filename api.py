import io
# io: permite tratar dados em memória (bytes) como se fossem um arquivo.

import time
# time: mede o tempo da análise.

from collections.abc import Callable
# Callable: tipo para "algo que pode ser chamado como função".

from pathlib import Path
# Manipula caminhos de arquivos.

import torch
# PyTorch.

import uvicorn
# Uvicorn: servidor web que executa a aplicação FastAPI e responde às requisições HTTP.

from fastapi import FastAPI, File, HTTPException, UploadFile
# FastAPI: framework para criar APIs web em Python.
#   FastAPI       -> a classe da aplicação
#   File          -> indica que um parâmetro vem como arquivo enviado no formulário
#   HTTPException -> gera respostas de erro HTTP (400, 413...)
#   UploadFile    -> representa o arquivo recebido
# Obs.: para receber arquivos, o FastAPI exige o pacote "python-multipart" instalado.

from fastapi.middleware.cors import CORSMiddleware

from PIL import Image, UnidentifiedImageError
# Image: abre e manipula imagens.
# UnidentifiedImageError: erro gerado quando o arquivo não é uma imagem reconhecível.

from pydantic import BaseModel
# BaseModel: define o formato (esquema) dos dados das respostas.
# O FastAPI usa isso para validar os dados e gerar a documentação automática.

import config
# Caminhos e escolha do dispositivo.

from dataset import transform_avaliacao
# Mesmas transformações usadas na validação/teste.

from modelo import carregar_checkpoint
# Carrega o modelo treinado.

# ------------------------------------------------------------
# CONSTANTES
# ------------------------------------------------------------

CAMINHO_MODELO: Path = config.DIR_MODELOS / "melhor_modelo.pth"
# Arquivo do modelo que a API vai usar.

TAMANHO_MAX_MB: int = 10
# Tamanho máximo de imagem aceito, em megabytes.

TAMANHO_MAX_BYTES: int = TAMANHO_MAX_MB * 1024 * 1024
# O mesmo limite convertido em bytes (1 MB = 1024 × 1024 bytes).

# ------------------------------------------------------------
# CRIAÇÃO DA APLICAÇÃO
# ------------------------------------------------------------

app: FastAPI = FastAPI(
    title="Detector de Plantas Saudáveis x Doentes",
    description="Envie a foto de uma folha e receba se ela está saudável ou doente.",
    version="1.0",
)
# Cria a aplicação web. Título, descrição e versão aparecem na documentação
# automática, acessível em http://localhost:8000/docs.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# CARREGAMENTO DO MODELO (UMA ÚNICA VEZ)
# ------------------------------------------------------------

device: torch.device = config.dispositivo()
# Escolhe GPU NVIDIA, GPU do Mac ou CPU.

modelo: torch.nn.Module
classes: list[str]
# Declaração dos tipos.

modelo, classes = carregar_checkpoint(CAMINHO_MODELO, device)
# Carrega o modelo quando a API inicia, e não a cada requisição.
# Carregar um modelo é lento; fazendo isso uma vez só, cada análise fica rápida.

transform: Callable[[Image.Image], torch.Tensor] = transform_avaliacao()
# Cria as transformações uma vez e reaproveita em todas as requisições.
# O tipo diz: "função que recebe uma imagem PIL e devolve um tensor".

MENSAGENS: dict[str, str] = {
    "saudavel": "A folha parece saudável.",
    "doente": "A folha apresenta sinais de doença. Recomenda-se inspecionar a planta.",
}
# Mensagem amigável para cada classe. As chaves precisam ser iguais
# aos nomes das pastas de classe usadas no treino.

# ------------------------------------------------------------
# FORMATO DAS RESPOSTAS (ESQUEMAS)
# ------------------------------------------------------------

class StatusResposta(BaseModel):
    # Formato da resposta da rota "/" (verificar se a API está no ar).

    status: str
    # Ex.: "online".

    modelo: str
    # Nome do arquivo do modelo carregado.

    classes: list[str]
    # Classes que o modelo reconhece.

    dispositivo: str
    # Onde o modelo está rodando (cpu, cuda, mps).

    uso: str
    # Instrução rápida de como usar a API.

class AnaliseResposta(BaseModel):
    # Formato da resposta da rota "/analisar".

    arquivo: str | None
    # Nome do arquivo enviado (pode ser None se o cliente não informar).

    resultado: str
    # Classe prevista (ex.: "doente").

    confianca: float
    # Probabilidade da classe prevista (0 a 1).

    probabilidades: dict[str, float]
    # Probabilidade de todas as classes (ex.: {"doente": 0.91, "saudavel": 0.09}).

    mensagem: str
    # Texto explicativo para o usuário.

    tempo_ms: float
    # Tempo gasto na análise, em milissegundos.

# ------------------------------------------------------------
# ROTA GET "/" : STATUS DA API
# ------------------------------------------------------------

@app.get("/")
# Decorador: diz ao FastAPI que a função abaixo responde a requisições GET na rota "/".
# GET é o método usado para CONSULTAR informações (é o que o navegador faz ao abrir um link).

def status() -> StatusResposta:
    return StatusResposta(
        status="online",
        modelo=CAMINHO_MODELO.name,
        # .name pega só o nome do arquivo: "melhor_modelo.pth".

        classes=classes,
        dispositivo=str(device),
        # Converte o device em texto (ex.: "cuda").

        uso="POST /analisar com form-data, campo 'imagem'",
    )
    # O FastAPI converte esse objeto automaticamente em JSON na resposta.

# ------------------------------------------------------------
# ROTA POST "/analisar" : CLASSIFICAR UMA IMAGEM
# ------------------------------------------------------------

@app.post("/analisar")
# Esta função responde a requisições POST na rota "/analisar".
# POST é o método usado para ENVIAR dados ao servidor (aqui, a imagem).

async def analisar(
    imagem: UploadFile = File(..., description="Foto da folha (jpg, png...)"),
    # O arquivo chega num campo de formulário chamado "imagem".
    # File(...): os três pontos (Ellipsis) indicam que o campo é OBRIGATÓRIO.
    # "async def" permite usar "await" para ler o arquivo sem travar o servidor.

) -> AnaliseResposta:

    conteudo: bytes = await imagem.read()
    # Lê todo o conteúdo do arquivo enviado como bytes.
    # "await" espera a leitura terminar.

    if not conteudo:
        raise HTTPException(400, "Arquivo vazio.")
        # Se o arquivo veio vazio, devolve erro 400 (Bad Request = requisição inválida).

    if len(conteudo) > TAMANHO_MAX_BYTES:
        raise HTTPException(413, f"Imagem maior que {TAMANHO_MAX_MB} MB.")
        # Se passar do limite, devolve erro 413 (Payload Too Large = conteúdo grande demais).

    try:
        img: Image.Image = Image.open(io.BytesIO(conteudo)).convert("RGB")
        # io.BytesIO transforma os bytes em um "arquivo em memória",
        # permitindo que o PIL abra a imagem sem salvá-la em disco.
        # .convert("RGB") garante 3 canais.

    except UnidentifiedImageError:
        raise HTTPException(400, "O arquivo enviado não é uma imagem válida.") from None
        # Se o arquivo não for imagem (ex.: um PDF), devolve erro 400 com mensagem clara.
        # "from None" esconde o erro original do PIL, deixando o registro de erros mais limpo.

    t0: float = time.perf_counter()
    # Marca o início da medição. perf_counter é mais preciso que time.time()
    # para medir intervalos curtos.

    x: torch.Tensor = transform(img).unsqueeze(0).to(device)
    # Aplica as transformações -> (3, 224, 224);
    # unsqueeze(0) cria um lote de uma imagem -> (1, 3, 224, 224);
    # .to(device) envia para o dispositivo do modelo.

    with torch.no_grad():
        probs: torch.Tensor = torch.softmax(modelo(x), dim=1)[0].cpu()
        # Sem gradientes (só previsão): obtém os logits, converte em probabilidades
        # com softmax, pega a única imagem do lote e traz para a CPU.

    idx: int = int(probs.argmax())
    # Índice da classe mais provável.

    classe: str = classes[idx]
    # Nome da classe prevista.

    return AnaliseResposta(
        arquivo=imagem.filename,
        # Nome original do arquivo enviado.

        resultado=classe,

        confianca=round(float(probs[idx]), 4),
        # Probabilidade da classe prevista, arredondada para 4 casas.

        probabilidades={c: round(float(p), 4) for c, p in zip(classes, probs)},
        # Dict comprehension: junta cada nome de classe à sua probabilidade.

        mensagem=MENSAGENS.get(classe, ""),
        # .get devolve a mensagem da classe ou "" se ela não estiver no dicionário
        # (evita erro caso exista uma classe sem mensagem cadastrada).

        tempo_ms=round((time.perf_counter() - t0) * 1000, 1),
        # Tempo decorrido em milissegundos (segundos × 1000), com 1 casa decimal.
        # Mede só a transformação + previsão, não a leitura/abertura da imagem.
    )
    # O FastAPI converte esse objeto em JSON e envia ao cliente.

# ------------------------------------------------------------
# INICIAR O SERVIDOR
# ------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000)
    # Inicia o servidor quando o arquivo é executado diretamente (python api.py).
    # "api:app" significa: no arquivo api.py, use a variável app.
    #   (por isso o arquivo precisa se chamar api.py)
    # host="0.0.0.0": aceita conexões de outras máquinas da rede, não só do próprio computador.
    #   Para aceitar apenas conexões locais, usaria "127.0.0.1".
    # port=8000: a API fica disponível em http://localhost:8000