"""Storage Analyzer - scan a drive, drill into folders by size, get AI clean-up and organising advice."""

import os
import queue
import shutil
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cleanup
import core
import organiser
from core import Scanner, fmt_size
from llm import LLMError, Ollama

MAX_ROWS = 2000          # rows shown per folder before collapsing the rest
RISK_COLORS = {cleanup.SAFE: "#1e7d32", cleanup.REVIEW: "#b26a00", cleanup.CAUTION: "#c43e00",
               cleanup.KEEP: "#9e1b1b"}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Storage Analyzer")
        self.geometry("1400x820")
        self.minsize(1000, 560)

        self.q = queue.Queue()
        self.scanner = None
        self.root_node = None
        self.current = None
        self.scan_started = 0.0
        self.row_items = {}     # browse iid -> ("dir", Node) | ("file", path)
        self.clean_items = {}   # clean-up iid -> item dict or Category
        self.categories = []
        self.ai_category = None
        self.profile = None
        self.llm = Ollama()
        self.ai_busy = False

        self._build_ui()
        self._refresh_drives()
        self._load_models()
        self.after(100, self._poll)

    # ================================================================ UI
    def _build_ui(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=24)
        style.configure("Mode.Toolbutton", padding=(14, 6), font=("Segoe UI", 10, "bold"))

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Drive:").pack(side="left")
        self.drive_var = tk.StringVar()
        self.drive_combo = ttk.Combobox(top, textvariable=self.drive_var, width=34, state="readonly")
        self.drive_combo.pack(side="left", padx=(4, 6))
        self.scan_btn = ttk.Button(top, text="Scan", command=self.scan_drive)
        self.scan_btn.pack(side="left")
        ttk.Button(top, text="Scan folder...", command=self.scan_folder).pack(side="left", padx=6)
        self.cancel_btn = ttk.Button(top, text="Cancel", command=self.cancel_scan, state="disabled")
        self.cancel_btn.pack(side="left")
        ttk.Button(top, text="↻", width=3, command=self._refresh_drives).pack(side="left", padx=6)

        self.ai_status = tk.StringVar(value="Connecting to Ollama...")
        ttk.Label(top, textvariable=self.ai_status, foreground="#555").pack(side="right")
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(top, textvariable=self.model_var, width=22, state="readonly")
        self.model_combo.pack(side="right", padx=6)
        self.model_combo.bind("<<ComboboxSelected>>", lambda e: setattr(self.llm, "model", self.model_var.get()))
        ttk.Label(top, text="AI model:").pack(side="right")

        modes = ttk.Frame(self, padding=(8, 0, 8, 6))
        modes.pack(fill="x")
        self.mode_var = tk.StringVar(value="cleanup")
        ttk.Radiobutton(modes, text="\U0001F9F9  Clean-up mode", value="cleanup", variable=self.mode_var,
                        style="Mode.Toolbutton", command=self._switch_mode).pack(side="left")
        ttk.Radiobutton(modes, text="\U0001F5C2  Organiser mode", value="organise", variable=self.mode_var,
                        style="Mode.Toolbutton", command=self._switch_mode).pack(side="left", padx=4)

        nav = ttk.Frame(self, padding=(8, 0, 8, 6))
        nav.pack(fill="x")
        self.up_btn = ttk.Button(nav, text="↑ Up", command=self.go_up, state="disabled")
        self.up_btn.pack(side="left")
        self.explorer_btn = ttk.Button(nav, text="Open in Explorer", command=self.open_selected_in_explorer,
                                       state="disabled")
        self.explorer_btn.pack(side="left", padx=6)
        self.path_var = tk.StringVar(value="Select a drive and click Scan.")
        ttk.Label(nav, textvariable=self.path_var, font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8)

        self.tabs = ttk.Notebook(panes)
        panes.add(self.tabs, weight=5)
        self._build_browse_tab()
        self._build_big_tab()

        self.mode_host = ttk.Frame(panes)
        panes.add(self.mode_host, weight=6)
        self._build_cleanup_panel()
        self._build_organiser_panel()
        self._switch_mode()

        self.menu = tk.Menu(self, tearoff=0)

        status = ttk.Frame(self, padding=(8, 4))
        status.pack(fill="x")
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=160)
        self.progress.pack(side="right")
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status, textvariable=self.status_var).pack(side="left", fill="x", expand=True)

    def _scrolled(self, parent, widget):
        sb = ttk.Scrollbar(parent, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=sb.set)
        widget.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return widget

    def _build_browse_tab(self):
        browse = ttk.Frame(self.tabs)
        self.tabs.add(browse, text="Browse")
        self.tree = ttk.Treeview(browse, columns=("size", "pct", "files", "cloud"), selectmode="browse")
        for col, text, width, anchor in (("#0", "Name", 260, "w"), ("size", "On disk", 80, "e"),
                                         ("pct", "% of folder", 160, "w"), ("files", "Files", 65, "e"),
                                         ("cloud", "Online-only", 85, "e")):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.tag_configure("dir", foreground="#1a4fa0")
        self.tree.tag_configure("denied", foreground="#a33")
        self.tree.tag_configure("more", foreground="#777")
        self._scrolled(browse, self.tree)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_double_click)
        self.tree.bind("<BackSpace>", lambda e: self.go_up())
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons())

    def _build_big_tab(self):
        big = ttk.Frame(self.tabs)
        self.tabs.add(big, text="Largest files")
        self.big_tree = ttk.Treeview(big, columns=("size", "path"), show="headings", selectmode="browse")
        self.big_tree.heading("size", text="Size")
        self.big_tree.heading("path", text="Path")
        self.big_tree.column("size", width=80, anchor="e", stretch=False)
        self.big_tree.column("path", width=520)
        self._scrolled(big, self.big_tree)
        self.big_tree.bind("<Double-1>", lambda e: self._big_open())
        self.big_tree.bind("<Button-3>", self._on_big_right_click)

    def _text_box(self, parent, height):
        frame = ttk.Frame(parent)
        text = tk.Text(frame, wrap="word", height=height, font=("Segoe UI", 10), relief="flat",
                       padx=8, pady=6, background="#fbfbfb")
        text.tag_configure("h", font=("Segoe UI", 11, "bold"), spacing1=6, spacing3=2)
        text.tag_configure("muted", foreground="#666")
        text.tag_configure("warn", foreground="#9e1b1b")
        self._scrolled(frame, text)
        text.configure(state="disabled")
        return frame, text

    def _build_cleanup_panel(self):
        p = self.cleanup_panel = ttk.Frame(self.mode_host)
        bar = ttk.Frame(p)
        bar.pack(fill="x", pady=(0, 4))
        self.find_btn = ttk.Button(bar, text="1. Find clean-up candidates", command=self.find_candidates)
        self.find_btn.pack(side="left")
        self.review_btn = ttk.Button(bar, text="2. AI: review unrecognised big folders", command=self.ai_review)
        self.review_btn.pack(side="left", padx=6)
        self.explain_btn = ttk.Button(bar, text="Ask AI about selected", command=self.ai_explain_selected)
        self.explain_btn.pack(side="left")
        self.savings_var = tk.StringVar(value="Scan a drive, then click 'Find clean-up candidates'.")
        ttk.Label(p, textvariable=self.savings_var, font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(0, 4))

        split = ttk.PanedWindow(p, orient="vertical")
        split.pack(fill="both", expand=True)
        tframe = ttk.Frame(split)
        self.clean_tree = ttk.Treeview(tframe, columns=("size", "risk", "note"), selectmode="browse")
        for col, text, width, anchor in (("#0", "Category / item", 330, "w"), ("size", "Size", 80, "e"),
                                         ("risk", "Risk", 70, "w"), ("note", "Details", 260, "w")):
            self.clean_tree.heading(col, text=text)
            self.clean_tree.column(col, width=width, anchor=anchor)
        for risk, color in RISK_COLORS.items():
            self.clean_tree.tag_configure(risk, foreground=color)
        self.clean_tree.tag_configure("cat", font=("Segoe UI", 10, "bold"))
        self._scrolled(tframe, self.clean_tree)
        self.clean_tree.bind("<<TreeviewSelect>>", lambda e: self._show_clean_details())
        self.clean_tree.bind("<Double-1>", lambda e: self._clean_reveal())
        self.clean_tree.bind("<Button-3>", self._on_clean_right_click)
        split.add(tframe, weight=3)
        dframe, self.clean_text = self._text_box(split, 9)
        split.add(dframe, weight=2)
        self._set_text(self.clean_text, [
            ("How clean-up mode works", "h"),
            ("1. Rules find well-known space wasters (temp files, caches, update leftovers, old installers, "
             "duplicates, large old files) and rate how safe each is to remove.\n", None),
            ("2. Your local Llama model reviews big folders the rules don't recognise and explains what they "
             "are, whether they can go, and the impact.\n", None),
            ("Select any item to see its impact; right-click to open it in Explorer or ask the AI about it. "
             "Nothing is ever deleted by this app.", "muted"),
        ])

    def _build_organiser_panel(self):
        p = self.organise_panel = ttk.Frame(self.mode_host)
        bar = ttk.Frame(p)
        bar.pack(fill="x", pady=(0, 4))
        self.analyse_btn = ttk.Button(bar, text="Analyse current folder", command=self.analyse_folder)
        self.analyse_btn.pack(side="left")
        self.plan_btn = ttk.Button(bar, text="AI: suggest organisation plan", command=self.ai_plan)
        self.plan_btn.pack(side="left", padx=6)
        self.org_folder_var = tk.StringVar(value="Browse to a folder on the left, then analyse it.")
        ttk.Label(p, textvariable=self.org_folder_var, font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(0, 4))

        split = ttk.PanedWindow(p, orient="vertical")
        split.pack(fill="both", expand=True)
        dframe, self.org_text = self._text_box(split, 12)
        split.add(dframe, weight=3)
        tframe = ttk.Frame(split)
        self.org_tree = ttk.Treeview(tframe, columns=("detail",), selectmode="browse")
        self.org_tree.heading("#0", text="Suggested structure / moves")
        self.org_tree.heading("detail", text="Details")
        self.org_tree.column("#0", width=300)
        self.org_tree.column("detail", width=420)
        self.org_tree.tag_configure("folder", foreground="#1a4fa0", font=("Segoe UI", 10, "bold"))
        self._scrolled(tframe, self.org_tree)
        split.add(tframe, weight=3)
        self._set_text(self.org_text, [
            ("How organiser mode works", "h"),
            ("Open any folder in the Browse list (for example Documents or Downloads), then click "
             "'Analyse current folder' for a quick health check: loose files, mixed types, duplicates, copies, "
             "empty and deeply nested folders.\n", None),
            ("'AI: suggest organisation plan' asks your local Llama model for a folder structure tailored to "
             "what is actually in that folder, and which files should move where. Nothing is moved automatically.",
             "muted"),
        ])

    def _switch_mode(self):
        self.cleanup_panel.pack_forget()
        self.organise_panel.pack_forget()
        panel = self.cleanup_panel if self.mode_var.get() == "cleanup" else self.organise_panel
        panel.pack(fill="both", expand=True, padx=(6, 0))
        self._update_org_label()

    def _set_text(self, widget, parts, append=False):
        widget.configure(state="normal")
        if not append:
            widget.delete("1.0", "end")
        for text, tag in parts:
            if tag == "h":
                text = text + "\n"
            widget.insert("end", text, tag or ())
        widget.configure(state="disabled")
        if not append:
            widget.see("1.0")

    # ================================================================ background work
    def run_bg(self, work, done, busy_text):
        """Run `work()` in a thread for AI calls; `done(result, error)` runs on the UI thread."""
        if self.ai_busy:
            messagebox.showinfo("Busy", "The AI is still working on the previous request.")
            return
        self._set_ai_busy(True, busy_text)

        def target():
            try:
                self.q.put(("ui", done, work(), None))
            except Exception as e:  # report any failure in the UI
                self.q.put(("ui", done, None, e))
        threading.Thread(target=target, daemon=True).start()

    def _set_ai_busy(self, busy, text=""):
        self.ai_busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.review_btn, self.explain_btn, self.plan_btn, self.analyse_btn, self.find_btn):
            b.config(state=state)
        if busy:
            self.progress.start(12)
            self.status_var.set(text)
        else:
            self.progress.stop()

    def _status_from_thread(self, text):
        self.q.put(("status", text))

    def _load_models(self):
        def work():
            return self.llm.models()

        def done(names, err):
            if err:
                self.ai_status.set("Ollama not reachable - AI features off")
                return
            self.model_combo["values"] = names
            if self.llm.model:
                self.model_var.set(self.llm.model)
            self.ai_status.set(f"Ollama connected ({len(names)} models)")
        threading.Thread(target=lambda: self._bg_simple(work, done), daemon=True).start()

    def _bg_simple(self, work, done):
        try:
            self.q.put(("ui", done, work(), None))
        except Exception as e:
            self.q.put(("ui", done, None, e))

    def _ai_error(self, err):
        msg = str(err) if isinstance(err, LLMError) else f"{type(err).__name__}: {err}"
        self.status_var.set("AI request failed")
        messagebox.showerror("AI error", msg)

    # ================================================================ scanning
    def _refresh_drives(self):
        labels = []
        for d in os.listdrives():
            try:
                u = shutil.disk_usage(d)
                labels.append(f"{d}   {fmt_size(u.used)} used of {fmt_size(u.total)}  ({fmt_size(u.free)} free)")
            except OSError:
                labels.append(f"{d}   (not ready)")
        self.drive_combo["values"] = labels
        if labels and not self.drive_var.get():
            self.drive_combo.current(0)

    def scan_drive(self):
        value = self.drive_var.get()
        if value:
            self._start_scan(value.split()[0])

    def scan_folder(self):
        path = filedialog.askdirectory(title="Choose a folder to scan")
        if path:
            self._start_scan(os.path.normpath(path))

    def _start_scan(self, path):
        if self.scanner and self.scanner.is_alive():
            return
        self.root_node = self.current = None
        self.categories, self.ai_category, self.profile = [], None, None
        for t in (self.tree, self.big_tree, self.clean_tree, self.org_tree):
            t.delete(*t.get_children())
        self.savings_var.set("Scanning...")
        self.path_var.set(f"Scanning {path} ...")
        self.scan_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self._update_buttons()
        self.progress.start(12)
        self.scan_started = time.monotonic()
        self.scanner = Scanner(path, self.q)
        self.scanner.start()

    def cancel_scan(self):
        if self.scanner:
            self.scanner.cancelled = True

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, files, dirs, path = msg
                    self.status_var.set(f"{files:,} files, {dirs:,} folders  -  {path}")
                elif kind == "done":
                    _, root, top, files, dirs = msg
                    self._scan_finished()
                    self.root_node = root
                    secs = time.monotonic() - self.scan_started
                    self.status_var.set(f"Scanned {files:,} files in {dirs:,} folders in {secs:.1f}s - "
                                        f"{fmt_size(root.size)} on disk, {fmt_size(root.cloud)} online-only "
                                        f"cloud files (not using disk space)")
                    self.savings_var.set("Scan complete. Click 'Find clean-up candidates'.")
                    self._fill_big(top)
                    self.show(root)
                elif kind == "cancelled":
                    self._scan_finished()
                    self.path_var.set("Scan cancelled.")
                    self.status_var.set("Ready")
                elif kind == "status":
                    self.status_var.set(msg[1])
                elif kind == "ui":
                    _, callback, result, err = msg
                    callback(result, err)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _scan_finished(self):
        self.progress.stop()
        self.scan_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")

    # ================================================================ browsing
    def show(self, node):
        self.current = node
        self.tree.delete(*self.tree.get_children())
        self.row_items.clear()
        cloud = f"  (+{fmt_size(node.cloud)} online-only)" if node.cloud else ""
        self.path_var.set(f"{node.path}   -   {fmt_size(node.size)} on disk{cloud}")

        # (kind, name, bytes on disk, online-only bytes, node)
        entries = [("dir", d.name, d.size, d.cloud, d) for d in node.dirs]
        entries += [("file", f[0], 0, f[1], None) if f[3] else ("file", f[0], f[1], 0, None) for f in node.files]
        entries.sort(key=lambda e: (e[2], e[3]), reverse=True)

        total = node.size or 1
        for kind, name, size, online, child in entries[:MAX_ROWS]:
            pct = size * 100 / total
            bar_text = f"{chr(0x2588) * round(pct / 5):<20} {pct:5.1f}%"
            online_text = fmt_size(online) if online else ""
            if kind == "dir":
                tags = ("dir", "denied") if child.denied else ("dir",)
                label = f"\U0001F4C1 {name}" + ("  (access denied)" if child.denied else "")
                iid = self.tree.insert("", "end", text=label, tags=tags,
                                       values=(fmt_size(size), bar_text, f"{child.file_count:,}", online_text))
                self.row_items[iid] = ("dir", child)
            else:
                icon = "☁" if online else "\U0001F4C4"
                iid = self.tree.insert("", "end", text=f"{icon} {name}",
                                       values=(fmt_size(size), bar_text, "", online_text))
                self.row_items[iid] = ("file", os.path.join(node.path, name))

        if len(entries) > MAX_ROWS:
            rest = entries[MAX_ROWS:]
            self.tree.insert("", "end", text=f"... {len(rest):,} more smaller items", tags=("more",),
                             values=(fmt_size(sum(e[2] for e in rest)), "", "", ""))

        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
        self.tree.focus_set()
        self._update_buttons()
        self._update_org_label()

    def go_up(self):
        if self.current and self.current.parent:
            prev = self.current
            self.show(self.current.parent)
            for iid, (kind, obj) in self.row_items.items():
                if obj is prev:
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    self.tree.see(iid)
                    break

    def _selected(self):
        sel = self.tree.selection()
        return self.row_items.get(sel[0]) if sel else None

    def _update_buttons(self):
        self.up_btn.config(state="normal" if self.current and self.current.parent else "disabled")
        self.explorer_btn.config(state="normal" if self.current else "disabled")

    def _on_double_click(self, event=None):
        item = self._selected()
        if not item:
            return
        kind, obj = item
        if kind == "dir":
            self.show(obj)
        else:
            reveal_in_explorer(obj)

    def _on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or iid not in self.row_items:
            return
        self.tree.selection_set(iid)
        kind, obj = self.row_items[iid]
        path = obj.path if kind == "dir" else obj
        self.menu.delete(0, "end")
        if kind == "dir":
            self.menu.add_command(label="Drill into folder", command=lambda: self.show(obj))
        self.menu.add_command(label="Show in Explorer", command=lambda: reveal_in_explorer(path))
        self.menu.add_command(label="Open folder" if kind == "dir" else "Open file", command=lambda: open_path(path))
        self.menu.add_separator()
        self.menu.add_command(label="Ask AI: can I delete this?", command=lambda: self.ai_explain_path(path))
        if kind == "dir":
            self.menu.add_command(label="Organise this folder (AI)", command=lambda: self._organise_node(obj))
        self.menu.add_separator()
        self.menu.add_command(label="Copy path", command=lambda: self._copy(path))
        self.menu.tk_popup(event.x_root, event.y_root)

    def open_selected_in_explorer(self):
        item = self._selected()
        if item:
            kind, obj = item
            reveal_in_explorer(obj.path if kind == "dir" else obj)
        elif self.current:
            open_path(self.current.path)

    def browse_to(self, folder):
        node = self.root_node.find(folder) if self.root_node else None
        if node:
            self.tabs.select(0)
            self.show(node)
        return node

    # ================================================================ largest files
    def _fill_big(self, top):
        for size, path in top:
            self.big_tree.insert("", "end", iid=path, values=(fmt_size(size), path))

    def _big_open(self):
        sel = self.big_tree.selection()
        if sel:
            reveal_in_explorer(sel[0])

    def _on_big_right_click(self, event):
        iid = self.big_tree.identify_row(event.y)
        if not iid:
            return
        self.big_tree.selection_set(iid)
        self.menu.delete(0, "end")
        self.menu.add_command(label="Show in Explorer", command=lambda: reveal_in_explorer(iid))
        self.menu.add_command(label="Go to folder in Browse", command=lambda: self.browse_to(os.path.dirname(iid)))
        self.menu.add_command(label="Open file", command=lambda: open_path(iid))
        self.menu.add_command(label="Ask AI: can I delete this?", command=lambda: self.ai_explain_path(iid))
        self.menu.add_separator()
        self.menu.add_command(label="Copy path", command=lambda: self._copy(iid))
        self.menu.tk_popup(event.x_root, event.y_root)

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(f"Copied: {text}")

    # ================================================================ clean-up mode
    def _need_scan(self):
        if not self.root_node:
            messagebox.showinfo("Scan first", "Scan a drive or folder first.")
            return True
        return False

    def find_candidates(self):
        if self._need_scan():
            return
        root = self.root_node

        def done(cats, err):
            self._set_ai_busy(False)
            if err:
                return self._ai_error(err)
            self.categories = cats
            self.ai_category = None
            self._fill_clean_tree()
            self.status_var.set(f"Found {sum(len(c.items) for c in cats):,} clean-up candidates")
        self.run_bg(lambda: cleanup.find_candidates(root), done, "Looking for clean-up candidates...")

    def _fill_clean_tree(self):
        t = self.clean_tree
        t.delete(*t.get_children())
        self.clean_items.clear()
        cats = list(self.categories) + ([self.ai_category] if self.ai_category else [])
        for cat in cats:
            risks = {i.get("risk", cat.risk) for i in cat.items}
            risk_label = cat.risk if len(risks) <= 1 else "Mixed"
            cid = t.insert("", "end", text=f"{cat.name}  ({len(cat.items)})", open=False,
                           values=(fmt_size(cat.total), risk_label, "AI suggestions" if cat.source == "ai" else ""),
                           tags=("cat", cat.risk))
            self.clean_items[cid] = cat
            for item in cat.items[:500]:
                risk = item.get("risk", cat.risk)
                iid = t.insert(cid, "end", text=item["path"], values=(fmt_size(item["size"]), risk, item["note"]),
                               tags=(risk,))
                self.clean_items[iid] = item
            if len(cat.items) > 500:
                t.insert(cid, "end", text=f"... {len(cat.items) - 500} more", values=("", "", ""))

        def total(risk):
            return sum(i.get("reclaim", i["size"]) for c in cats for i in c.items if i.get("risk", c.risk) == risk)
        self.savings_var.set(f"Safe to free: {fmt_size(total(cleanup.SAFE))}    "
                             f"Worth reviewing: {fmt_size(total(cleanup.REVIEW) + total(cleanup.CAUTION))}    "
                             f"Keep / special handling: {fmt_size(total(cleanup.KEEP))}")

    def _category_of(self, iid):
        parent = self.clean_tree.parent(iid)
        return self.clean_items.get(parent) if parent else self.clean_items.get(iid)

    def _show_clean_details(self):
        sel = self.clean_tree.selection()
        if not sel or sel[0] not in self.clean_items:
            return
        obj = self.clean_items[sel[0]]
        cat = self._category_of(sel[0])
        if isinstance(obj, cleanup.Category):
            parts = [(obj.name, "h"), (f"Risk: {obj.risk}    Total: {fmt_size(obj.total)}    "
                                       f"Items: {len(obj.items)}\n\n", "muted"),
                     ("Impact: ", "h"), (obj.impact + "\n", None), ("How to clean: ", "h"), (obj.how + "\n", None)]
        else:
            risk = obj.get("risk", cat.risk)
            parts = [(os.path.basename(obj["path"]) or obj["path"], "h"),
                     (f"{obj['path']}\nSize: {fmt_size(obj['size'])}    Risk: {risk}    {obj['note']}\n", "muted")]
            if cat.source == "ai":
                parts += [("Impact (AI): ", "h"), ((obj.get("impact") or "-") + "\n", None),
                          ("Suggested action (AI): ", "h"), ((obj.get("action") or "-") + "\n", None),
                          ("AI suggestions can be wrong - check before deleting.", "warn")]
            else:
                parts += [("Impact: ", "h"), (cat.impact + "\n", None), ("How to clean: ", "h"), (cat.how + "\n", None)]
            if risk == cleanup.KEEP:
                parts.append(("\nDo not delete this manually.", "warn"))
            elif cleanup.is_cloud_synced(obj["path"]) and cat.name != "Cloud files kept on this PC" \
                    and cat.source != "ai":
                parts.append(("\n" + cleanup.CLOUD_NOTE, "warn"))
        self._set_text(self.clean_text, parts)

    def _clean_reveal(self):
        sel = self.clean_tree.selection()
        obj = self.clean_items.get(sel[0]) if sel else None
        if isinstance(obj, dict):
            reveal_in_explorer(obj["path"])

    def _on_clean_right_click(self, event):
        iid = self.clean_tree.identify_row(event.y)
        obj = self.clean_items.get(iid)
        if not isinstance(obj, dict):
            return
        self.clean_tree.selection_set(iid)
        path = obj["path"]
        self.menu.delete(0, "end")
        self.menu.add_command(label="Show in Explorer", command=lambda: reveal_in_explorer(path))
        self.menu.add_command(label="Go to in Browse",
                              command=lambda: self.browse_to(path if obj["kind"] == "dir" else os.path.dirname(path)))
        self.menu.add_command(label="Ask AI about this", command=lambda: self.ai_explain_path(path))
        self.menu.add_separator()
        self.menu.add_command(label="Copy path", command=lambda: self._copy(path))
        self.menu.tk_popup(event.x_root, event.y_root)

    def ai_review(self):
        if self._need_scan():
            return
        if not self.categories:
            self.categories = cleanup.find_candidates(self.root_node)
            self._fill_clean_tree()
        folders = cleanup.unknown_big_folders(self.root_node, self.categories)
        if not folders:
            messagebox.showinfo("Nothing to review", "No large unrecognised folders were found.")
            return

        def done(cat, err):
            self._set_ai_busy(False)
            if err:
                return self._ai_error(err)
            self.ai_category = cat
            self._fill_clean_tree()
            last = self.clean_tree.get_children()[-1]
            self.clean_tree.item(last, open=True)
            self.clean_tree.see(last)
            self.status_var.set(f"AI reviewed {len(cat.items)} folders")
        self.run_bg(lambda: cleanup.ai_review_folders(self.llm, folders, self._status_from_thread), done,
                    f"Asking {self.llm.model} about {len(folders)} large folders (this can take a few minutes)...")

    def ai_explain_selected(self):
        sel = self.clean_tree.selection()
        obj = self.clean_items.get(sel[0]) if sel else None
        if isinstance(obj, dict):
            return self.ai_explain_path(obj["path"])
        item = self._selected()
        if item:
            kind, o = item
            return self.ai_explain_path(o.path if kind == "dir" else o)
        messagebox.showinfo("Select an item", "Select a file or folder first.")

    def ai_explain_path(self, path):
        if self._need_scan():
            return
        node = self.root_node.find(path) if os.path.isdir(path) else None
        size = mtime = None
        if node is None:
            parent = self.root_node.find(os.path.dirname(path))
            name = os.path.basename(path).lower()
            match = next((f for f in parent.files if f[0].lower() == name), None) if parent else None
            if match:
                size, mtime = match[1], match[2]
            elif not os.path.exists(path):
                return messagebox.showwarning("Not found", f"This item no longer exists:\n{path}")
            else:
                st = os.stat(path)
                size, mtime = st.st_size, st.st_mtime
        if self.mode_var.get() != "cleanup":
            self.mode_var.set("cleanup")
            self._switch_mode()

        def done(answer, err):
            self._set_ai_busy(False)
            if err:
                return self._ai_error(err)
            self._set_text(self.clean_text, [(f"AI: {os.path.basename(path) or path}", "h"),
                                             (path + "\n\n", "muted"), (answer + "\n\n", None),
                                             ("AI answers can be wrong - check before deleting.", "warn")])
            self.status_var.set("AI answer ready")
        self._set_text(self.clean_text, [(f"Asking {self.llm.model} about {path} ...", "muted")])
        self.run_bg(lambda: cleanup.ai_explain(self.llm, node, path, size, mtime), done,
                    f"Asking {self.llm.model}...")

    # ================================================================ organiser mode
    def _update_org_label(self):
        if self.current:
            self.org_folder_var.set(f"Folder: {self.current.path}   ({fmt_size(self.current.size)}, "
                                    f"{self.current.file_count:,} files)")

    def _organise_node(self, node):
        self.show(node)
        self.mode_var.set("organise")
        self._switch_mode()
        self.ai_plan()

    def analyse_folder(self, then=None):
        if self._need_scan():
            return
        node, path = self.current, self.current.path

        def done(profile, err):
            self._set_ai_busy(False)
            if err:
                return self._ai_error(err)
            self.profile = profile
            self._render_profile(profile)
            if then:
                then()
        self.run_bg(lambda: organiser.profile_folder(node, path), done, f"Analysing {path}...")

    def _render_profile(self, p, ai=None):
        parts = [(os.path.basename(p["path"].rstrip("\\")) or p["path"], "h"),
                 (f"{fmt_size(p['size'])} (incl. online-only) in {p['file_count']:,} files - "
                  f"{len(p['subfolders'])} subfolders, "
                  f"{p['direct_count']} loose files directly inside\n", "muted")]
        if p["direct_types"]:
            parts.append(("Loose files by type: " + ", ".join(f"{k} {n}" for k, n in p["direct_types"]) + "\n", None))
        if ai:
            parts += [("AI summary", "h"), (ai["summary"] + "\n", None)]
        issues = organiser.rule_issues(p)
        parts.append(("Issues found", "h"))
        parts += [(f"• {i}\n", None) for i in issues] or [("No obvious problems found.\n", "muted")]
        if ai:
            for issue in ai["issues"]:
                if isinstance(issue, dict):
                    parts.append((f"• {issue.get('problem', '')} → {issue.get('fix', '')}\n", None))
            if ai["tips"]:
                parts.append(("Tips", "h"))
                parts += [(f"• {t}\n", None) for t in ai["tips"]]
            parts.append(("\nAI suggestions - review before moving files. Nothing is moved automatically.", "warn"))
        self._set_text(self.org_text, parts)
        self._fill_org_tree(p, ai)

    def _fill_org_tree(self, p, ai):
        t = self.org_tree
        t.delete(*t.get_children())
        if ai:
            groups = {}
            for entry in ai["structure"]:
                if isinstance(entry, dict) and entry.get("folder"):
                    groups[entry["folder"]] = t.insert("", "end", text=f"\U0001F4C1 {entry['folder']}", open=True,
                                                       values=(entry.get("purpose", ""),), tags=("folder",))
            for move in ai["moves"]:
                if not isinstance(move, dict):
                    continue
                target = str(move.get("to", ""))
                parent = groups.get(target)
                if parent is None:
                    parent = groups[target] = t.insert("", "end", text=f"\U0001F4C1 {target or '(unspecified)'}",
                                                       open=True, values=("",), tags=("folder",))
                t.insert(parent, "end", text=f"← {move.get('what', '')}", values=(move.get("why", ""),))
        else:
            dup = t.insert("", "end", text=f"Duplicates ({len(p['duplicates'])})", values=("",), tags=("folder",))
            for paths in p["duplicates"][:100]:
                t.insert(dup, "end", text=os.path.basename(paths[0]), values=(" | ".join(paths),))
            cop = t.insert("", "end", text=f"Copies / versions ({len(p['copies'])})", values=("",), tags=("folder",))
            for c in p["copies"][:200]:
                t.insert(cop, "end", text=os.path.basename(c), values=(c,))
            emp = t.insert("", "end", text=f"Empty folders ({len(p['empty'])})", values=("",), tags=("folder",))
            for e in p["empty"][:200]:
                t.insert(emp, "end", text=os.path.basename(e), values=(e,))

    def ai_plan(self):
        if self._need_scan():
            return
        if not self.profile or self.profile["path"] != self.current.path:
            return self.analyse_folder(then=self.ai_plan)
        profile = self.profile

        def done(ai, err):
            self._set_ai_busy(False)
            if err:
                return self._ai_error(err)
            self._render_profile(profile, ai)
            self.status_var.set("AI organisation plan ready")
        self.run_bg(lambda: organiser.ai_organise(self.llm, profile), done,
                    f"Asking {self.llm.model} for an organisation plan (can take a minute)...")


def reveal_in_explorer(path):
    try:
        core.reveal_in_explorer(path)
    except FileNotFoundError as e:
        messagebox.showwarning("Not found", str(e))


def open_path(path):
    try:
        core.open_path(path)
    except OSError as e:
        messagebox.showerror("Could not open", str(e))


if __name__ == "__main__":
    App().mainloop()
