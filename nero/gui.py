from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, ttk

from nero.config import AppSettings
from nero.controller import NeroController, UIEvent


COLORS = {
    "bg": "#0b1020",
    "panel": "#141b2d",
    "panel_alt": "#1b2438",
    "text": "#f4f7fb",
    "muted": "#94a3b8",
    "accent": "#38bdf8",
    "good": "#34d399",
    "warn": "#fbbf24",
    "error": "#fb7185",
}


class NeroWindow:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.root = tk.Tk()
        self.root.title("Nero — IA local")
        self.root.geometry("820x610")
        self.root.minsize(680, 520)
        self.root.configure(bg=COLORS["bg"])
        self.events: queue.Queue[UIEvent] = queue.Queue()
        self.controller = NeroController(settings, self.events)
        self._paused = False
        self._closing = False
        self._voice_ids: dict[str, str] = {}
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def run(self) -> None:
        self.controller.start()
        self.root.after(30, self._poll)
        self.root.mainloop()

    def _build(self) -> None:
        top = tk.Frame(self.root, bg=COLORS["bg"], padx=24, pady=18)
        top.pack(fill="x")
        tk.Label(
            top,
            text="NERO",
            font=("Segoe UI Semibold", 22),
            fg=COLORS["text"],
            bg=COLORS["bg"],
        ).pack(side="left")
        tk.Label(
            top,
            text="LOCAL",
            font=("Segoe UI Semibold", 9),
            fg=COLORS["bg"],
            bg=COLORS["accent"],
            padx=7,
            pady=3,
        ).pack(side="left", padx=10)
        self.status = tk.Label(
            top,
            text="● Inicializando",
            font=("Segoe UI", 11),
            fg=COLORS["warn"],
            bg=COLORS["bg"],
        )
        self.status.pack(side="right")

        self.detail = tk.Label(
            self.root,
            text="Preparando os modelos locais…",
            anchor="w",
            font=("Segoe UI", 10),
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            padx=24,
        )
        self.detail.pack(fill="x", pady=(0, 12))

        body = tk.Frame(self.root, bg=COLORS["bg"], padx=24)
        body.pack(fill="both", expand=True)
        self.user_text = self._panel(body, "VOCÊ", 3)
        self.nero_text = self._panel(body, "NERO", 6)

        metrics = tk.Frame(
            self.root, bg=COLORS["panel_alt"], padx=20, pady=12
        )
        metrics.pack(fill="x", padx=24, pady=(12, 10))
        self.last_latency = self._metric(metrics, "ÚLTIMA", "—", 0)
        self.p50 = self._metric(metrics, "P50", "—", 1)
        self.p95 = self._metric(metrics, "P95", "—", 2)
        self.turns = self._metric(metrics, "TURNOS", "0", 3)

        controls = tk.Frame(self.root, bg=COLORS["bg"], padx=24, pady=12)
        controls.pack(fill="x")
        self.pause_button = self._button(
            controls, "Pausar", self._toggle_pause, COLORS["accent"]
        )
        self.pause_button.pack(side="left")
        voice_box = tk.Frame(controls, bg=COLORS["bg"])
        voice_box.pack(side="left", padx=(10, 0))
        tk.Label(
            voice_box,
            text="Voz",
            font=("Segoe UI", 9),
            fg=COLORS["muted"],
            bg=COLORS["bg"],
        ).pack(side="left", padx=(0, 6))
        self.voice_selector = ttk.Combobox(
            voice_box,
            state="disabled",
            width=20,
            font=("Segoe UI", 10),
        )
        self.voice_selector.pack(side="left")
        self.voice_selector.bind("<<ComboboxSelected>>", self._select_voice)
        self._button(
            controls, "Nova conversa", self.controller.new_conversation, COLORS["panel_alt"]
        ).pack(side="left", padx=10)
        self._button(
            controls, "Encerrar", self._close, COLORS["panel_alt"]
        ).pack(side="right")

    def _panel(self, parent: tk.Widget, title: str, height: int) -> tk.Text:
        frame = tk.Frame(parent, bg=COLORS["panel"], padx=16, pady=12)
        frame.pack(fill="both", expand=height > 3, pady=(0, 10))
        tk.Label(
            frame,
            text=title,
            font=("Segoe UI Semibold", 9),
            fg=COLORS["accent"],
            bg=COLORS["panel"],
        ).pack(anchor="w")
        text = tk.Text(
            frame,
            height=height,
            wrap="word",
            relief="flat",
            borderwidth=0,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 13),
            padx=0,
            pady=8,
        )
        text.pack(fill="both", expand=True)
        text.configure(state="disabled")
        return text

    def _metric(
        self, parent: tk.Widget, label: str, value: str, column: int
    ) -> tk.Label:
        cell = tk.Frame(parent, bg=COLORS["panel_alt"])
        cell.grid(row=0, column=column, sticky="ew", padx=12)
        parent.grid_columnconfigure(column, weight=1)
        tk.Label(
            cell,
            text=label,
            font=("Segoe UI Semibold", 8),
            fg=COLORS["muted"],
            bg=COLORS["panel_alt"],
        ).pack()
        result = tk.Label(
            cell,
            text=value,
            font=("Segoe UI Semibold", 13),
            fg=COLORS["text"],
            bg=COLORS["panel_alt"],
        )
        result.pack()
        return result

    def _button(
        self, parent: tk.Widget, text: str, command, background: str
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI Semibold", 10),
            bg=background,
            fg=COLORS["text"],
            activebackground=COLORS["good"],
            activeforeground=COLORS["bg"],
            relief="flat",
            borderwidth=0,
            padx=18,
            pady=9,
            cursor="hand2",
        )

    def _poll(self) -> None:
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        if not self._closing:
            self.root.after(30, self._poll)

    def _handle(self, event: UIEvent) -> None:
        if event.kind == "state":
            colors = {
                "Ouvindo": COLORS["good"],
                "Falando": COLORS["accent"],
                "Pensando": COLORS["warn"],
                "Interrompido": COLORS["warn"],
                "Erro": COLORS["error"],
            }
            self.status.configure(
                text=f"● {event.value}",
                fg=colors.get(str(event.value), COLORS["muted"]),
            )
        elif event.kind == "detail":
            self.detail.configure(text=str(event.value))
        elif event.kind in {"transcript", "transcript_partial"}:
            self._set_text(self.user_text, str(event.value))
        elif event.kind == "response_reset":
            self._set_text(self.nero_text, "")
        elif event.kind == "response_delta":
            self._append_text(self.nero_text, str(event.value))
        elif event.kind == "metrics":
            self._show_metrics(event.value)
        elif event.kind == "paused":
            self._paused = bool(event.value)
            self.pause_button.configure(text="Retomar" if self._paused else "Pausar")
        elif event.kind == "voices":
            self._show_voices(event.value)
        elif event.kind == "voice_changed":
            self._select_voice_id(str(event.value))
        elif event.kind == "clear":
            self._set_text(self.user_text, "")
            self._set_text(self.nero_text, "")
        elif event.kind == "error":
            self.detail.configure(text=str(event.value), fg=COLORS["error"])
            messagebox.showerror("Nero", str(event.value), parent=self.root)

    def _show_metrics(self, values: dict) -> None:
        latency = values.get("speech_to_audio_ms")
        self.last_latency.configure(text=_milliseconds(latency))
        self.p50.configure(text=_milliseconds(values.get("p50_ms")))
        p95 = values.get("p95_ms")
        self.p95.configure(
            text=_milliseconds(p95),
            fg=(
                COLORS["good"]
                if isinstance(p95, (int, float))
                and p95 <= self.settings.target_p95_ms
                else COLORS["warn"]
            ),
        )
        self.turns.configure(text=str(values.get("turns", 0)))

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    @staticmethod
    def _append_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.insert("end", value)
        widget.see("end")
        widget.configure(state="disabled")

    def _toggle_pause(self) -> None:
        self.controller.toggle_pause()

    def _show_voices(self, value: dict) -> None:
        voices = list(value.get("available", ()))
        labels = [_voice_label(voice) for voice in voices]
        self._voice_ids = dict(zip(labels, voices))
        self.voice_selector.configure(values=labels, state="readonly")
        self._select_voice_id(str(value.get("selected", "")))

    def _select_voice_id(self, voice: str) -> None:
        for label, voice_id in self._voice_ids.items():
            if voice_id == voice:
                self.voice_selector.set(label)
                return

    def _select_voice(self, _event=None) -> None:
        voice = self._voice_ids.get(self.voice_selector.get())
        if voice:
            self.controller.change_voice(voice)

    def _close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.status.configure(text="● Encerrando", fg=COLORS["muted"])
        self.root.update_idletasks()
        self.controller.stop()
        self.root.destroy()


def _milliseconds(value) -> str:
    return f"{float(value):.0f} ms" if isinstance(value, (int, float)) else "—"


def _voice_label(voice: str) -> str:
    labels = {
        "pf_dora": "Dora — feminina",
        "pm_alex": "Alex — masculina",
        "pm_santa": "Santa — masculina",
    }
    return labels.get(voice, voice)
