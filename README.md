# Nero local

Assistente de conversa por voz que funciona offline no Windows. O LM Studio
gera a resposta, Faster Whisper reconhece a fala e Kokoro ONNX produz a voz.
Nenhuma conversa é enviada para serviços externos.

## Requisitos

- Windows 10 ou 11
- Python 3.11
- LM Studio 0.4 ou mais recente
- Headset com microfone
- NVIDIA RTX 4050 6 GB ou equivalente

## Instalação

Abra PowerShell nesta pasta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

O instalador cria `.venv`, instala as dependências e baixa os modelos. A
internet só é necessária nessa etapa.

O Kokoro usa o modelo FP32 na CPU. Nesta máquina ele iniciou o áudio
consideravelmente mais rápido que a variante INT8, e fica isolado da GPU usada
pelo Qwen.

No LM Studio, mantenha o servidor em `127.0.0.1:1234`, com CORS desativado.
Desative também **Log sensitive data**. O aplicativo carrega e aquece o Qwen
3.5 9B instalado localmente; o Qwen 4B fica como perfil de reserva.

## Executar

```powershell
.\run_nero.ps1
```

Esse comando inicia e verifica automaticamente o servidor local do LM Studio
antes de abrir o Nero. Para iniciar somente o servidor:

```powershell
.\start_lmstudio.ps1
```

Ao clicar em **Encerrar**, o Nero descarrega os modelos, para a API local e
encerra o daemon `llmster`. Para executar essa limpeza manualmente:

```powershell
.\stop_lmstudio.ps1
```

Espere o estado mudar de **Inicializando** para **Ouvindo**. A primeira carga
não faz parte da medição. Fale normalmente; não é necessário dizer “Nero”.

- **Pausar** desliga a captura lógica do microfone.
- **Nova conversa** descarta o contexto mantido pelo LM Studio.
- Para interromper uma resposta, comece a falar usando o headset.

## Latência

A janela mostra a última latência, p50 e p95. O tempo começa no último frame
de voz detectado e termina na primeira escrita de áudio:

```powershell
.\.venv\Scripts\python.exe report_metrics.py
```

A meta só é declarada atingida após 30 turnos válidos, com p50 até 700 ms e
p95 até 1.000 ms. Os registros em `logs/metrics.jsonl` contêm apenas tempos,
contagens de tokens e tipos de erro — nunca transcrições ou áudio.

## Ajustes

Edite `settings.toml` para selecionar dispositivos de áudio ou calibrar o VAD.
O valor `-1` usa o dispositivo padrão do Windows. Para listar dispositivos:

```powershell
.\.venv\Scripts\python.exe -c "import pyaudio; p=pyaudio.PyAudio(); [print(i, p.get_device_info_by_index(i)['name']) for i in range(p.get_device_count())]; p.terminate()"
```

O perfil atual prioriza inteligência e mantém o Qwen 9B mesmo quando a meta de
latência falhar (`auto_fallback = false`). O Qwen 4B permanece instalado para
troca manual. O Whisper `tiny` também está disponível, mas só deve substituir o
`base` após validação de transcrição.

## Privacidade e recuperação

Em execução, todos os modelos usam arquivos locais e o cliente aceita somente
uma URL loopback para o LM Studio. O protótipo anterior está preservado em
`_legacy_backup_20260726_nero.zip`.

O roteiro para fechar a aceitação de 30 turnos, semântica, naturalidade,
interrupção e operação sem rede está em `VALIDATION.md`.

Se o Nero mostrar que o microfone está sem sinal, pressione uma vez o botão
`MIC` do H510-PRO, confirme que a haste removível está totalmente encaixada e
prefira o modo 2,4 GHz pelo dongle USB. O aplicativo rejeita áudio quase
silencioso em vez de deixar o Whisper inventar palavras.
