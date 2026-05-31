#!/usr/bin/env python3
"""
Conversor para Markdown v3 — Desktop
24 melhorias implementadas sobre a v1.

Lógica de conversão: converter_core.py  (Android-ready, sem GUI)
Interface gráfica:   este arquivo        (Desktop, customtkinter)
"""

import sys, os, re, uuid, json, threading, subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
import pystray
from PIL import Image, ImageDraw, ImageFont

from converter_core import convert_file, SUPPORTED_EXTENSIONS


def _open_path(path: str):
    """Abre arquivo ou pasta no gerenciador padrão do sistema (Windows, Mac e Linux)."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass

# ── Tema ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Config persistente ────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".conversor_md.json"

def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_config(cfg: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

# ── Constantes visuais ────────────────────────────────────────────────────────
EXT_ICON = {
    ".pdf": "📕", ".docx": "📘", ".html": "🌐", ".htm": "🌐",
    ".xlsx": "📗", ".xls": "📗", ".csv": "📊",
    ".txt": "📄", ".rst": "📄", ".log": "📄",
}
ROW_NORMAL   = "#111827"
ROW_HOVER    = "#1c2a3a"
ROW_SELECTED = "#1e3a5f"
ROW_ERROR    = "#2d1515"


# ── Ícone do app ──────────────────────────────────────────────────────────────
def _make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    r   = max(4, size // 6)
    d.rounded_rectangle([2, 2, size - 2, size - 2], radius=r, fill="#1565c0")
    try:
        fM = ImageFont.truetype("arial.ttf", max(8, int(size * 0.38)))
        fA = ImageFont.truetype("arial.ttf", max(6, int(size * 0.26)))
        d.text((size // 2, int(size * 0.36)), "M",  fill="white",   font=fM, anchor="mm")
        d.text((size // 2, int(size * 0.74)), "↓",  fill="#90caf9", font=fA, anchor="mm")
    except Exception:
        d.text((size // 5, size // 5), "M↓", fill="white")
    return img


# ── Modelo de dados ───────────────────────────────────────────────────────────
@dataclass
class FileItem:
    path: str
    uid: str       = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str    = "waiting"   # waiting | converting | done | error
    markdown: str  = ""
    output: str    = ""
    error_msg: str = ""

    @property
    def size_str(self) -> str:
        try:
            n = Path(self.path).stat().st_size
            if n < 1024:     return f"{n} B"
            if n < 1048576:  return f"{n // 1024} KB"
            return f"{n // 1048576} MB"
        except Exception:
            return ""


# ── Widget de linha de arquivo ────────────────────────────────────────────────
class FileRow(ctk.CTkFrame):
    def __init__(self, parent, item: FileItem,
                 on_select: Callable, on_remove: Callable, on_retry: Callable):
        super().__init__(parent, corner_radius=7, fg_color=ROW_NORMAL, cursor="hand2")
        self.item      = item
        self._on_select = on_select
        self._selected  = False
        self._build(on_remove, on_retry)
        self.bind("<Enter>",    self._hover_on)
        self.bind("<Leave>",    self._hover_off)
        self.bind("<Button-1>", lambda e: on_select(item))

    def _build(self, on_remove, on_retry):
        icon = EXT_ICON.get(Path(self.item.path).suffix.lower(), "📄")
        name = Path(self.item.path).name

        # ── Linha principal ──
        main = ctk.CTkFrame(self, fg_color="transparent", height=44)
        main.pack(fill="x")
        main.pack_propagate(False)
        main.bind("<Button-1>", lambda e: self._on_select(self.item))

        il = ctk.CTkLabel(main, text=icon, width=28, font=ctk.CTkFont(size=15))
        il.pack(side="left", padx=(8, 2))
        il.bind("<Button-1>", lambda e: self._on_select(self.item))

        nl = ctk.CTkLabel(main, text=name, font=ctk.CTkFont(size=12), anchor="w")
        nl.pack(side="left", fill="x", expand=True)
        nl.bind("<Button-1>", lambda e: self._on_select(self.item))

        ctk.CTkLabel(main, text=self.item.size_str, font=ctk.CTkFont(size=10),
                     text_color="gray", width=50).pack(side="left", padx=2)

        # Botão remover (sempre visível)
        ctk.CTkButton(main, text="×", width=24, height=24,
                      font=ctk.CTkFont(size=14),
                      fg_color="#7f0000", hover_color="#500000",
                      command=lambda: on_remove(self.item)).pack(side="right", padx=(2, 6))

        # Botão retry — sempre presente, invisível até erro
        self._retry_btn = ctk.CTkButton(
            main, text="", width=24, height=24,
            font=ctk.CTkFont(size=13),
            fg_color=ROW_NORMAL, hover_color=ROW_NORMAL, text_color=ROW_NORMAL,
            command=lambda: on_retry(self.item))
        self._retry_btn.pack(side="right", padx=(0, 2))

        # Ícone de status
        self._status_lbl = ctk.CTkLabel(main, text="⏸", width=26,
                                         font=ctk.CTkFont(size=14), text_color="#777")
        self._status_lbl.pack(side="right", padx=2)
        self._status_lbl.bind("<Button-1>", lambda e: self._on_select(self.item))

        # ── Barra de progresso (oculta inicialmente) ──
        self._prog_frame = ctk.CTkFrame(self, fg_color="transparent", height=16)
        self._bar = ctk.CTkProgressBar(self._prog_frame, height=5, mode="indeterminate",
                                        progress_color="#42a5f5")
        self._bar.pack(fill="x", padx=10, pady=(0, 4))

    # ── Estados visuais ───────────────────────────────────────────────────────
    def set_converting(self):
        self._status_lbl.configure(text="⏳", text_color="#ffa726")
        self._hide_retry()
        self._prog_frame.pack(fill="x")
        self._bar.start()

    def set_done(self):
        self._bar.stop()
        self._prog_frame.pack_forget()
        self._hide_retry()
        self._status_lbl.configure(text="✅", text_color="#66bb6a")
        self._refresh_color()

    def set_error(self):
        self._bar.stop()
        self._prog_frame.pack_forget()
        self._status_lbl.configure(text="❌", text_color="#ef5350")
        self._retry_btn.configure(text="↺", fg_color="#e65100", hover_color="#bf360c",
                                   text_color="white")
        self.configure(fg_color=ROW_ERROR)

    def set_waiting(self):
        self._bar.stop()
        self._prog_frame.pack_forget()
        self._hide_retry()
        self._status_lbl.configure(text="⏸", text_color="#777")
        self._refresh_color()

    def _hide_retry(self):
        self._retry_btn.configure(text="", fg_color=ROW_NORMAL,
                                   hover_color=ROW_NORMAL, text_color=ROW_NORMAL)

    # ── Seleção e hover ───────────────────────────────────────────────────────
    def select(self, selected: bool):
        self._selected = selected
        self._refresh_color()

    def _hover_on(self, _=None):
        if not self._selected and self.item.status != "error":
            self.configure(fg_color=ROW_HOVER)

    def _hover_off(self, _=None):
        self._refresh_color()

    def _refresh_color(self):
        if self.item.status == "error":
            self.configure(fg_color=ROW_ERROR)
        elif self._selected:
            self.configure(fg_color=ROW_SELECTED)
        else:
            self.configure(fg_color=ROW_NORMAL)


# ── App principal ─────────────────────────────────────────────────────────────
class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self._cfg        = load_config()
        self._items:     list[FileItem]       = []
        self._rows:      dict[str, FileRow]   = {}
        self._sel:       Optional[FileItem]   = None
        self._tray:      Optional[pystray.Icon] = None
        self._cancel     = threading.Event()
        self._converting = False

        self.title("Conversor para Markdown")
        self.geometry("1040x680")
        self.minsize(780, 540)

        # Ícone da janela e barra de tarefas
        try:
            from PIL import ImageTk
            _ico = ImageTk.PhotoImage(_make_icon(32))
            self.iconphoto(True, _ico)
            self._ico_ref = _ico
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._hide)
        self._build()
        self._start_tray()
        self._bind_keys()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        # Cabeçalho
        hdr = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color="#0d47a1")
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="  Conversor para Markdown",
                     font=ctk.CTkFont(size=19, weight="bold"), text_color="white").pack(side="left", padx=16)
        ctk.CTkLabel(hdr, text="HTML · DOCX · PDF · CSV · XLSX · TXT",
                     font=ctk.CTkFont(size=12), text_color="#90caf9").pack(side="left")

        # Barra de configurações
        cfg_bar = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color="#0a1929")
        cfg_bar.pack(fill="x")
        cfg_bar.pack_propagate(False)
        ctk.CTkLabel(cfg_bar, text="  📁 Pasta de saída:",
                     font=ctk.CTkFont(size=12), text_color="#90caf9").pack(side="left", padx=(8, 2))
        self._out_var = ctk.StringVar(value=self._cfg.get("output_folder", ""))
        ctk.CTkEntry(cfg_bar, textvariable=self._out_var,
                     placeholder_text="Mesmo diretório do arquivo original",
                     width=320, height=26, font=ctk.CTkFont(size=12)).pack(side="left", padx=4)
        ctk.CTkButton(cfg_bar, text="...", width=30, height=26,
                      command=self._pick_out_folder).pack(side="left", padx=(2, 14))
        self._auto_var = ctk.BooleanVar(value=self._cfg.get("auto_convert", False))
        ctk.CTkCheckBox(cfg_bar, text="Converter ao soltar", variable=self._auto_var,
                         font=ctk.CTkFont(size=12), command=self._save_cfg).pack(side="left", padx=6)

        # Corpo principal
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=8)

        # ── Painel esquerdo ───────────────────────────────────────────────────
        left = ctk.CTkFrame(body, width=340, corner_radius=12)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="Arquivos",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(12, 6))

        # Zona de drop (animada)
        self._dz = ctk.CTkFrame(left, height=112, corner_radius=12,
                                  border_width=2, border_color="#1e56b0",
                                  fg_color="#0a1e4a", cursor="hand2")
        self._dz.pack(fill="x", padx=12, pady=(0, 8))
        self._dz.pack_propagate(False)
        self._dz_top = ctk.CTkLabel(self._dz, text="⬇   Arraste arquivos aqui",
                                     font=ctk.CTkFont(size=13), text_color="#90caf9")
        self._dz_top.place(relx=.5, rely=.38, anchor="center")
        ctk.CTkLabel(self._dz, text="ou clique em  + Adicionar",
                     font=ctk.CTkFont(size=11), text_color="#4a6fa5").place(relx=.5, rely=.72, anchor="center")

        for w in (self._dz, self._dz_top):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>",       self._on_drop)
            w.dnd_bind("<<DragEnter>>",  self._dz_enter)
            w.dnd_bind("<<DragLeave>>",  self._dz_leave)

        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)

        # Lista de arquivos
        self._list = ctk.CTkScrollableFrame(left, corner_radius=8, fg_color="#0d1117")
        self._list.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self._empty_lbl = ctk.CTkLabel(
            self._list,
            text="Nenhum arquivo\n\nArraste aqui ou clique em\n+ Adicionar",
            font=ctk.CTkFont(size=12), text_color="gray", justify="center")
        self._empty_lbl.pack(pady=28)

        # Botões Adicionar / Limpar
        br = ctk.CTkFrame(left, fg_color="transparent")
        br.pack(fill="x", padx=12, pady=(2, 4))
        ctk.CTkButton(br, text="+ Adicionar", width=114, height=34,
                      font=ctk.CTkFont(size=13), command=self._browse).pack(side="left", padx=(0, 6))
        ctk.CTkButton(br, text="🗑 Limpar", width=96, height=34,
                      font=ctk.CTkFont(size=13), fg_color="#7f0000", hover_color="#500000",
                      command=self._clear).pack(side="left")

        # Converter + Parar
        cb = ctk.CTkFrame(left, fg_color="transparent")
        cb.pack(fill="x", padx=12, pady=(4, 12))
        self._conv_btn = ctk.CTkButton(
            cb, text="▶  Converter Todos", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#1565c0", hover_color="#0d47a1",
            state="disabled", command=self._convert_all)
        self._conv_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._stop_btn = ctk.CTkButton(
            cb, text="⏹", width=44, height=44,
            font=ctk.CTkFont(size=18),
            fg_color="#7f0000", hover_color="#500000",
            state="disabled", command=self._cancel_conversion)
        self._stop_btn.pack(side="left")

        # ── Painel direito (preview) ──────────────────────────────────────────
        right = ctk.CTkFrame(body, corner_radius=12)
        right.pack(side="left", fill="both", expand=True)

        ph = ctk.CTkFrame(right, height=42, fg_color="transparent")
        ph.pack(fill="x", padx=14, pady=(10, 4))
        ph.pack_propagate(False)
        ctk.CTkLabel(ph, text="Preview Markdown",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(ph, text="📋 Copiar", width=90, height=30,
                      font=ctk.CTkFont(size=12), command=self._copy).pack(side="right")
        self._open_file_btn = ctk.CTkButton(
            ph, text="📄 Abrir", width=82, height=30,
            font=ctk.CTkFont(size=12), fg_color="transparent", border_width=1,
            state="disabled", command=self._open_file)
        self._open_file_btn.pack(side="right", padx=4)
        self._open_folder_btn = ctk.CTkButton(
            ph, text="📂 Pasta", width=82, height=30,
            font=ctk.CTkFont(size=12), fg_color="transparent", border_width=1,
            state="disabled", command=self._open_folder)
        self._open_folder_btn.pack(side="right", padx=4)

        self._preview = ctk.CTkTextbox(right, font=ctk.CTkFont(family="Consolas", size=12),
                                        wrap="word", state="disabled", fg_color="#0d1117")
        self._preview.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # Barra de status
        self._sb = ctk.CTkLabel(
            self, anchor="w", font=ctk.CTkFont(size=11), text_color="gray",
            text="Ctrl+O: Adicionar  •  Del: Remover  •  Ctrl+Enter: Converter")
        self._sb.pack(fill="x", padx=14, pady=(0, 6))

    # ── Drag & Drop (animado) ─────────────────────────────────────────────────
    def _dz_enter(self, _=None):
        self._dz.configure(fg_color="#0d2d6e", border_color="#42a5f5")
        self._dz_top.configure(text="📂   Solte aqui!", text_color="#42a5f5")

    def _dz_leave(self, _=None):
        self._dz.configure(fg_color="#0a1e4a", border_color="#1e56b0")
        self._dz_top.configure(text="⬇   Arraste arquivos aqui", text_color="#90caf9")

    def _on_drop(self, event):
        self._dz_leave()
        added = False
        for p in self._parse_paths(event.data):
            path = Path(p)
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                if not any(it.path == str(path) for it in self._items):
                    item = FileItem(path=str(path))
                    self._items.append(item)
                    self._add_row(item)
                    added = True
        if added:
            self._refresh()
            if self._auto_var.get():
                self._convert_all()

    @staticmethod
    def _parse_paths(data: str) -> list[str]:
        return [a or b for a, b in re.findall(r'\{([^}]+)\}|(\S+)', data)]

    # ── Gerenciamento de arquivos ─────────────────────────────────────────────
    def _browse(self):
        last = self._cfg.get("last_folder", "")
        paths = filedialog.askopenfilenames(
            title="Selecionar arquivos",
            initialdir=last or None,
            filetypes=[("Suportados", "*.html *.htm *.docx *.pdf *.csv *.xlsx *.xls *.txt *.rst *.log"),
                       ("Todos", "*.*")])
        if not paths:
            return
        self._cfg["last_folder"] = str(Path(paths[0]).parent)
        save_config(self._cfg)
        for p in paths:
            if not any(it.path == p for it in self._items):
                item = FileItem(path=p)
                self._items.append(item)
                self._add_row(item)
        self._refresh()

    def _add_row(self, item: FileItem):
        row = FileRow(self._list, item,
                      on_select=self._select,
                      on_remove=self._remove,
                      on_retry=self._retry)
        row.pack(fill="x", pady=2)
        self._rows[item.uid] = row
        self._empty_lbl.pack_forget()

    def _select(self, item: FileItem):
        if self._sel and self._sel.uid in self._rows:
            self._rows[self._sel.uid].select(False)
        self._sel = item
        if item.uid in self._rows:
            self._rows[item.uid].select(True)

        if item.status == "done" and item.markdown:
            self._set_preview(item.markdown)
            self._open_file_btn.configure(state="normal")
            self._open_folder_btn.configure(state="normal")
        elif item.status == "error":
            self._set_preview(f"❌  Erro ao converter:\n{Path(item.path).name}\n\n{item.error_msg}")
            self._open_file_btn.configure(state="disabled")
            self._open_folder_btn.configure(state="disabled")
        else:
            self._set_preview(f"Aguardando conversão:\n{Path(item.path).name}")
            self._open_file_btn.configure(state="disabled")
            self._open_folder_btn.configure(state="disabled")

    def _remove(self, item: FileItem):
        if self._converting and item.status == "converting":
            return
        if item.uid in self._rows:
            self._rows[item.uid].destroy()
            del self._rows[item.uid]
        if item in self._items:
            self._items.remove(item)
        if self._sel is item:
            self._sel = None
            self._set_preview("")
            self._open_file_btn.configure(state="disabled")
            self._open_folder_btn.configure(state="disabled")
        if not self._items:
            self._empty_lbl.pack(pady=28)
        self._refresh()

    def _retry(self, item: FileItem):
        item.status    = "waiting"
        item.markdown  = ""
        item.output    = ""
        item.error_msg = ""
        if item.uid in self._rows:
            self._rows[item.uid].set_waiting()
        self._refresh()

    def _clear(self):
        if self._converting:
            messagebox.showwarning("Atenção", "Aguarde a conversão terminar antes de limpar.")
            return
        if self._items and not messagebox.askyesno(
                "Limpar lista", f"Remover {len(self._items)} arquivo(s) da lista?"):
            return
        for row in self._rows.values():
            row.destroy()
        self._rows.clear()
        self._items.clear()
        self._sel = None
        self._set_preview("")
        self._open_file_btn.configure(state="disabled")
        self._open_folder_btn.configure(state="disabled")
        self._empty_lbl.pack(pady=28)
        self._refresh()

    def _pick_out_folder(self):
        folder = filedialog.askdirectory(title="Pasta de destino dos arquivos convertidos")
        if folder:
            self._out_var.set(folder)
            self._cfg["output_folder"] = folder
            save_config(self._cfg)

    def _save_cfg(self):
        self._cfg["auto_convert"] = self._auto_var.get()
        save_config(self._cfg)

    def _refresh(self):
        waiting = sum(1 for it in self._items if it.status == "waiting")
        self._conv_btn.configure(
            state="normal" if waiting and not self._converting else "disabled",
            text=f"▶  Converter {waiting}" if waiting else "▶  Converter Todos")
        total = len(self._items)
        if not total:
            self._sb.configure(
                text="Ctrl+O: Adicionar  •  Del: Remover  •  Ctrl+Enter: Converter")
        else:
            done = sum(1 for it in self._items if it.status == "done")
            err  = sum(1 for it in self._items if it.status == "error")
            txt  = f"{total} arquivo(s)  •  ✅ {done} convertido(s)"
            if err:
                txt += f"  •  ❌ {err} erro(s) — clique na linha para ver detalhes"
            self._sb.configure(text=txt)

    # ── Conversão ─────────────────────────────────────────────────────────────
    def _convert_all(self):
        pending = [it for it in self._items if it.status == "waiting"]
        if not pending or self._converting:
            return
        self._converting = True
        self._cancel.clear()
        self._conv_btn.configure(state="disabled", text="Convertendo…")
        self._stop_btn.configure(state="normal")
        threading.Thread(target=self._run, args=(pending,), daemon=True).start()

    def _cancel_conversion(self):
        self._cancel.set()
        self._stop_btn.configure(state="disabled")

    def _make_output_path(self, item_path: str) -> Optional[str]:
        out_folder = self._out_var.get().strip()
        if not out_folder:
            return None   # salva junto ao original
        stem = Path(item_path).stem
        out  = Path(out_folder) / (stem + ".md")
        n = 1
        while out.exists():
            out = Path(out_folder) / f"{stem}_{n}.md"
            n += 1
        return str(out)

    def _update_row(self, uid: str, method: str):
        if uid in self._rows:
            getattr(self._rows[uid], method)()

    def _run(self, items: list[FileItem]):
        for item in items:
            if self._cancel.is_set():
                break
            item.status = "converting"
            self.after(0, self._update_row, item.uid, "set_converting")
            try:
                out_path      = self._make_output_path(item.path)
                md, out       = convert_file(item.path, out_path)
                item.markdown = md
                item.output   = out
                item.status   = "done"
                self.after(0, self._update_row, item.uid, "set_done")
                self.after(0, self._select, item)
            except Exception as exc:
                item.error_msg = str(exc)
                item.status    = "error"
                self.after(0, self._update_row, item.uid, "set_error")
        self.after(0, self._run_done)

    def _run_done(self):
        self._converting = False
        self._cancel.clear()
        self._stop_btn.configure(state="disabled")
        done = sum(1 for it in self._items if it.status == "done")
        err  = sum(1 for it in self._items if it.status == "error")
        self._refresh()
        if self._tray:
            try:
                msg = f"{done} arquivo(s) convertido(s)"
                if err:
                    msg += f" • {err} com erro"
                self._tray.notify("Conversão concluída", msg)
            except Exception:
                pass

    # ── Preview ───────────────────────────────────────────────────────────────
    def _set_preview(self, text: str):
        self._preview.configure(state="normal")
        self._preview.delete("1.0", "end")
        if text:
            self._preview.insert("1.0", text)
        self._preview.configure(state="disabled")

    def _copy(self):
        txt = self._preview.get("1.0", "end-1c")
        if txt:
            self.clipboard_clear()
            self.clipboard_append(txt)

    def _open_file(self):
        if not (self._sel and self._sel.output):
            return
        if Path(self._sel.output).exists():
            _open_path(self._sel.output)
        else:
            messagebox.showwarning(
                "Arquivo não encontrado",
                f"O arquivo foi movido ou deletado:\n{self._sel.output}")

    def _open_folder(self):
        if not (self._sel and self._sel.output):
            return
        folder = Path(self._sel.output).parent
        if folder.exists():
            _open_path(str(folder))
        else:
            messagebox.showwarning(
                "Pasta não encontrada",
                f"A pasta não existe mais:\n{folder}")

    # ── Atalhos de teclado ────────────────────────────────────────────────────
    def _bind_keys(self):
        self.bind("<Control-o>",      lambda e: self._browse())
        self.bind("<Control-Return>", lambda e: self._convert_all())
        self.bind("<Delete>",         lambda e: self._sel and self._remove(self._sel))

    # ── Bandeja do sistema ────────────────────────────────────────────────────
    def _start_tray(self):
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Abrir Conversor", self._show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", self._quit),
            )
            self._tray = pystray.Icon("conversor_md", _make_icon(64),
                                       "Conversor para Markdown", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception:
            # Bandeja não disponível (Linux sem AppIndicator3, Wayland, etc.)
            # Nesse caso X fecha o app normalmente em vez de minimizar para bandeja
            self._tray = None
            self.protocol("WM_DELETE_WINDOW", self._quit)

    def _hide(self):
        self.withdraw()

    def _show(self, *_):
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(0, self.focus_force)

    def _quit(self, *_):
        if self._tray:
            self._tray.stop()
        self.after(0, self.destroy)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()
