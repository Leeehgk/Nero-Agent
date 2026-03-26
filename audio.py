import os
import sys
import tempfile
import asyncio
import threading
import re
from typing import List, Optional

# Suporte a UTF-8 no Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
import speech_recognition as sr
import edge_tts
import pygame

# ==========================================
# CONFIGURAÇÃO DE AMBIENTE
# ==========================================

load_dotenv()

_mic_global: Optional[sr.Microphone] = None
_fonte_global: Optional[sr.AudioSource] = None
_rec_standby: Optional[sr.Recognizer] = None
_mic_lock = threading.Lock()


def inicializar_microfone_global() -> None:
    """Abre o microfone UMA VEZ no início do programa e mantém aberto."""
    global _mic_global, _fonte_global, _rec_standby
    _rec_standby = sr.Recognizer()
    _rec_standby.energy_threshold = 280
    _rec_standby.dynamic_energy_threshold = False
    _rec_standby.pause_threshold = 1.5  # Permite pausas longas (respirar)
    _rec_standby.phrase_threshold = 0.1
    _mic_global = sr.Microphone()
    _fonte_global = _mic_global.__enter__()
    _rec_standby.adjust_for_ambient_noise(_fonte_global, duration=0.8)
    print("🎙️ Microfone global inicializado. Sessão persistente ativa.")


def fechar_microfone_global() -> None:
    """Fecha o microfone ao encerrar o programa."""
    global _mic_global
    if _mic_global:
        try:
            _mic_global.__exit__(None, None, None)
        except Exception:
            pass


def esperar_palavra_ativacao(palavra_chave: str = "nero") -> str:
    """
    Escuta a wake word usando o microfone global (sempre aberto).
    Zero overhead de hardware — sem abrir/fechar mic, sem recalibrar.
    """
    variacoes: List[str] = [
        palavra_chave.lower(), "nero", "néro", "nerô",
        "neiro", "néiro", "nehru", "neuro", "mero", "zero",
        "nelo", "nélo", "nero ai", "ô nero", "ei nero",
    ]

    print(f"\n💤 Stand-by. Diga '{palavra_chave}' para ativar...")

    if _fonte_global is None:
        raise RuntimeError("Microfone global não inicializado. Chame inicializar_microfone_global() primeiro.")

    while True:
        try:
            audio: sr.AudioData = _rec_standby.listen(
                _fonte_global, timeout=None, phrase_time_limit=2.5
            )
            texto: str = _rec_standby.recognize_google(audio, language='pt-BR').lower()

            print(f"   (Ouvido: '{texto}')")

            if any(var in texto for var in variacoes):
                print("🔔 Wake Word detectada!")
                return texto

        except sr.UnknownValueError:
            pass
        except sr.WaitTimeoutError:
            pass
        except Exception:
            pass


def criar_sessao_microfone():
    """
    Retorna os objetos de sessão do microfone global já aberto.
    Para uso no loop de diálogo ativo — sem overhead de hardware.
    """
    rec = sr.Recognizer()
    rec.energy_threshold = 350
    rec.dynamic_energy_threshold = False
    rec.pause_threshold = 1.5  # Permite pausas longas (respirar)
    rec.phrase_threshold = 0.1
    return rec, _mic_global, _fonte_global


def escutar_com_microfone_aberto(
    reconhecedor: sr.Recognizer,
    fonte: sr.AudioSource,
    timeout_segundos: int = 20
) -> str:
    """Escuta usando microfone já aberto. Zero overhead de hardware."""
    print("🟢 Ouvindo...")
    try:
        audio: sr.AudioData = reconhecedor.listen(
            fonte, timeout=timeout_segundos, phrase_time_limit=15
        )
        texto: str = reconhecedor.recognize_google(audio, language='pt-BR')
        print(f"👤 Comando: {texto}")
        return texto
    except sr.WaitTimeoutError:
        print("⏳ Silêncio detectado.")
        return "TIMEOUT"
    except sr.UnknownValueError:
        print("❓ Não entendi.")
        return ""
    except Exception as e:
        print(f"❌ Erro de escuta: {str(e)}")
        return ""


# ==========================================
# TTS VIA EDGE TTS
# ==========================================

_tts_interrompido = threading.Event()
_tts_lock = asyncio.Lock()
_interrupcao_detectada = threading.Event()


def verificar_interrupcao() -> bool:
    """Retorna True se o usuário interrompeu a fala do agente."""
    if _interrupcao_detectada.is_set():
        _interrupcao_detectada.clear()
        return True
    return False


def _limpar_interrupcao() -> None:
    """Limpa o sinal de interrupção."""
    _interrupcao_detectada.clear()


def _limpar_texto_tts(texto: str) -> str:
    """Remove emojis, emoticons e marcadores de ação."""
    t = re.sub(r'[\U00010000-\U0010ffff]', '', texto)
    t = re.sub(r'[\u2600-\u27BF]', '', t)
    t = re.sub(r'\*[^*]+\*', '', t)
    t = re.sub(r'[:;=8][\-~]?[)D\(pP/\|\]\[]+', '', t)
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)
    t = re.sub(r'__(.*?)__', r'\1', t)
    return t.strip()


async def falar_texto(texto: str) -> bool:
    """
    Converte texto em áudio via Edge TTS e reproduz.
    - Interrupção por voz do usuário
    - Retry com backoff para erros TTS
    - Retorna True se foi interrompido pelo usuário, False caso contrário
    """
    global _tts_interrompido, _interrupcao_detectada

    texto_limpo = _limpar_texto_tts(texto)
    if not texto_limpo:
        return False

    print(f"🤖 Nero: {texto_limpo}")

    voz = "pt-BR-AntonioNeural"
    comunicador = edge_tts.Communicate(texto_limpo, voz, rate="+5%")
    arquivo_temp = tempfile.mktemp(suffix=".mp3")

    try:
        # Retry com backoff exponencial
        for tentativa in range(3):
            try:
                await comunicador.save(arquivo_temp)
                break
            except Exception as e_tts:
                if tentativa < 2:
                    import time as _t
                    _t.sleep(0.4 * (tentativa + 1))
                    comunicador = edge_tts.Communicate(texto_limpo, voz, rate="+5%")
                else:
                    raise e_tts

        pygame.mixer.init()
        pygame.mixer.music.load(arquivo_temp)

        _tts_interrompido.clear()
        _interrupcao_detectada.clear()
        is_playing = True
        foi_interrompido = False

        def checar_interrupcao() -> None:
            """Thread que monitora microfone para interrupção imediata."""
            nonlocal foi_interrompido
            try:
                import time
                
                # Verificar pygame antes de abrir microfone
                if not pygame.mixer.get_init():
                    return
                
                # Criar nova sessão de microfone para esta thread
                mic_temp = None
                mic_fonte = None
                try:
                    mic_temp = sr.Microphone()
                    mic_fonte = mic_temp.__enter__()
                    
                    rec_int = sr.Recognizer()
                    rec_int.energy_threshold = 300
                    rec_int.dynamic_energy_threshold = True

                    time.sleep(0.4)
                    print("👂 [Interrupção] Monitorando...")

                    while is_playing and pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                        try:
                            audio = rec_int.listen(mic_fonte, timeout=0.2, phrase_time_limit=0.3)
                            texto = rec_int.recognize_google(audio, language='pt-BR')
                            if texto and len(texto.strip()) > 1:
                                print(f"\n🛑 INTERRUPÇÃO! Oouvé: '{texto}'")
                                pygame.mixer.music.stop()
                                _tts_interrompido.set()
                                _interrupcao_detectada.set()
                                foi_interrompido = True
                                break
                        except (sr.WaitTimeoutError, sr.UnknownValueError):
                            continue
                        except Exception as e:
                            print(f"⚠️ [Inter] Erro: {type(e).__name__}: {e}")
                            break
                except Exception as e:
                    print(f"⚠️ [Inter] Erro geral: {type(e).__name__}: {e}")
                finally:
                    if mic_fonte and mic_temp:
                        try:
                            mic_temp.__exit__(None, None, None)
                        except:
                            pass
                        
            except Exception as e:
                import traceback
                print(f"⚠️ [Interrupção] Erro na thread: {type(e).__name__}: {e}")
                traceback.print_exc()

        t_int = threading.Thread(target=checar_interrupcao, daemon=True)
        t_int.start()

        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)

        is_playing = False
        t_int.join(timeout=0.2)

        return foi_interrompido

    except Exception as e:
        print(f"❌ Erro de áudio: {str(e)}")
        return False
    finally:
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        if os.path.exists(arquivo_temp):
            try:
                os.remove(arquivo_temp)
            except Exception:
                pass
