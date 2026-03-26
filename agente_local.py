import os
import json
import asyncio
import random
from typing import List, Dict, Any

from dotenv import load_dotenv
from groq import Groq

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
from ferramentas import TOOL_SCHEMAS, TOOL_FUNCTIONS

# ==========================================
# CONFIGURAÇÃO E AMBIENTE
# ==========================================

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("⚠️ GROQ_API_KEY não encontrada no arquivo .env!")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
# CLIENTE GROQ + FUNCTION CALLING
# ==========================================

client = Groq(api_key=GROQ_API_KEY)


def montar_system_prompt(nome_usuario: str, perfil: Dict[str, Any]) -> Dict[str, str]:
    fatos_texto = formatar_fatos_para_prompt(perfil)

    return {
        "role": "system",
        "content": f"""Você é o Nero, assistente pessoal de IA do usuário '{nome_usuario}'.

REGRAS CRUCIAIS PARA AÇÕES:
- Se usuário disser "tocar", "colocar música", "ouvir", "escutar", "youtube", "red hot", "spotify", "deezer", use a ferramenta 'tocar_youtube'. O parâmetro 'pesquisa' deve conter o que o usuário quer ouvir (ex: "Red Hot Chili Peppers", "música feliz", "rock clássico").
- Se usuário disser "pausar", "parar música", "stop", use 'controlar_midia' com acao='pausar'.
- Se usuário disser "tocar" (após pausa), "play", use 'controlar_midia' com acao='tocar'.
- Se usuário disser "próxima", "pular", "skip", use 'controlar_midia' com acao='proximo'.

PERSONALIDADE:
1. Descolado, direto, animado, empático. Como um amigo expert.
2. Fale sempre Português do Brasil. Tom natural, moderno e CONCISO.
3. Respostas CURTAS — você fala em voz, não escreve textos longos.
4. Se não souber algo, diga diretamente. Não enrole.
5. Seu nome é Nero.
6. USE as ferramentas quando o usuário pedir ações.
7. Para conversa casual, responda naturalmente sem ferramentas.{fatos_texto}"""
    }


def perguntar_groq(
    historico: List[Dict[str, str]],
    nome_usuario: str,
    perfil: Dict[str, Any]
) -> str:
    """
    Envia o histórico ao Groq com ferramentas disponíveis.
    Se o Groq decidir usar uma ferramenta, executa e retorna a resposta final.
    """
    mensagens = [montar_system_prompt(nome_usuario, perfil)] + historico

    # 1ª chamada — Groq decide se usa ferramenta ou responde direto
    resposta = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=mensagens,
        tools=TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=0.2,
        max_tokens=500,
    )

    msg = resposta.choices[0].message

    # Se NÃO chamou ferramenta, retorna resposta direta
    if not msg.tool_calls:
        return msg.content.strip() if msg.content else "Não consegui processar."

    # Se chamou ferramenta(s), executa cada uma
    print(f"🔧 [Tools] {len(msg.tool_calls)} ferramenta(s) detectada(s)")

    # Adicionar a mensagem do assistant com tool_calls ao histórico
    mensagens.append({
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            }
            for tc in msg.tool_calls
        ]
    })

    for tool_call in msg.tool_calls:
        nome_func = tool_call.function.name
        args_json = tool_call.function.arguments

        try:
            args = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError:
            args = {}

        print(f"   ⚡ Executando: {nome_func}({args})")

        # Executar a função
        func = TOOL_FUNCTIONS.get(nome_func)
        if func:
            try:
                resultado = func(**args)
            except Exception as e:
                resultado = f"Erro ao executar {nome_func}: {str(e)}"
        else:
            resultado = f"Ferramenta '{nome_func}' não encontrada."

        print(f"   ✅ Resultado: {resultado[:100]}...")

        # Adicionar resultado da ferramenta ao histórico
        mensagens.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": resultado
        })

    # 2ª chamada — Groq formula resposta natural com o resultado da ferramenta
    resposta_final = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=mensagens,
        temperature=0.2,
        max_tokens=300,
    )

    return resposta_final.choices[0].message.content.strip()


# ==========================================
# LOOP PRINCIPAL
# ==========================================

async def iniciar_assistente() -> None:
    palavra_de_ativacao = "Nero"

    print("🎙️ Inicializando microfone global...")
    inicializar_microfone_global()

    # Carregar memórias
    historico_curto: List[Dict[str, str]] = carregar_memoria()
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

            # === ENVIAR AO GROQ (com ferramentas) ===
            historico_curto.append({"role": "user", "content": comando})
            if len(historico_curto) > 30:
                historico_curto = historico_curto[-30:]

            try:
                print("🧠 [Groq] Processando...")
                resposta_texto = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: perguntar_groq(historico_curto, nome_atual, perfil)
                    ),
                    timeout=20.0  # 20s — tool calls podem demorar um pouco mais
                )

                historico_curto.append({"role": "assistant", "content": resposta_texto})
                print(f"🧠 [Groq]: {resposta_texto[:120]}...")
                
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
                        lambda: aprender(client, historico_curto, perfil)
                    )
                except Exception:
                    pass

            except asyncio.TimeoutError:
                print("⏰ Groq travou — abortando após 20s")
                if historico_curto and historico_curto[-1]["role"] == "user":
                    historico_curto.pop()
                await falar_texto(random.choice([
                    "Demorou demais. Pode tentar de outra forma?",
                    "O processamento travou. Tenta de novo?",
                    "Não consegui processar a tempo. Reformula pra mim?",
                ]))
            except Exception as e:
                print(f"❌ Erro Groq: {str(e)}")
                if historico_curto and historico_curto[-1]["role"] == "user":
                    historico_curto.pop()
                await falar_texto("Tive um problema aqui. Pode repetir?")


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(iniciar_assistente())
    except KeyboardInterrupt:
        print("\nAssistente encerrado pelo usuário.")
        fechar_microfone_global()
