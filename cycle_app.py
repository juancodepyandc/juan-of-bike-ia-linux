"""Local training center; light UI venv and a separate ML worker process."""
from __future__ import annotations
import json
import os
import signal
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
import psutil
from auto_rl.config import LABELS, PYTHON, ROOT, STATE, defaults, validate
from auto_rl.storage import atomic_json, read_json, submit_decision

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AuroraCycleApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AuroraIA · Entraîner et comparer")
        self.geometry("1180x850")
        self.minsize(1000, 720)
        self.process = self.log_handle = self.diagnostic = None
        self.status, self.reference, self.closing = {}, "", False
        STATE.mkdir(parents=True, exist_ok=True)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.build_ui()
        self.after(200, self.refresh)

    def build_ui(self):
        ctk.CTkLabel(self, text="AURORA  /  ENTRAÎNER ET COMPARER", font=ctk.CTkFont(size=25, weight="bold")).pack(anchor="w", padx=25, pady=(22, 4))
        ctk.CTkLabel(self, text="Poids d'origine conservés · Candidats séparés · Validation manuelle par défaut", text_color="#a7bacf").pack(anchor="w", padx=25)
        layout = ctk.CTkFrame(self, fg_color="transparent")
        layout.pack(fill="both", expand=True, padx=20, pady=15)
        left = ctk.CTkScrollableFrame(layout, width=350)
        left.pack(side="left", fill="y", padx=(0, 15))
        right = ctk.CTkFrame(layout)
        right.pack(side="right", fill="both", expand=True)
        self.module = ctk.StringVar(value=LABELS["3d"])
        ctk.CTkLabel(left, text="Modèle à améliorer", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(10, 6))
        self.module_menu = ctk.CTkOptionMenu(left, values=list(LABELS.values()), variable=self.module, width=315, command=self.module_changed)
        self.module_menu.pack(pady=5)
        self.version_label = ctk.CTkLabel(left, text="Base intacte", wraplength=310, text_color="#82d5c6")
        self.version_label.pack(pady=8)
        ctk.CTkLabel(left, text="Sujet personnel (facultatif)").pack(anchor="w", pady=(12, 3))
        self.prompt = ctk.CTkTextbox(left, width=315, height=85)
        self.prompt.pack()
        self.reference_label = ctk.CTkLabel(left, text="3D : tes références locales, complétées si nécessaire", wraplength=305)
        self.reference_label.pack(pady=5)
        self.image_button = ctk.CTkButton(left, text="Choisir une image de référence 3D", command=self.pick_image, width=315)
        self.image_button.pack(pady=5)
        ctk.CTkLabel(left, text="Durée et nombre d'essais", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(20, 5))
        self.profile = ctk.StringVar(value="Premier essai")
        ctk.CTkOptionMenu(left, values=["Premier essai", "Approfondi"], variable=self.profile, width=315).pack(pady=5)
        
        self.execution_mode = ctk.StringVar(value="Hybride (PC + Cloud)")
        ctk.CTkOptionMenu(left, values=["Local 100%", "Hybride (PC + Cloud)"], variable=self.execution_mode, width=315).pack(pady=5)
        
        ctk.CTkLabel(left, text="Premier essai : 3 à 6 sujets d'apprentissage,\n3 sujets d'audit × 2 graines.\nLe temps dépend fortement du modèle.", justify="left", text_color="#a7bacf").pack(anchor="w", pady=8)
        ctk.CTkLabel(left, text="Nombre de cycles (1 à 100)").pack(anchor="w")
        self.cycles = ctk.CTkEntry(left, width=100)
        self.cycles.insert(0, "1")
        self.cycles.pack(anchor="w", pady=5)
        self.auto = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(left, text="Valider automatiquement", variable=self.auto).pack(anchor="w", pady=(16, 5))
        ctk.CTkLabel(left, text="Automatique : audit porté à 8 sujets,\narrêt après 3 rejets consécutifs.\nÀ activer après tes premiers comparatifs.", justify="left", text_color="#a7bacf").pack(anchor="w", pady=5)
        self.start_btn = ctk.CTkButton(left, text="LANCER LE CYCLE", height=46, width=315, fg_color="#137c69", command=self.start)
        self.start_btn.pack(pady=(20, 8))
        self.stop_btn = ctk.CTkButton(left, text="Arrêter le cycle", width=315, fg_color="#8a3c45", state="disabled", command=self.stop)
        self.stop_btn.pack(pady=5)
        self.doctor_btn = ctk.CTkButton(left, text="Vérifier l'installation", width=315, command=self.run_doctor)
        self.doctor_btn.pack(pady=10)
        ctk.CTkButton(left, text="Campagne de tous les modules", width=315, command=self.start_campaign).pack(pady=5)
        ctk.CTkButton(left, text="Arrêter la campagne", width=315, fg_color="#8a3c45", command=self.stop_campaign).pack(pady=5)
        ctk.CTkButton(left, text="Interface web · entraînement et médias", width=315,
                         command=lambda: self.open_path("http://127.0.0.1:3001/api/training/ui")).pack(pady=5)
        self.phase_label = ctk.CTkLabel(right, text="Prêt pour un premier cycle", font=ctk.CTkFont(size=20, weight="bold"), wraplength=640, justify="left")
        self.phase_label.pack(anchor="w", padx=20, pady=(20, 10))
        self.progress = ctk.CTkProgressBar(right)
        self.progress.pack(fill="x", padx=20, pady=5)
        self.progress.set(0)
        self.resources = ctk.CTkLabel(right, text="Ressources locales", text_color="#a7bacf")
        self.resources.pack(anchor="w", padx=20, pady=8)
        self.score = ctk.CTkLabel(right, text="Gain mesuré : en attente de l'audit", font=ctk.CTkFont(size=21), text_color="#82d5c6")
        self.score.pack(anchor="w", padx=20, pady=12)
        self.metrics = ctk.CTkLabel(right, text="", wraplength=640, justify="left")
        self.metrics.pack(anchor="w", padx=20, pady=5)
        self.compare_btn = ctk.CTkButton(right, text="OUVRIR LA COMPARAISON AVANT / APRÈS", height=42, command=self.compare, state="disabled")
        self.compare_btn.pack(fill="x", padx=20, pady=(15, 8))
        decisions = ctk.CTkFrame(right, fg_color="transparent")
        decisions.pack(fill="x", padx=20)
        self.accept_btn = ctk.CTkButton(decisions, text="Valider le candidat", fg_color="#137c69", command=lambda: self.decide("ACCEPT"), state="disabled")
        self.accept_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.reject_btn = ctk.CTkButton(decisions, text="Rejeter / conserver le champion", fg_color="#8a3c45", command=lambda: self.decide("REJECT"), state="disabled")
        self.reject_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))
        files = ctk.CTkFrame(right, fg_color="transparent")
        files.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(files, text="Fichiers 3D côte à côte", command=self.open_artifacts).pack(side="left", padx=(0, 8))
        ctk.CTkButton(files, text="Historique", command=lambda: self.open_path(STATE / "runs")).pack(side="left")
        ctk.CTkLabel(right, text="Journal du cycle", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(10, 4))
        self.log = ctk.CTkTextbox(right, height=200, font=("monospace", 12))
        self.log.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.module_changed()

    def key(self):
        return next(k for k, v in LABELS.items() if v == self.module.get())

    def module_changed(self, *_):
        record = read_json(STATE / "registry" / (self.key() + ".json"), {})
        self.version_label.configure(text=f"Base intacte · {record['name']} disponible" if record else "Base intacte · aucun champion validé")
        self.image_button.configure(state="normal" if self.key() == "3d" else "disabled")

    def pick_image(self):
        value = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if value:
            self.reference = value
            self.reference_label.configure(text=Path(value).name)

    def start(self):
        if self.process and self.process.poll() is None:
            return
        try:
            c = defaults(self.key())
            c.update(prompt=self.prompt.get("1.0", "end").strip(), reference_image=self.reference,
                     cycles=int(self.cycles.get()), mode="auto" if self.auto.get() else "manual")
            c.update(iterations=1, directions=1) if self.profile.get() == "Premier essai" else c.update(iterations=3, directions=2, train_tasks=8, eval_tasks=6)
            if self.key() in {'video','animation'}:
                c['train_tasks']=3
                c['local_epochs']=1 if self.profile.get()=='Premier essai' else 3
                c['directions']=2  # At least six measured observations for Kaggle.
            exec_map = {"Local 100%": "local", "Hybride (PC + Cloud)": "hybrid"}
            c.update(execution=exec_map[self.execution_mode.get()])
            if c["mode"] == "auto":
                c["eval_tasks"] = 8
            validate(c)
            if not PYTHON.is_file():
                raise ValueError(f"Environnement IA introuvable : {PYTHON}")
            path = STATE / "launch_config.json"
            atomic_json(path, c)
            self.log_handle = (STATE / "worker.log").open("w")
            self.process = subprocess.Popen([str(PYTHON), "-u", "-m", "auto_rl.cli", "run", "--config", str(path)],
                cwd=ROOT, stdout=self.log_handle, stderr=subprocess.STDOUT, start_new_session=True)
            self.phase_label.configure(text="Démarrage du moteur local…")
        except (ValueError, OSError) as e:
            messagebox.showerror("Lancement impossible", str(e))

    def start_campaign(self):
        try:
            campaign = read_json(STATE / "campaign.json", {})
            if campaign.get("phase") == "running" and psutil.pid_exists(campaign.get("pid", 0)):
                self.phase_label.configure(text="La campagne est déjà en cours.")
                return
            profile = Path.home() / "Bureau/Aurora_Entrainement.json"
            if not profile.is_file():
                raise ValueError("Profil de campagne absent : " + str(profile))
            with (STATE / "campaign.log").open("a") as log:
                subprocess.Popen([str(PYTHON), "-u", "-m", "auto_rl.campaign", "run", "--config", str(profile)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            self.phase_label.configure(text="Campagne démarrée ; suivi du module courant ci-dessous.")
        except (ValueError, OSError) as e:
            messagebox.showerror("Campagne impossible", str(e))

    def stop_campaign(self):
        (STATE / "campaign.stop").write_text("STOP")
        self.phase_label.configure(text="Arrêt de la campagne demandé…")

    def stop(self):
        if self.status.get("run_id"):
            (STATE / "runs" / self.status["run_id"] / "stop_signal.txt").write_text("STOP")
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGINT)
        self.phase_label.configure(text="Arrêt demandé…")

    def decide(self, decision):
        try:
            submit_decision(STATE, self.status["run_id"], decision)
            self.accept_btn.configure(state="disabled")
            self.reject_btn.configure(state="disabled")
        except (ValueError, KeyError) as e:
            messagebox.showerror("Validation impossible", str(e))

    def open_path(self, path):
        if path and Path(path).exists():
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def compare(self):
        self.open_path(self.status.get("report"))

    def open_artifacts(self):
        import shutil
        for field in ("file_base", "file_new"):
            path = self.status.get(field)
            if path and Path(path).exists():
                f3d = shutil.which("f3d") or str(Path.home() / ".local/bin/f3d")
                if path.endswith(".glb") and Path(f3d).is_file():
                    subprocess.Popen([f3d, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    self.open_path(path)

    def run_doctor(self):
        if self.diagnostic and self.diagnostic.poll() is None:
            return
        self.doctor_log = (STATE / "doctor.log").open("w")
        self.diagnostic = subprocess.Popen([str(PYTHON), "-m", "auto_rl.cli", "doctor"], cwd=ROOT, stdout=self.doctor_log, stderr=subprocess.STDOUT)
        self.doctor_btn.configure(text="Vérification en cours…", state="disabled")

    def refresh(self):
        try:
            s = self.status = read_json(STATE / "status.json", {})
            active = bool(self.process and self.process.poll() is None)
            other = bool(s.get("pid") and psutil.pid_exists(s["pid"]) and s.get("phase") not in {"accepted", "rejected", "error", "cancelled"})
            busy = active or other
            self.start_btn.configure(state="disabled" if busy else "normal")
            self.stop_btn.configure(state="normal" if busy else "disabled")
            self.module_menu.configure(state="disabled" if busy else "normal")
            if s:
                self.phase_label.configure(text=s.get("status", "Prêt"))
                self.progress.set(s.get("progress_percent", 0) / 100)
                gain = s.get("improvement")
                self.score.configure(text=f"Gain face au champion : {gain:+.3f} points / 100" if isinstance(gain, (int, float)) else "Gain mesuré : en attente de l'audit")
                self.metrics.configure(text=" · ".join(s.get("rejection_reasons", [])) or f"Score du juge : {s.get('judge_score')}  |  Objectif d'entraînement : {s.get('loss')}")
                self.compare_btn.configure(state="normal" if s.get("report") and Path(s["report"]).is_file() else "disabled")
                waiting = busy and s.get("phase") == "awaiting_validation"
                self.accept_btn.configure(state="normal" if waiting and s.get("eligible") else "disabled")
                self.reject_btn.configure(state="normal" if waiting else "disabled")
                if not busy and s.get("phase") not in {"accepted", "rejected", "error", "cancelled"}:
                    self.phase_label.configure(text="Processus interrompu. Les fichiers produits restent dans l'historique.")
            self.resources.configure(text=f"CPU {psutil.cpu_percent():.0f} % · RAM {psutil.virtual_memory().percent:.0f} % · GPU {s.get('gpu_percent', 0):.0f} % · VRAM {s.get('gpu_memory_gb', 0):.1f} Go")
            path = STATE / "worker.log"
            if path.exists():
                with path.open("rb") as f:
                    f.seek(max(0, path.stat().st_size - 9000))
                    content = f.read().decode(errors="replace")
                if getattr(self, "last_log", None) != content:
                    self.log.delete("1.0", "end")
                    self.log.insert("end", content)
                    self.log.see("end")
                    self.last_log = content
            if self.process and self.process.poll() is not None and self.log_handle:
                self.log_handle.close()
                self.log_handle = None
                self.module_changed()
            if self.diagnostic and self.diagnostic.poll() is not None:
                self.doctor_log.close()
                self.doctor_btn.configure(text="Vérifier l'installation", state="normal")
                self.diagnostic = None
                self.open_path(STATE / "doctor.json")
            if self.closing and not active:
                self.destroy()
                return
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        self.after(1000, self.refresh)

    def close_window(self):
        if self.process and self.process.poll() is None:
            self.closing = True
            self.stop()
            self.after(15000, self.force_close_worker)
        else:
            self.destroy()

    def force_close_worker(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.after(5000, self.kill_worker)

    def kill_worker(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)


if __name__ == "__main__":
    AuroraCycleApp().mainloop()
