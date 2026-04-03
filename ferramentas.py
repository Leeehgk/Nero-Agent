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

from langchain_core.tools import tool
import pywhatkit
import pyautogui
from PIL import ImageGrab

# ==========================================
# CONTROLE DE JANELAS (Win32 API)
# ==========================================

_janelas_ocultas = []  # Guarda handles das janelas ocultadas

def _obter_hwnd_janelas_visiveis():
    """Retorna lista de handles de janelas visíveis (exceto Taskbar e Desktop)."""
    if sys.platform != 'win32':
        return []
    import ctypes
    import ctypes.wintypes

    janelas = []
    BLACKLIST_CLASSES = {"Shell_TrayWnd", "Progman", "WorkerW", "DV2ControlHost", "Windows.UI.Core.CoreWindow"}

    def enum_callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            class_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, class_buf, 256)
            if class_buf.value not in BLACKLIST_CLASSES:
                janelas.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return janelas


# ==========================================
# FERRAMENTAS — Funções Python puras
# ==========================================

@tool
def tocar_youtube(pesquisa: str) -> str:
    """
    TOQUE MÚSICA NO YOUTUBE.
    Use quando usuário disser: 'tocar', 'colocar pra tocar', 'ouvir', 'youtube' ou pedir um artista.
    Parâmetro 'pesquisa' é o que o usuário quer ouvir (ex: 'Red Hot Chili Peppers', 'música tranquila').
    Abre o YouTube diretamente no navegador padrão com a busca especificada.
    """
    print(f"🔍 [YouTube] Procurando: {pesquisa}")

    # Método 1: pywhatkit (padrão) — abre e toca o primeiro resultado
    try:
        pywhatkit.playonyt(pesquisa)
        print("✅ [YouTube] pywhatkit executou com sucesso")
        return f"Tocando '{pesquisa}' no YouTube!"
    except Exception as e1:
        print(f"⚠️ [YouTube] pywhatkit falhou: {e1}")

    # Método 2: webbrowser direto com resultados de busca
    try:
        pesquisa_encoded = urllib.parse.quote(pesquisa)
        url = f"https://www.youtube.com/results?search_query={pesquisa_encoded}"
        webbrowser.open(url)
        print(f"✅ [YouTube] webbrowser abriu: {url}")
        return f"Tocando '{pesquisa}' no YouTube!"
    except Exception as e2:
        print(f"⚠️ [YouTube] webbrowser falhou: {e2}")

    # Método 3: subprocess com Chrome (fallback Windows)
    try:
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            pesquisa_encoded = urllib.parse.quote(pesquisa)
            url = f"https://www.youtube.com/results?search_query={pesquisa_encoded}"
            subprocess.Popen([chrome_path, url])
            print("✅ [YouTube] Chrome abriu diretamente")
            return f"Tocando '{pesquisa}' no YouTube!"
    except Exception as e3:
        print(f"⚠️ [YouTube] Chrome falhou: {e3}")

    return f"Não consegui abrir '{pesquisa}' no YouTube. Verifique se o Chrome está instalado."


@tool
def pausar_youtube() -> str:
    """
    PAUSA A MÚSICA/VÍDEO NO YOUTUBE.
    Use quando o usuário disser: 'pausar', 'pause', 'para a música', 'para o vídeo', 'parar'.
    Simula a tecla Espaço na janela do Chrome/YouTube para pausar.
    """
    try:
        # A tecla 'space' só funciona se o navegador do YouTube estiver focado na tela.
        # A tecla 'playpause' (mídia) do teclado envia o comando de pausa em nível global no Windows,
        # funcionando mesmo com o YouTube escondido em segundo plano no Chrome.
        pyautogui.press("playpause")
        return "Música pausada! ⏸️"
    except Exception as e:
        return f"Erro ao pausar: {str(e)}"


@tool
def tocar_pausar_midia() -> str:
    """
    ALTERNA ENTRE PLAY E PAUSE NA MÍDIA ATUAL.
    Use quando o usuário disser: 'play', 'continuar', 'tocar', 'pausar', 'pause',
    'para a música', 'continua a música', 'toggle play'.
    Usa a tecla de mídia PlayPause do teclado.
    """
    try:
        pyautogui.press("playpause")
        return "Play/Pause alternado! ▶️⏸️"
    except Exception as e:
        return f"Erro no play/pause: {str(e)}"


@tool
def proxima_faixa() -> str:
    """
    PULA PARA A PRÓXIMA FAIXA/MÚSICA/VÍDEO.
    Use quando o usuário disser: 'próxima', 'pular', 'skip', 'avançar música', 'passa a música'.
    """
    try:
        pyautogui.press("nexttrack")
        return "Pulei para a próxima faixa! ⏭️"
    except Exception as e:
        return f"Erro ao pular faixa: {str(e)}"


@tool
def faixa_anterior() -> str:
    """
    VOLTA PARA A FAIXA/MÚSICA/VÍDEO ANTERIOR.
    Use quando o usuário disser: 'anterior', 'voltar música', 'música anterior', 'volta'.
    """
    try:
        pyautogui.press("prevtrack")
        return "Voltei para a faixa anterior! ⏮️"
    except Exception as e:
        return f"Erro ao voltar faixa: {str(e)}"


@tool
def controlar_midia(acao: str) -> str:
    """
    CONTROLA MÍDIA DO COMPUTADOR.
    Use quando usuário disser: 'pausar', 'parar', 'pause' (pausar).
    'tocar', 'play', 'continuar' (voltar a tocar).
    'próxima', 'pular', 'skip' (próxima faixa).
    'anterior', 'voltar' (faixa anterior).
    """
    try:
        acao_lower = acao.lower()
        if acao_lower in ["pausar", "tocar", "play", "pause", "play/pause", "toggle"]:
            pyautogui.press("playpause")
            return "Play/Pause executado. ▶️⏸️"
        elif acao_lower in ["proximo", "próximo", "pular", "skip", "avançar"]:
            pyautogui.press("nexttrack")
            return "Próxima faixa. ⏭️"
        elif acao_lower in ["anterior", "voltar", "volta"]:
            pyautogui.press("prevtrack")
            return "Faixa anterior. ⏮️"
        else:
            return f"Ação '{acao}' não suportada. Use: pausar, tocar, proximo, anterior."
    except Exception as e:
        return f"Erro ao controlar mídia: {str(e)}"


@tool
def esconder_todas_janelas() -> str:
    """
    ESCONDE/MINIMIZA TODAS AS JANELAS ABERTAS (mostra a área de trabalho).
    Use quando o usuário disser: 'esconde as janelas', 'minimiza tudo', 'mostra a área de trabalho',
    'limpa a tela', 'esconde tudo', 'oculta as janelas'.
    Guarda a lista de janelas para restaurar depois.
    """
    global _janelas_ocultas
    try:
        if sys.platform == 'win32':
            import ctypes
            # Win+D — mostra área de trabalho (toggle)
            # Método robusto: minimizar cada janela individualmente
            janelas = _obter_hwnd_janelas_visiveis()
            SW_MINIMIZE = 6
            _janelas_ocultas = []
            for hwnd in janelas:
                try:
                    ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
                    _janelas_ocultas.append(hwnd)
                except Exception:
                    pass
            return f"Todas as {len(_janelas_ocultas)} janelas foram minimizadas! 🖥️ Área de trabalho limpa."
        else:
            # Linux/Mac: usa xdotool ou equivalente
            subprocess.run(["xdotool", "key", "super+d"], check=False)
            return "Janelas minimizadas! Área de trabalho limpa. 🖥️"
    except Exception as e:
        return f"Erro ao esconder janelas: {str(e)}"


@tool
def restaurar_todas_janelas() -> str:
    """
    RESTAURA TODAS AS JANELAS QUE FORAM ESCONDIDAS/MINIMIZADAS.
    Use quando o usuário disser: 'restaura as janelas', 'abre as janelas de volta',
    'restaura tudo', 'volta as janelas', 'mostra as janelas'.
    Restaura janelas que foram escondidas anteriormente.
    """
    global _janelas_ocultas
    try:
        if sys.platform == 'win32':
            import ctypes
            SW_RESTORE = 9
            if _janelas_ocultas:
                restauradas = 0
                for hwnd in _janelas_ocultas:
                    try:
                        if ctypes.windll.user32.IsWindow(hwnd):
                            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                            restauradas += 1
                    except Exception:
                        pass
                _janelas_ocultas = []
                return f"Restaurei {restauradas} janela(s)! 🪟 Tudo de volta."
            else:
                # Se não há janelas salvas, tenta Win+D para alternar
                pyautogui.hotkey('win', 'd')
                return "Tentei restaurar as janelas com Win+D! 🪟"
        else:
            subprocess.run(["xdotool", "key", "super+d"], check=False)
            return "Janelas restauradas! 🪟"
    except Exception as e:
        return f"Erro ao restaurar janelas: {str(e)}"


@tool
def alternar_janelas() -> str:
    """
    ALTERNA ENTRE MOSTRAR ÁREA DE TRABALHO E RESTAURAR JANELAS (Win+D).
    Use quando o usuário disser: 'alterna janelas', 'Win+D', 'toggle área de trabalho'.
    """
    try:
        pyautogui.hotkey('win', 'd')
        return "Alternado entre área de trabalho e janelas! 🪟"
    except Exception as e:
        return f"Erro: {str(e)}"


@tool
def alterar_volume(acao: str) -> str:
    """Altera o volume do sistema Windows. Use quando o usuário pedir para aumentar, diminuir ou mutar o volume."""
    try:
        acao_lower = acao.lower()
        if acao_lower in ["aumentar", "mais", "up", "aumenta"]:
            for _ in range(5):
                pyautogui.press("volumeup")
            return "Volume aumentado. 🔊"
        elif acao_lower in ["diminuir", "menos", "down", "abaixar", "diminui"]:
            for _ in range(5):
                pyautogui.press("volumedown")
            return "Volume reduzido. 🔉"
        elif acao_lower in ["mutar", "mudo", "mute"]:
            pyautogui.press("volumemute")
            return "Volume mutado/desmutado. 🔇"
        else:
            return f"Ação '{acao}' não reconhecida. Use: aumentar, diminuir, mutar."
    except Exception as e:
        return f"Erro ao alterar volume: {str(e)}"


@tool
def obter_data_hora() -> str:
    """Retorna a data e hora atuais. Use quando o usuário perguntar que dia é, que horas são, etc."""
    agora = datetime.datetime.now()
    dias: List[str] = [
        "Segunda-feira", "Terça-feira", "Quarta-feira",
        "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"
    ]
    return f"Hoje é {dias[agora.weekday()]}, {agora.strftime('%d/%m/%Y %H:%M')}."


@tool
def obter_clima(cidade: str) -> str:
    """Retorna a temperatura e condição climática de uma cidade. Use quando perguntarem sobre clima, tempo, temperatura."""
    try:
        url = f"https://wttr.in/{cidade}?format=3"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return f"Clima: {resp.text.strip()}"
        return f"Não foi possível obter o clima para {cidade}."
    except Exception as e:
        return f"Erro ao consultar clima: {str(e)}"


@tool
def ler_noticias_dia() -> str:
    """Lê um resumo das principais notícias do dia. Use quando o usuário perguntar sobre 'notícias', 'manchetes', 'o que aconteceu hoje'."""
    try:
        from ddgs import DDGS
        resultados = list(DDGS().news(keywords="brasil", region="pt-br", safesearch="off", time="d", max_results=4))
        if not resultados:
            return "Não consegui encontrar as notícias de hoje. Tente pesquisar na web."
        resumo = "Aqui estão as principais notícias de hoje: "
        for i, r in enumerate(resultados):
            titulo = r.get("title", "sem título")
            resumo += f"{i+1}: {titulo}. "
        return resumo.strip()
    except Exception as e:
        return f"Erro ao buscar notícias: {str(e)}"


@tool
def pesquisar_web(query: str) -> str:
    """Pesquisa na internet sobre qualquer assunto. Use quando o usuário pedir para pesquisar, buscar informação ou quando você não souber a resposta."""
    try:
        from ddgs import DDGS
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


@tool
def abrir_navegador(url: str) -> str:
    """Abre o navegador em uma URL específica. Use quando pedirem para abrir um site (ex: google.com, youtube.com)."""
    try:
        if not url.startswith("http"):
            url = f"https://{url}"
        webbrowser.open(url)
        return f"Navegador aberto em: {url}"
    except Exception as e:
        return f"Erro ao abrir navegador: {str(e)}"


@tool
def abrir_programa(nome: str) -> str:
    """Abre um programa do Windows (calculadora, bloco de notas, paint, explorador, terminal, configurações)."""
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
        if ":" in cmd:
            os.startfile(cmd)
        else:
            subprocess.Popen(cmd, shell=True)
        return f"Programa '{nome}' aberto."
    except Exception as e:
        return f"Erro ao abrir '{nome}': {str(e)}"


@tool
def fechar_programa(nome: str) -> str:
    """Fecha um programa do Windows que está aberto. Use quando o usuário pedir para fechar ou encerrar um programa."""
    programas = {
        "calculadora": "CalculatorApp.exe",
        "bloco de notas": "notepad.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
        "explorador": "explorer.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "terminal": "WindowsTerminal.exe",
        "configurações": "SystemSettings.exe",
        "configuracoes": "SystemSettings.exe",
    }
    try:
        nome_lower = nome.lower().strip()
        proc_name = programas.get(nome_lower, f"{nome_lower}.exe" if not nome_lower.endswith(".exe") else nome_lower)
        resultado = subprocess.run(f"taskkill /F /IM {proc_name} /T", shell=True, capture_output=True, text=True)
        if resultado.returncode != 0 and nome_lower == "calculadora":
            resultado = subprocess.run("taskkill /F /IM calc.exe /T", shell=True, capture_output=True, text=True)
        if resultado.returncode == 0:
            return f"Programa '{nome}' fechado."
        else:
            return f"Não foi possível fechar '{nome}'. Talvez não esteja aberto."
    except Exception as e:
        return f"Erro ao fechar '{nome}': {str(e)}"


@tool
def capturar_tela() -> str:
    """Tira um print/screenshot da tela inteira. Use APENAS quando pedirem explicitamente para tirar um print."""
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


@tool
def criar_anotacao(texto: str) -> str:
    """Salva uma anotação/lembrete em arquivo de texto. Use quando pedirem para anotar, salvar, registrar algo."""
    try:
        caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anotacoes_nero.txt")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(f"[{agora}] {texto}\n")
        return f"Anotação salva: '{texto}'"
    except Exception as e:
        return f"Erro ao anotar: {str(e)}"


@tool
def obter_musica_atual() -> str:
    """
    INFORMA QUAL MÚSICA/VÍDEO ESTÁ TOCANDO ATUALMENTE.
    Use quando o usuário perguntar: 'que música é essa?', 'o que está tocando?', 'qual o nome da música'.
    """
    if sys.platform != 'win32':
        return "Só consigo verificar a mídia atual no Windows."
    
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        import asyncio
        
        async def _obter_info():
            try:
                manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
                session = manager.get_current_session()
                if not session:
                    return "Não há nada tocando no momento."
                
                info = await session.try_get_media_properties_async()
                titulo = info.title
                artista = info.artist
                
                if titulo and artista:
                    return f"A música atual é '{titulo}' do artista '{artista}' 🎵"
                elif titulo:
                    return f"Está tocando: '{titulo}' 🎵"
                else:
                    return "Tem uma mídia tocando, mas o aplicativo não forneceu o nome da faixa."
            except Exception as e:
                return f"Erro interno ao ler mídia: {e}"

        novo_loop = asyncio.new_event_loop()
        resultado = novo_loop.run_until_complete(_obter_info())
        novo_loop.close()
        return resultado

    except ImportError:
        return "A biblioteca 'winsdk' não está instalada. Avise ao usuário para executar: pip install winsdk"
    except Exception as e:
        return f"Não consegui pegar a música. Erro: {str(e)}"


# ==========================================
# FERRAMENTAS DO AGENTE (LANGCHAIN)
# ==========================================

FERRAMENTAS_LANGCHAIN = [
    # YouTube & Mídia
    tocar_youtube,
    pausar_youtube,
    tocar_pausar_midia,
    proxima_faixa,
    faixa_anterior,
    controlar_midia,
    alterar_volume,
    obter_musica_atual,
    # Janelas
    esconder_todas_janelas,
    restaurar_todas_janelas,
    alternar_janelas,
    # Sistema
    obter_data_hora,
    obter_clima,
    ler_noticias_dia,
    pesquisar_web,
    abrir_navegador,
    abrir_programa,
    fechar_programa,
    capturar_tela,
    criar_anotacao,
]
