# 🤖 Nero Agent — Assistente Pessoal de IA por Voz

Assistente pessoal de IA ativado por voz, com **inteligência autônoma** via Groq (Llama 3.1 8B), **memória de longo prazo** e **12 ferramentas** que ele decide sozinho quando usar.

> Fala Português do Brasil 🇧🇷 · Voz neural Edge TTS · Roda 100% local no Windows

---

## ✨ Funcionalidades

### 🧠 Inteligência
- **Groq + Function Calling** — O LLM analisa o que você diz e decide sozinho se precisa executar uma ação ou apenas conversar
- **Memória de longo prazo** — Aprende fatos sobre você (nome, preferências, hábitos) e lembra entre sessões
- **Memória de curto prazo** — Histórico das últimas 30 mensagens persistido em JSON
- **Aprendizado contínuo** — Após cada conversa, o Groq extrai automaticamente novos fatos sobre você

### 🎤 Voz
- **Wake Word** — Diga "Nero" para ativar (com variações de pronúncia)
- **TTS Edge Neural** — Voz natural em Português (`pt-BR-AntonioNeural`)
- **Interrupção por voz** — Fale durante a resposta para interromper imediatamente
- **Microfone persistente** — Zero latência de hardware (mic aberto durante toda a sessão)

### 🛠️ 12 Ferramentas Autônomas

O Nero decide sozinho quando usar cada ferramenta:

| Ferramenta | Comando exemplo |
|------------|----------------|
| 🎵 Tocar no YouTube | *"toca Red Hot no YouTube"* |
| ⏯️ Controlar Mídia | *"pausa a música"* / *"próxima faixa"* |
| 🔊 Alterar Volume | *"aumenta o volume"* / *"mutar"* |
| 💻 Abrir Programa | *"abre a calculadora"* |
| ❌ Fechar Programa | *"fecha o bloco de notas"* |
| 📰 Notícias do Dia | *"quais são as notícias de hoje?"* |
|  Data e Hora | *"que horas são?"* / *"que dia é hoje?"* |
| 🌤️ Clima | *"como está o clima em São Paulo?"* |
| 🔍 Pesquisa Web | *"pesquisa sobre inteligência artificial"* |
| 🌐 Abrir Navegador | *"abre o GitHub"* |
| 📸 Capturar Tela | *"tira um print"* |
| 📝 Criar Anotação | *"anota: reunião às 15h"* |

### 🗣️ Comandos de Controle por Voz

| Comando | Ação |
|---------|------|
| *"Nero"* | Ativa o assistente (wake word) |
| *"vai descansar"* | Volta ao stand-by |
| *"desligar sistema"* | Encerra o programa |
| *"o que você sabe sobre mim?"* | Lista fatos aprendidos |
| *"limpa a memória"* / *"esquece tudo"* | Reseta memória completa |

---

## 📁 Estrutura do Projeto

```
Eon-Agent/
├── agente_local.py     ← Loop principal + Groq function calling
├── ferramentas.py      ← 9 ferramentas + schemas para o LLM
├── memoria.py          ← Memória de curto prazo + longo prazo + aprendizado
├── audio.py            ← Microfone global, TTS Edge, wake word, interrupção
├── config_eon.json     ← Configuração do nome do usuário
├── memoria_nero.json   ← Memória de curto prazo (auto-gerado)
├── perfil_nero.json    ← Memória de longo prazo — fatos aprendidos (auto-gerado)
└── README.md
```

---

## ⚙️ Instalação

### Pré-requisitos
- Python 3.10+
- Windows 10/11
- Microfone

### Dependências

```bash
python -m pip install groq SpeechRecognition edge-tts pygame pywhatkit pyautogui Pillow requests duckduckgo-search
```

---

## 🚀 Como Usar

```bash
cd C:\Eon-Agent
python agente_local.py
```

1. O Nero inicia e fica em **stand-by** 💤
2. Diga **"Nero"** para ativar
3. Converse ou peça ações naturalmente
4. Diga **"vai descansar"** para voltar ao stand-by
5. Diga **"desligar sistema"** para encerrar

---

## 🔑 Configuração

### Arquivo .env
O projeto utiliza um arquivo `.env` para gerenciar chaves de API e configurações sensíveis.
1. Copie o arquivo `.env.example` para `.env`.
2. Insira sua `GROQ_API_KEY` no arquivo `.env`.

> [!CAUTION]
> Nunca envie seu arquivo `.env` para o GitHub. Ele já está configurado no `.gitignore`.

### Configurações Adicionais
- **Groq**: Pegue sua chave em [console.groq.com](https://console.groq.com).
- **Nome do Usuário**: Edite `config_eon.json`.

---

## 🧠 Como Funciona a Inteligência

### Function Calling (Intenções)
```
Usuário: "toca Metallica no YouTube"
  ↓
Groq analisa → detecta intenção → chama tocar_youtube("Metallica")
  ↓
Função executa → retorna resultado
  ↓
Groq formula resposta: "Colocando Metallica no YouTube!"
```

### Aprendizado de Longo Prazo
```
Conversa: "me chame de Mestre"
  ↓
Groq responde normalmente
  ↓
2ª chamada (background): analisa e extrai → "O usuário quer ser chamado de Mestre"
  ↓
Salva em perfil_nero.json → próxima sessão já lembra
```

---

## 🛣️ Roadmap

- [x] Groq como cérebro (substituiu Google AI)
- [x] Wake word + TTS + interrupção por voz
- [x] Memória de curto prazo persistente
- [x] Memória de longo prazo com aprendizado via LLM
- [x] Function calling — 9 ferramentas autônomas
- [ ] Controle de abas do Chrome por nome
- [ ] Modo programação (IDE automation)
- [ ] Visão computacional (OCR/Tesseract)
- [ ] Rotinas automáticas baseadas em padrões do usuário
