import os
import json
import re
import asyncio
import random
import requests
from typing import List, Dict, Any

from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage

from audio import (
    inicializar_microfone_global, fechar_microfone_global,
    esperar_palavra_ativacao, escutar_com_microfone_aberto,
    criar_sessao_microfone, falar_texto
)
from memoria import (
    carregar_memoria, salvar_memoria, limpar_memoria,
    carregar_perfil, limpar_perfil,
    formatar_fatos_para_prompt, aprender
)
from ferramentas import FERRAMENTAS_LANGCHAIN

# ==========================================
# CONFIGURAÇÃO E AMBIENTE
# ==========================================

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# GROQ_API_KEY será validada apenas se o usuário escolher iniciar com Groq

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config_eon.json")


def ler_config_nome() -> str:
    """Lê o nome do usuário salvo no config_eon.json."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                return dados.get("nome_usuario", "chefe")
    except Exception:
        pass
    return "chefe"


# ==========================================
# CLIENTE (Groq ou LM local) + FUNCTION CALLING
# ==========================================

client_llm = None  # Inicializado na escolha de provedor


def criar_agente_langchain(client, nome_usuario: str, perfil: Dict[str, Any]):
    fatos_texto = formatar_fatos_para_prompt(perfil)
    system_prompt = f"""Você é o Nero, assistente pessoal de IA do usuário '{nome_usuario}'.

REGRAS CRUCIAIS PARA AÇÕES:
- Use as ferramentas ativamente quando o usuário pedir para tocar música, alterar volume, abrir programas, pesquisar, etc.
- OBRIGATÓRIO: NUNCA diga que executou uma ação sem ANTES chamar a ferramenta correspondente.

PERSONALIDADE:
1. Descolado, direto, animado, empático. Como um amigo expert.
2. Fale sempre Português do Brasil. Tom natural, moderno e CONCISO.
3. Respostas CURTAS — você fala em voz, não escreve textos longos.
4. Se não souber algo, diga diretamente. Não enrole.
5. Seu nome é Nero.
6. Para conversa casual, responda naturalmente sem ferramentas.
{fatos_texto}"""

    # O LangGraph substitui o antigo AgentExecutor com uma arquitetura mais moderna
    # IMPORTANTE: Bindamos as ferramentas ao modelo para que ele saiba como chamá-las
    model_with_tools = client.bind_tools(FERRAMENTAS_LANGCHAIN)
    return create_react_agent(model=model_with_tools, tools=FERRAMENTAS_LANGCHAIN, prompt=system_prompt)


def perguntar_langchain(
    historico: List[Dict[str, Any]],
    nome_usuario: str,
    perfil: Dict[str, Any]
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Formata o histórico e repassa para o agente do LangGraph processar texto e ações.
    """
    executor = criar_agente_langchain(client_llm, nome_usuario, perfil)

    # Converte todo o histórico para o padrão de mensagens
    lc_history = []
    for msg in historico:
        if msg.get("role") == "user":
            lc_history.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant" and msg.get("content"):
            lc_history.append(AIMessage(content=msg.get("content", "")))

    try:
        resposta = executor.invoke({
            "messages": lc_history
        })
        # A última mensagem será a resposta final do modelo
        texto_final = resposta["messages"][-1].content
    except Exception as e:
        texto_final = f"Tive um erro interno processando a requisição: {str(e)}"

    # Fallback para modelos locais (como Qwen no LM Studio) que geram a chamada da ferramenta no próprio texto
    padrao_funcao = re.search(r'<function=([^>]+)>(.*?)</function>', texto_final, re.DOTALL)
    if padrao_funcao:
        nome_func = padrao_funcao.group(1).strip()
        args_str = padrao_funcao.group(2).strip()
        
        # Limpa a tag do texto final para o Nero não falar o código da função em voz alta
        texto_final = re.sub(r'<function=[^>]+>.*?</function>', '', texto_final, flags=re.DOTALL).strip()
        
        try:
            if args_str:
                args = json.loads(args_str)
            else:
                args = {}
            print(f"🔧 [Fallback LM Local] Forçando execução da ferramenta '{nome_func}' com {args}")
            for ferramenta in FERRAMENTAS_LANGCHAIN:
                if ferramenta.name == nome_func:
                    # Executa a função encontrada manualmente
                    ferramenta.invoke(args)
                    break
        except Exception as e:
            print(f"⚠️ Erro ao executar ferramenta de fallback: {e}")

    novas_mensagens = [{"role": "assistant", "content": texto_final}]

    return texto_final, novas_mensagens


# ==========================================
# LOOP PRINCIPAL
# ==========================================

async def iniciar_assistente() -> None:
    palavra_de_ativacao = "Nero"

    print("🎙️ Inicializando microfone global...")
    inicializar_microfone_global()

    # Carregar memórias
    historico_curto: List[Dict[str, Any]] = carregar_memoria()
    perfil: Dict[str, Any] = carregar_perfil()

    tem_memoria = bool(historico_curto) or bool(perfil.get("fatos"))
    n_fatos = len(perfil.get("fatos", []))
    if tem_memoria:
        boas_vindas = [
            f"Nero de volta! Lembro de tudo — {n_fatos} fato(s) sobre você. Modo stand-by.",
            "Memória carregada! Sei quem você é. Só me chamar!",
            "Sistemas online com ferramentas ativas! Stand-by.",
        ]
    else:
        boas_vindas = [
            "Sistemas online! Ferramentas carregadas. Modo de espera ativado.",
            "Nero na área. Cérebro e ferramentas prontos. Só me chamar!",
            "Primeira sessão! Pronto pra te conhecer. Stand-by ativado.",
        ]
    await falar_texto(random.choice(boas_vindas))

    while True:
        # ======== STAND-BY ========
        texto_wake = esperar_palavra_ativacao(palavra_de_ativacao)
        if not texto_wake:
            continue

        nome_atual = ler_config_nome()
        texto_w = texto_wake.lower()

        if any(p in texto_w for p in ["vamos lá", "bora", "vamos começar", "vamos nessa"]):
            acordando = [f"Bora, {nome_atual}! Tô ligado.", "Vamos nessa! Manda o comando."]
        elif any(p in texto_w for p in ["ajude", "ajuda", "preciso", "socorro"]):
            acordando = [f"Pode contar comigo, {nome_atual}!", f"Tô aqui. Me conta."]
        elif any(p in texto_w for p in ["urgente", "rápido", "agora", "já"]):
            acordando = [f"Pronto! Fala rápido, {nome_atual}!", "Modo turbo! Diz aí!"]
        else:
            acordando = [
                f"Pode falar, {nome_atual}.", "Tô na escuta.", "Fala aí!",
                f"Opa! Me chamou?", "Ao seu dispor.", f"Pois não, {nome_atual}?",
            ]
        await falar_texto(random.choice(acordando))

        rec, mic_obj, mic_fonte = criar_sessao_microfone()
        ativado = True

        while ativado:
            comando = escutar_com_microfone_aberto(rec, mic_fonte, timeout_segundos=20)
            comando_lower = comando.lower() if comando else ""

            # --- Timeout de inatividade ---
            if comando == "TIMEOUT":
                n = ler_config_nome()
                await falar_texto(random.choice([
                    f"Ainda por aí, {n}? Precisa de mim?",
                    f"Tô esperando, {n}.",
                    "Quer continuar ou volto pro stand-by?",
                ]))
                resposta = escutar_com_microfone_aberto(rec, mic_fonte, timeout_segundos=10)
                resp_lower = resposta.lower() if resposta else ""

                if not resposta or any(p in resp_lower for p in ["não", "descansar", "agora não", "pode ir", "tchau"]):
                    await falar_texto(random.choice([
                        "Combinado! Qualquer coisa é só chamar.",
                        "Vou ficar nos bastidores. Precisando, grita.",
                        "Beleza. Fui pro stand-by!",
                    ]))
                    ativado = False
                    continue
                elif resposta != "TIMEOUT":
                    comando = resposta
                    comando_lower = resp_lower
                else:
                    await falar_texto("Voltando ao stand-by.")
                    ativado = False
                    continue

            elif not comando:
                continue

            # --- Comandos de controle (diretos, sem LLM) ---
            if "desligar sistema" in comando_lower:
                salvar_memoria(historico_curto)
                await falar_texto("Memória salva. Encerrando operações. Até logo.")
                fechar_microfone_global()
                return

            if any(p in comando_lower for p in ["descansar", "agora não", "pode ir", "vai descansar"]):
                salvar_memoria(historico_curto)
                await falar_texto(f"Combinado, {nome_atual}. Memória salva. É só me chamar.")
                ativado = False
                continue

            if any(p in comando_lower for p in ["limpa a memória", "apaga a memória", "esquece tudo", "reseta memória"]):
                historico_curto.clear()
                limpar_memoria()
                limpar_perfil()
                perfil = {"fatos": []}
                await falar_texto(f"Memória completa limpa, {nome_atual}. Começando do zero!")
                continue

            if any(p in comando_lower for p in ["o que você sabe sobre mim", "o que sabe de mim", "o que aprendeu"]):
                fatos = perfil.get("fatos", [])
                if fatos:
                    lista = ". ".join(fatos[:8])
                    await falar_texto(f"O que sei sobre você: {lista}")
                else:
                    await falar_texto(f"Ainda não sei muito sobre você, {nome_atual}. Vamos conversar mais!")
                continue

            # === ENVIAR AO LLM (Groq ou LM local) ===
            historico_curto.append({"role": "user", "content": comando})
            if len(historico_curto) > 30:
                historico_curto = historico_curto[-30:]

            try:
                print("🧠 [LangGraph] Processando agente...")
                resposta_texto, novas_msgs = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: perguntar_langchain(historico_curto, nome_atual, perfil)
                    ),
                    timeout=120.0  # 120s — LLM local e ferramentas podem demorar mais
                )

                historico_curto.extend(novas_msgs)
                print(f"🧠 [LangGraph]: {resposta_texto[:120]}...")
                
                # Falar e verificar se foi interrompido
                foi_interrompido = await falar_texto(resposta_texto)
                
                if foi_interrompido:
                    # Se foi interrompido, volta a escutar imediatamente
                    print("🔄 Retomando escuta após interrupção...")
                    nome_atual = ler_config_nome()
                    await falar_texto(f"Te escuto, {nome_atual}. Fala aí!")
                    rec, mic_obj, mic_fonte = criar_sessao_microfone()
                    continue  # Volta ao início do loop para escutar

                # Salvar memória de curto prazo
                salvar_memoria(historico_curto)

                # Aprendizado em background
                try:
                    perfil = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: aprender(client_llm, historico_curto, perfil)
                    )
                except Exception:
                    pass

            except (asyncio.TimeoutError, TimeoutError):
                print("⏰ LLM demorou muito — abortando limite de tempo")
                if historico_curto and historico_curto[-1]["role"] == "user":
                    historico_curto.pop()
                await falar_texto(random.choice([
                    "Demorou demais. Pode tentar de outra forma?",
                    "O processamento travou. Tenta de novo?",
                    "Não consegui processar a tempo. Reformula pra mim?",
                ]))
            except Exception as e:
                print(f"❌ Erro LLM: {str(e)}")
                if historico_curto and historico_curto[-1]["role"] == "user":
                    historico_curto.pop()
                await falar_texto("Tive um problema aqui. Pode repetir?")


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Seleção do provedor no início
    try:
        print("Escolha provedor de LLM:")
        print("  1) Groq (requer GROQ_API_KEY no .env)")
        print("  2) LM local (LM Studio) — exemplo: http://127.0.0.1:1234")
        escolha = input("Iniciar com [1=groq,2=local] (padrão 1): ").strip()

        if escolha in ["2", "local", "l"]:
            # LM Studio / OpenAI Compatível
            LM_URL = os.getenv("LOCAL_LM_URL", "http://127.0.0.1:1234/v1")
            LM_MODEL = os.getenv("LOCAL_LM_MODEL", "qwen/qwen3-vl-4b")
            
            client_llm = ChatOpenAI(base_url=LM_URL, api_key="lm-studio", model=LM_MODEL, temperature=0.2)
            print(f"Usando LangChain com LM local {LM_MODEL} em {LM_URL}")
        else:
            if not GROQ_API_KEY:
                raise ValueError("⚠️ GROQ_API_KEY não encontrada no arquivo .env! Defina-a ou escolha LM local.")
            
            client_llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.1-8b-instant", temperature=0.2)
            print("Usando LangChain com o Groq.")

        try:
            asyncio.run(iniciar_assistente())
        except KeyboardInterrupt:
            print("\nAssistente encerrado pelo usuário.")
            fechar_microfone_global()
    except Exception as e:
        print(f"Erro na inicialização: {e}")
