# Validação do Nero

Faça esta etapa com o aplicativo aquecido e um headset. Não altere o modelo ou
os limites no meio da sessão.

1. Complete 30 turnos: 10 frases curtas, 10 médias e 10 longas.
2. Inclua pausas naturais em pelo menos 6 frases e ruído moderado em 6.
3. Marque apenas quantas transcrições conservaram o sentido; não salve o texto.
4. Interrompa pelo menos 5 respostas e meça do início da fala até o áudio parar.
5. Dê notas de 1 a 5 a dez respostas, considerando naturalidade, ausência de
   Markdown falado e falta de repetição.
6. Desative a rede e faça mais três conversas. O LM Studio deve continuar em
   `127.0.0.1:1234`; qualquer fallback de nuvem é considerado falha.

Veja primeiro as etapas de latência:

```powershell
.\.venv\Scripts\python.exe report_metrics.py
```

Depois feche a aceitação substituindo os exemplos pelos valores observados:

```powershell
.\.venv\Scripts\python.exe validate_session.py `
  --semantic-correct 28 `
  --naturalness 4,4,5,4,4,5,4,4,4,5 `
  --interruptions-ms 145,152,138,161,149
```

O validador só aprova com 30 turnos completos, p50 até 700 ms, p95 até
1.000 ms, semântica mínima de 90%, naturalidade média mínima 4/5 e p95 de
interrupção até 250 ms.
