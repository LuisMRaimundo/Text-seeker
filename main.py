# main.py — GUI for text-seeker
def run_interface(search_fn):
    """
    Arranca a GUI e usa a função `search_fn` injetada para executar a pesquisa.
    `search_fn(directory, boolean_query, file_types, min_relevance, context_size,
               ocr_mode, output_path, output_format) -> list`
    """
    try:
        import os
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        print("CRITICAL: Tkinter not installed. Cannot run GUI.")
        return

    root = tk.Tk()
    root.title("text-seeker")
    root.geometry("900x720")

    # Variáveis
    dir_var = tk.StringVar()
    query_var = tk.StringVar()
    out_var = tk.StringVar()
    min_rel_var = tk.DoubleVar(value=0.1)
    ctx_var = tk.IntVar(value=150)
    ocr_var = tk.StringVar(value="auto")
    ocr_skip_paths = set()
    ocr_skip_count = tk.StringVar(value="OCR skip: 0")
    prog_var = tk.DoubleVar(value=0.0)
    eta_var = tk.StringVar(value="ETA: --")
    include_subfolders_var = tk.BooleanVar(value=True)

    ft_vars = {
        'txt': tk.BooleanVar(value=True),
        'pdf': tk.BooleanVar(value=True),
        'docx': tk.BooleanVar(value=True),
        'html': tk.BooleanVar(value=False),
        'image': tk.BooleanVar(value=False),
        'md': tk.BooleanVar(value=False),
        'excel': tk.BooleanVar(value=False),
        'csv': tk.BooleanVar(value=False),
    }
    
    # Performance options
    use_indexing_var = tk.BooleanVar(value=True)
    use_parallel_var = tk.BooleanVar(value=True)
    use_stemming_var = tk.BooleanVar(value=True)
    accent_sensitive_var = tk.BooleanVar(value=False)
    split_output_var = tk.BooleanVar(value=False)
    max_results_per_file_var = tk.IntVar(value=100)

    def on_browse_dir():
        p = filedialog.askdirectory()
        if p:
            dir_var.set(p)

    def on_browse_out():
        p = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[
                ("HTML", "*.html"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx"),
                ("Text", "*.txt")
            ]
        )
        if p:
            out_var.set(p)

    def on_pre_scan_ocr():
        d = dir_var.get()
        if not d:
            messagebox.showwarning("Missing Info", "Please select a directory first.")
            return
        file_types = {k: v.get() for k, v in ft_vars.items()}
        status_label.config(text="Pre-scanning OCR candidates...")
        root.update()
        try:
            from app import scan_ocr_candidates
            candidates = scan_ocr_candidates(d, file_types, include_subfolders=include_subfolders_var.get())
        except Exception as e:
            messagebox.showerror("Error", f"Pre-scan failed: {e}")
            status_label.config(text="Ready.")
            return
        status_label.config(text="Ready.")
        if not candidates:
            messagebox.showinfo("Pre-scan", "No OCR candidates detected.")
            return

        win = tk.Toplevel(root)
        win.title("OCR Candidates (select to skip)")
        win.geometry("800x500")
        ttk.Label(win, text=f"Found {len(candidates)} OCR candidates. Select any to skip OCR.").pack(anchor="w", padx=8, pady=6)
        lst = tk.Listbox(win, selectmode=tk.MULTIPLE)
        lst.pack(fill="both", expand=True, padx=8, pady=6)
        for c in candidates:
            lst.insert("end", c)

        def _apply_skip():
            selected = {lst.get(i) for i in lst.curselection()}
            ocr_skip_paths.update(selected)
            ocr_skip_count.set(f"OCR skip: {len(ocr_skip_paths)}")
            win.destroy()

        def _clear_skip():
            ocr_skip_paths.clear()
            ocr_skip_count.set("OCR skip: 0")
            win.destroy()

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=8, pady=6)
        ttk.Button(btns, text="Skip OCR for selected", command=_apply_skip).pack(side="left")
        ttk.Button(btns, text="Clear skip list", command=_clear_skip).pack(side="left", padx=6)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    def on_search():
        d, q, out = dir_var.get(), query_var.get(), out_var.get()
        if not d or not q:
            messagebox.showwarning("Missing Info", "Please select a directory and enter a query.")
            return

        status_label.config(text="Searching... please wait.")
        prog_var.set(0.0)
        eta_var.set("ETA: --")
        root.update()

        # Formato de saída pela extensão
        if out:
            out_lower = out.lower()
            if out_lower.endswith('.csv'):
                out_fmt = 'csv'
            elif out_lower.endswith('.xlsx'):
                out_fmt = 'xlsx'
            elif out_lower.endswith('.txt'):
                out_fmt = 'txt'
            else:
                out_fmt = 'html'
        else:
            out_fmt = 'html'

        def _progress_cb(processed: int, total: int, remaining_sec: float):
            pct = 0.0 if total <= 0 else (processed / total) * 100.0
            prog_var.set(pct)
            if remaining_sec > 0:
                mins = int(remaining_sec // 60)
                secs = int(remaining_sec % 60)
                eta_var.set(f"ETA: {mins}m {secs}s")
            else:
                eta_var.set("ETA: --")
            root.update_idletasks()

        try:
            file_types = {k: v.get() for k, v in ft_vars.items()}
            results = search_fn(
                directory=d,
                boolean_query=q,
                file_types=file_types,
                min_relevance=min_rel_var.get(),
                context_size=ctx_var.get(),
                ocr_mode=ocr_var.get(),
                output_path=out if out else None,
                output_format=out_fmt,
                use_indexing=use_indexing_var.get(),
                use_parallel=use_parallel_var.get(),
                use_stemming=use_stemming_var.get(),
                accent_fold=not accent_sensitive_var.get(),
                progress_callback=_progress_cb,
                ocr_skip_paths=ocr_skip_paths,
                include_subfolders=include_subfolders_var.get(),
                output_per_folder=split_output_var.get(),
                max_results_per_file=max_results_per_file_var.get() if split_output_var.get() else 0,
            )
            msg = f"Found {len(results)} results."
            if out:
                out_dir = os.path.dirname(out)
                base = os.path.splitext(os.path.basename(out))[0]
                idx_path = os.path.join(out_dir or ".", f"{base}_INDEX.html")
                if split_output_var.get() and os.path.exists(idx_path):
                    msg += f"\nGuardado em vários ficheiros. Abra o índice: {base}_INDEX.html"
                else:
                    msg += f"\nSaved to {out}"
            messagebox.showinfo("Search Complete", msg)
            status_label.config(text="Ready.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
            status_label.config(text="Error occurred.")

    # Layout
    main = ttk.Frame(root, padding=20)
    main.pack(fill='both', expand=True)

    ttk.Label(main, text="Directory:").grid(row=0, column=0, sticky='w')
    ttk.Entry(main, textvariable=dir_var, width=50).grid(row=0, column=1, padx=5, sticky='ew')
    ttk.Button(main, text="Browse...", command=on_browse_dir).grid(row=0, column=2)

    ttk.Label(main, text="Query (AND/OR/NEAR):").grid(row=1, column=0, sticky='w', pady=10)
    ttk.Entry(main, textvariable=query_var, width=50).grid(row=1, column=1, padx=5, sticky='ew')
    ttk.Label(
        main,
        text='Examples: piano AND cello | "spectral centroid" | clar* OR bass? | term1 NEAR/5 term2 | NOT noise',
        foreground="#666666"
    ).grid(row=2, column=1, sticky='w', padx=5)

    ft_frame = ttk.LabelFrame(main, text="File Types")
    ft_frame.grid(row=3, column=0, columnspan=3, sticky='ew', pady=10)
    for k, v in ft_vars.items():
        ttk.Checkbutton(ft_frame, text=k.upper(), variable=v).pack(side='left', padx=10)

    adv_frame = ttk.LabelFrame(main, text="Advanced Options")
    adv_frame.grid(row=4, column=0, columnspan=3, sticky='ew', pady=10)

    ttk.Label(adv_frame, text="OCR Mode:").pack(side='left', padx=5)
    ttk.Combobox(adv_frame, textvariable=ocr_var, values=["auto", "force", "never"], width=10).pack(side='left')

    ttk.Label(adv_frame, text="Min Relevance:").pack(side='left', padx=10)
    ttk.Spinbox(adv_frame, from_=0.0, to=1.0, increment=0.1, textvariable=min_rel_var, width=5).pack(side='left')

    ttk.Label(adv_frame, text="Context Size:").pack(side='left', padx=10)
    ttk.Spinbox(adv_frame, from_=50, to=500, increment=50, textvariable=ctx_var, width=5).pack(side='left')
    
    ttk.Checkbutton(adv_frame, text="Search subfolders", variable=include_subfolders_var).pack(side='left', padx=10)

    ttk.Label(main, text="Output File (Optional):").grid(row=5, column=0, sticky='w')
    ttk.Entry(main, textvariable=out_var, width=50).grid(row=5, column=1, padx=5, sticky='ew')
    ttk.Button(main, text="Save As...", command=on_browse_out).grid(row=5, column=2)

    out_split_frame = ttk.LabelFrame(main, text="Opções de saída", padding="6")
    out_split_frame.grid(row=6, column=0, columnspan=3, sticky='ew', padx=0, pady=(4, 0))
    ttk.Checkbutton(
        out_split_frame,
        text="Guardar em vários ficheiros (evita acumular demasiado texto)",
        variable=split_output_var
    ).pack(side='left')
    ttk.Label(out_split_frame, text="Máx. resultados por ficheiro:").pack(side='left', padx=(15, 4))
    ttk.Spinbox(out_split_frame, from_=50, to=1000, increment=50, textvariable=max_results_per_file_var, width=6).pack(side='left')
    ttk.Label(out_split_frame, text="(ex.: 100)", foreground="#666666").pack(side='left', padx=4)

    # Performance options
    perf_frame = ttk.LabelFrame(main, text="Performance Options", padding="10")
    perf_frame.grid(row=7, column=0, columnspan=3, sticky='ew', padx=5, pady=10)
    
    ttk.Checkbutton(perf_frame, text="Use Indexing (faster on large sets)", 
                   variable=use_indexing_var).pack(side='left', padx=10)
    ttk.Checkbutton(perf_frame, text="Parallel Processing (multi-core)", 
                   variable=use_parallel_var).pack(side='left', padx=10)

    ling_frame = ttk.LabelFrame(main, text="Linguistic Options", padding="10")
    ling_frame.grid(row=8, column=0, columnspan=3, sticky='ew', padx=5, pady=6)
    ttk.Checkbutton(ling_frame, text="Stemming (PT/EN: run/running, análise/analise)",
                    variable=use_stemming_var).pack(side='left', padx=10)
    ttk.Checkbutton(ling_frame, text="Accent-sensitive (ação ≠ acao)",
                    variable=accent_sensitive_var).pack(side='left', padx=10)

    ttk.Button(main, text="Pre-scan OCR", command=on_pre_scan_ocr).grid(
        row=9, column=0, pady=8, sticky='w'
    )
    ttk.Label(main, textvariable=ocr_skip_count).grid(row=9, column=1, sticky='w')

    ttk.Button(main, text="START SEARCH", command=on_search, style="Accent.TButton").grid(
        row=10, column=0, columnspan=3, pady=12, sticky='ew'
    )

    prog = ttk.Progressbar(main, variable=prog_var, maximum=100.0)
    prog.grid(row=11, column=0, columnspan=2, sticky='ew', pady=(0, 6))
    ttk.Label(main, textvariable=eta_var).grid(row=11, column=2, sticky='e', padx=6)

    status_label = ttk.Label(main, text="Ready.", relief='sunken')
    status_label.grid(row=12, column=0, columnspan=3, sticky='ew')

    legal_frame = ttk.LabelFrame(main, text="Copyright and use", padding="8")
    legal_frame.grid(row=13, column=0, columnspan=3, sticky='ew', pady=(8, 0))
    legal_text = (
        "Copyright © 2026 Luís Raimundo. All rights reserved.\n"
        "Proprietary research material. No open-source licence is granted.\n"
        "Contact: lmr.2020@outlook.pt\n\n"
        "Acknowledgements: FCT and Universidade NOVA de Lisboa "
        "(DOI: 10.54499/2020.08817.BD). Thanks to Isabel Pires."
    )
    ttk.Label(legal_frame, text=legal_text, wraplength=820, justify='left').pack(anchor='w')

    main.columnconfigure(1, weight=1)
    root.geometry("900x820")
    root.mainloop()
