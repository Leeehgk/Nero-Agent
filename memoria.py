import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from groq import Groq

# ==========================================
# CAMINHOS DOS ARQUIVOS
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORIA_FILE = os.path.join(BASE_DIR, "memoria_nero.json")
PERFIL_FILE = os.path.join(BASE_DIR, "perfil_nero.json")

# Limites
MAX_MENSAGENS_CURTO = 30   # Mensagens no histórico de curto prazo
MAX_FATOS_PERFIL = 50      # Fatos no perfil de longo prazo


# ==========================================
# MEMÓRIA DE CURTO PRAZO (histórico de chat)
# ==========================================

def carregar_memoria() -> List[Dict[str, Any]]:
    """Carrega o histórico de conversas salvo no JSON."""
    try:
        if os.path.exists(MEMORIA_FILE):
            with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                mensagens = dados.get("mensagens", [])
                print(f"📝 Memória curta carregada: {len(mensagens)} mensagens")
                return mensagens
    except Exception as e:
        print(f"⚠️ Erro ao carregar memória curta: {e}")
    return []


def salvar_memoria(historico: List[Dict[str, Any]]) -> None:
    """Salva o histórico de conversas no JSON."""
    try:
        # Limitar antes de salvar
        if len(historico) > MAX_MENSAGENS_CURTO:
            historico = historico[-MAX_MENSAGENS_CURTO:]

        dados = {
            "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "total_mensagens": len(historico),
            "mensagens": historico
        }
        with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar memória curta: {e}")


def limpar_memoria() -> None:
    """Limpa a memória de curto prazo."""
    salvar_memoria([])


# ==========================================
# MEMÓRIA DE LONGO PRAZO (perfil do usuário)
# ==========================================

def carregar_perfil() -> Dict[str, Any]:
    """Carrega o perfil persistente do usuário."""
    try:
        if os.path.exists(PERFIL_FILE):
            with open(PERFIL_FILE, "r", encoding="utf-8") as f:
                perfil = json.load(f)
                fatos = perfil.get("fatos", [])
                if fatos:
                    print(f"🧠 Perfil carregado: {len(fatos)} fatos sobre o usuário")
                return perfil
    except Exception as e:
        print(f"⚠️ Erro ao carregar perfil: {e}")
    return {"fatos": [], "ultima_atualizacao": None}


def salvar_perfil(perfil: Dict[str, Any]) -> None:
    """Salva o perfil persistente do usuário."""
    try:
        perfil["ultima_atualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # Limitar fatos
        if len(perfil.get("fatos", [])) > MAX_FATOS_PERFIL:
            perfil["fatos"] = perfil["fatos"][-MAX_FATOS_PERFIL:]

        with open(PERFIL_FILE, "w", encoding="utf-8") as f:
            json.dump(perfil, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar perfil: {e}")


def limpar_perfil() -> None:
    """Limpa o perfil de longo prazo."""
    salvar_perfil({"fatos": []})


def formatar_fatos_para_prompt(perfil: Dict[str, Any]) -> str:
    """Formata os fatos do perfil para injeção no system prompt."""
    fatos = perfil.get("fatos", [])
    if not fatos:
        return ""
    lista = "\n".join(f"- {f}" for f in fatos)
    return f"\n\nFATOS QUE VOCÊ APRENDEU SOBRE O USUÁRIO (USE SEMPRE):\n{lista}"


# ==========================================
# EXTRAÇÃO DE FATOS VIA GROQ
# ==========================================

PROMPT_EXTRACAO = """Analise a conversa abaixo e extraia FATOS NOVOS e IMPORTANTES sobre o usuário.

EXTRAIA APENAS:
- Como o usuário quer ser chamado (nome/apelido)
- Preferências pessoais (música, comida, hobbies, trabalho)
- Informações pessoais relevantes (profissão, família, localização)
- Hábitos ou rotinas mencionados
- Coisas que o usuário gosta ou não gosta

NÃO EXTRAIA:
- Comandos técnicos (abrir programa, tocar música)
- Perguntas genéricas sem informação pessoal
- Informações que já estão na lista atual

Responda SOMENTE com os fatos novos, um por linha, sem numeração, sem explicação.
Se NÃO houver fatos novos, responda exatamente: NENHUM

FATOS JÁ CONHECIDOS:
{fatos_atuais}

CONVERSA RECENTE:
{conversa}"""


def extrair_fatos(
    client,  # Pode ser Groq ou ChatOpenAI (ou qualquer LangChain LLM)
    ultimas_mensagens: List[Dict[str, Any]],
    perfil_atual: Dict[str, Any]
) -> List[str]:
    """
    Usa o LLM para analisar a conversa e extrair fatos novos sobre o usuário.
    Funciona com Groq e ChatOpenAI (LM Studio).
    Retorna lista de fatos novos (pode ser vazia).
    """
    if not ultimas_mensagens:
        return []

    # Filtrar apenas mensagens de usuário e assistente com conteúdo
    msgs_validas = [
        m for m in ultimas_mensagens 
        if m.get("role") in ["user", "assistant"] and m.get("content")
    ]

    # Pegar apenas as últimas 4 mensagens válidas para análise (2 turnos)
    msgs_recentes = msgs_validas[-4:]
    conversa_texto = "\n".join(
        f"{'Usuário' if m['role'] == 'user' else 'Nero'}: {m['content']}"
        for m in msgs_recentes
    )

    fatos_atuais = perfil_atual.get("fatos", [])
    fatos_texto = "\n".join(f"- {f}" for f in fatos_atuais) if fatos_atuais else "(nenhum ainda)"

    prompt = PROMPT_EXTRACAO.format(
        fatos_atuais=fatos_texto,
        conversa=conversa_texto
    )

    try:
        # Detectar tipo de cliente e usar o método apropriado
        texto = None
        
        # Tenta como ChatOpenAI/LangChain (LM Studio)
        if hasattr(client, 'invoke'):
            from langchain_core.messages import HumanMessage
            resposta = client.invoke([HumanMessage(content=prompt)])
            texto = resposta.content.strip() if hasattr(resposta, 'content') else str(resposta).strip()
        # Tenta como Groq
        elif hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
            resposta = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            texto = resposta.choices[0].message.content.strip()
        else:
            print("⚠️ Cliente LLM não reconhecido para extração de fatos")
            return []

        if "NENHUM" in texto.upper():
            return []

        # Parsear fatos (um por linha)
        fatos_novos = []
        for linha in texto.split("\n"):
            linha = linha.strip().lstrip("- •·▸▹")
            linha = linha.strip()
            if linha and len(linha) > 5 and len(linha) < 200:
                # Evitar duplicatas
                duplicado = any(
                    linha.lower() in f.lower() or f.lower() in linha.lower()
                    for f in fatos_atuais
                )
                if not duplicado:
                    fatos_novos.append(linha)

        return fatos_novos

    except Exception as e:
        print(f"⚠️ Erro na extração de fatos: {e}")
        return []


def aprender(
    client,  # Pode ser Groq ou ChatOpenAI (LM Studio)
    historico: List[Dict[str, Any]],
    perfil: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Função principal de aprendizado.
    Analisa a conversa, extrai fatos novos e atualiza o perfil.
    Retorna o perfil atualizado.
    Funciona com Groq e ChatOpenAI (LM Studio).
    """
    fatos_novos = extrair_fatos(client, historico, perfil)

    if fatos_novos:
        perfil["fatos"].extend(fatos_novos)
        salvar_perfil(perfil)
        print(f"🧠 [Aprendizado] +{len(fatos_novos)} fato(s): {fatos_novos}")

    return perfil
