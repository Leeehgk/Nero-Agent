import os
import sys
import subprocess
import webbrowser
import datetime
import requests
import urllib.parse
from typing import List

# Suporte a UTF-8 no Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pywhatkit
import pyautogui
from PIL import ImageGrab

# ==========================================
# FERRAMENTAS — Funções Python puras
# ==========================================


def tocar_youtube(pesquisa: str) -> str:
    """Toca música ou vídeo no YouTube usando múltiplas abordagens."""
    print(f"🔍 [YouTube] Procurando: {pesquisa}")
    
    # Método 1: pywhatkit (padrão)
    try:
        pywhatkit.playonyt(pesquisa)
        print(f"✅ [YouTube] pywhatkit executou com sucesso")
        return f"Tocando '{pesquisa}' no YouTube!"
    except Exception as e1:
        print(f"⚠️ [YouTube] pywhatkit falhou: {str(e1)}")
        
        # Método 2: webbrowser direto
        try:
            pesquisa_encoded = urllib.parse.quote(pesquisa)
            url = f"https://www.youtube.com/results?search_query={pesquisa_encoded}"
            webbrowser.open(url)
            print(f"✅ [YouTube] webbrowser abriu: {url}")
            return f"Tocando '{pesquisa}' no YouTube!"
        except Exception as e2:
            print(f"⚠️ [YouTube] webbrowser falhou: {str(e2)}")
            
            # Método 3: subprocess com Chrome
            try:
                chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
                if os.path.exists(chrome_path):
                    pesquisa_encoded = urllib.parse.quote(pesquisa)
                    url = f"https://www.youtube.com/results?search_query={pesquisa_encoded}"
                    subprocess.Popen([chrome_path, url])
                    print(f"✅ [YouTube] Chrome abriu diretamente")
                    return f"Tocando '{pesquisa}' no YouTube!"
            except Exception as e3:
                print(f"⚠️ [YouTube] Chrome falhou: {str(e3)}")
    
    return f"Não consegui abrir '{pesquisa}' no YouTube. Verifique se o Chrome está instalado."


def controlar_midia(acao: str) -> str:
    """Controla mídia usando teclas multimídia do Windows."""
    try:
        acao_lower = acao.lower()
        if acao_lower in ["pausar", "tocar", "play", "pause", "play/pause"]:
            pyautogui.press("playpause")
            return "Play/Pause executado."
        elif acao_lower in ["proximo", "próximo", "pular", "skip"]:
            pyautogui.press("nexttrack")
            return "Próxima faixa."
        elif acao_lower in ["anterior", "voltar"]:
            pyautogui.press("prevtrack")
            return "Faixa anterior."
        else:
            return f"Ação '{acao}' não suportada. Use: pausar, tocar, proximo, anterior."
    except Exception as e:
        return f"Erro ao controlar mídia: {str(e)}"


def obter_data_hora() -> str:
    """Retorna data e hora atuais."""
    agora = datetime.datetime.now()
    dias: List[str] = [
        "Segunda-feira", "Terça-feira", "Quarta-feira",
        "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"
    ]
    return f"Hoje é {dias[agora.weekday()]}, {agora.strftime('%d/%m/%Y %H:%M')}."


def obter_clima(cidade: str) -> str:
    """Retorna o clima atual de uma cidade."""
    try:
        url = f"https://wttr.in/{cidade}?format=3"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return f"Clima: {resp.text.strip()}"
        return f"Não foi possível obter o clima para {cidade}."
    except Exception as e:
        return f"Erro ao consultar clima: {str(e)}"


def pesquisar_web(query: str) -> str:
    """Pesquisa na web usando DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        resultados = list(DDGS().text(query, region="pt-br", max_results=3))
        if resultados:
            resumo = " | ".join(r.get("body", "")[:150] for r in resultados)
            return f"Resultados para '{query}': {resumo}"
        return f"Nenhum resultado encontrado para '{query}'."
    except Exception:
        try:
            from langchain_community.tools import DuckDuckGoSearchRun
            ddg = DuckDuckGoSearchRun()
            resultado = ddg.run(query)
            return f"Resultados para '{query}': {resultado[:400]}"
        except Exception as e:
            return f"Erro ao pesquisar: {str(e)}"


def abrir_navegador(url: str) -> str:
    """Abre o navegador em uma URL."""
    try:
        if not url.startswith("http"):
            url = f"https://{url}"
        webbrowser.open(url)
        return f"Navegador aberto em: {url}"
    except Exception as e:
        return f"Erro ao abrir navegador: {str(e)}"


def abrir_programa(nome: str) -> str:
    """Abre um programa do Windows pelo nome."""
    programas = {
        "calculadora": "calc",
        "bloco de notas": "notepad",
        "notepad": "notepad",
        "paint": "mspaint",
        "explorador": "explorer",
        "explorer": "explorer",
        "cmd": "cmd",
        "terminal": "wt",
        "configurações": "ms-settings:",
        "configuracoes": "ms-settings:",
    }
    try:
        nome_lower = nome.lower().strip()
        cmd = programas.get(nome_lower, nome_lower)
        os.startfile(cmd) if ":" in cmd else subprocess.Popen(f"start {cmd}", shell=True)
        return f"Programa '{nome}' aberto."
    except Exception as e:
        return f"Erro ao abrir '{nome}': {str(e)}"


def capturar_tela() -> str:
    """Tira um print da tela inteira."""
    try:
        pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Prints")
        if not os.path.exists(pasta):
            os.makedirs(pasta)
        agora = datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        caminho = os.path.join(pasta, f"Print_{agora}.png")
        ImageGrab.grab().save(caminho)
        return f"Print salvo em: {caminho}"
    except Exception as e:
        return f"Erro ao capturar tela: {str(e)}"


def criar_anotacao(texto: str) -> str:
    """Salva uma anotação em arquivo de texto."""
    try:
        caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anotacoes_nero.txt")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(f"[{agora}] {texto}\n")
        return f"Anotação salva: '{texto}'"
    except Exception as e:
        return f"Erro ao anotar: {str(e)}"


# ==========================================
# SCHEMAS PARA GROQ FUNCTION CALLING
# ==========================================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "tocar_youtube",
            "description": "TOQUE MÚSICA NO YOUTUBE. Use quando usuário disser: 'tocar', 'colocar pra tocar', 'ouvir', 'escutar', 'youtube', 'spotify', 'música', 'banda', 'artista'. Parâmetro pesquisa = o que o usuário quer ouvir (ex: 'Red Hot Chili Peppers', 'música tranquila', 'rock anos 80').",
            "parameters": {
                "type": "object",
                "properties": {
                    "pesquisa": {
                        "type": "string",
                        "description": "O que o usuário quer ouvir: nome de música, artista, banda ou gênero. Ex: 'Red Hot Chili Peppers', 'música feliz para trabajar', 'Coldplay'"
                    }
                },
                "required": ["pesquisa"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "controlar_midia",
            "description": "CONTROLA MÍDIA DO COMPUTADOR. Use quando usuário disser: 'pausar', 'parar', 'pause' (pausar). 'tocar', 'play', 'continuar' (voltar a tocar). 'próxima', 'pular', 'skip' (próxima faixa). 'anterior', 'voltar' (faixa anterior).",
            "parameters": {
                "type": "object",
                "properties": {
                    "acao": {
                        "type": "string",
                        "enum": ["pausar", "pause", "tocar", "play", "proximo", "proxima", "anterior", "voltar"],
                        "description": "Ação: 'pausar' para pausar, 'tocar' para reproduzir, 'proximo' para próxima faixa, 'anterior' para faixa anterior"
                    }
                },
                "required": ["acao"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obter_data_hora",
            "description": "Retorna a data e hora atuais. Use quando o usuário perguntar que dia é, que horas são, etc.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obter_clima",
            "description": "Retorna a temperatura e condição climática de uma cidade. Use quando perguntarem sobre clima, tempo, temperatura.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidade": {
                        "type": "string",
                        "description": "Nome da cidade. Se não especificada, use 'São José do Rio Preto'."
                    }
                },
                "required": ["cidade"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pesquisar_web",
            "description": "Pesquisa na internet sobre qualquer assunto. Use quando o usuário pedir para pesquisar, buscar informação ou quando você não souber a resposta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de pesquisa"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_navegador",
            "description": "Abre o navegador em uma URL específica. Use quando pedirem para abrir um site.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL do site (ex: google.com, youtube.com)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_programa",
            "description": "Abre um programa do Windows (calculadora, bloco de notas, paint, explorador, terminal, configurações).",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {
                        "type": "string",
                        "description": "Nome do programa a abrir"
                    }
                },
                "required": ["nome"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capturar_tela",
            "description": "Tira um print/screenshot da tela inteira do computador. Use APENAS quando pedirem explicitamente para tirar um print.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "criar_anotacao",
            "description": "Salva uma anotação/lembrete em arquivo de texto. Use quando pedirem para anotar, salvar, registrar algo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {
                        "type": "string",
                        "description": "Texto da anotação a ser salva"
                    }
                },
                "required": ["texto"]
            }
        }
    },
]


# Mapa nome → função para execução
TOOL_FUNCTIONS = {
    "tocar_youtube": tocar_youtube,
    "controlar_midia": controlar_midia,
    "obter_data_hora": lambda **_: obter_data_hora(),
    "obter_clima": obter_clima,
    "pesquisar_web": pesquisar_web,
    "abrir_navegador": abrir_navegador,
    "abrir_programa": abrir_programa,
    "capturar_tela": lambda **_: capturar_tela(),
    "criar_anotacao": criar_anotacao,
}
