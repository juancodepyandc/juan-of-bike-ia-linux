import customtkinter as ctk
import psutil
import json
import os
import shutil

# Configuration de base
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AuroraCycleApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AuroraIA - Centre d'Entraînement Autonome")
        self.geometry("950x700")
        self.resizable(False, False)

        # Variables de statut
        self.is_running = False
        self.cloud_status_file = "/home/juan/cloud_ia/status.json"
        
        self.build_ui()
        self.update_local_stats()
        self.update_cloud_stats()

    def build_ui(self):
        # Titre
        self.title_label = ctk.CTkLabel(self, text="CENTRE DE CONTRÔLE - ENTRAÎNEMENT HYBRIDE", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=15)

        # Panneau Principal (Gauche et Droite)
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # --- GAUCHE : Configuration et Monitoring Local ---
        self.left_panel = ctk.CTkFrame(self.main_frame, width=400)
        self.left_panel.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(self.left_panel, text="1. SÉLECTION DU MODULE", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.module_var = ctk.StringVar(value="Module 3D (Trellis - Génération Mesh)")
        self.module_selector = ctk.CTkOptionMenu(
            self.left_panel, 
            variable=self.module_var, 
            values=[
                "Module 3D (Trellis - Génération Mesh)", 
                "Module Rigging (Retargeting et Mouvements)",
                "Module Cyber (Chat/Texte)",
                "Module Vision (Analyse Image)",
                "Module Dessin (Génération Image)",
                "Module Voice (Audio)"
            ],
            width=350,
            command=self.update_version_dropdown
        )
        self.module_selector.pack(pady=5)
        
        ctk.CTkLabel(self.left_panel, text="1b. VERSION DU MODÈLE", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        self.version_var = ctk.StringVar(value="Base (Sécurité maximale)")
        self.version_selector = ctk.CTkOptionMenu(
            self.left_panel, 
            variable=self.version_var,
            values=["Base (Sécurité maximale)", "Renforcé (Aucun entraînement existant)"],
            width=350
        )
        self.version_selector.pack(pady=5)
        
        # Populate immediately
        self.after(500, self.update_version_dropdown)
        
        self.time_switch_label = ctk.CTkLabel(self.left_panel, text="Rotation dans : 00:00 (Inactif)", text_color="cyan")
        self.time_switch_label.pack(pady=5)

        ctk.CTkLabel(self.left_panel, text="2. RESSOURCES LOCALES", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        
        self.cpu_label = ctk.CTkLabel(self.left_panel, text="CPU: 0%")
        self.cpu_label.pack()
        self.cpu_bar = ctk.CTkProgressBar(self.left_panel, width=300)
        self.cpu_bar.pack(pady=2)
        self.cpu_bar.set(0)

        self.ram_label = ctk.CTkLabel(self.left_panel, text="RAM: 0%")
        self.ram_label.pack()
        self.ram_bar = ctk.CTkProgressBar(self.left_panel, width=300)
        self.ram_bar.pack(pady=2)
        self.ram_bar.set(0)

        # Bouton Lancement
        self.start_btn = ctk.CTkButton(self.left_panel, text="🚀 LANCER LE CYCLE", font=ctk.CTkFont(size=18, weight="bold"), height=50, fg_color="green", hover_color="darkgreen", command=self.toggle_cycle)
        self.start_btn.pack(side="bottom", pady=20)

        # --- DROITE : Monitoring Cloud (Kaggle/Colab) ---
        self.right_panel = ctk.CTkFrame(self.main_frame, width=400)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(self.right_panel, text="3. STATUT KAGGLE / COLAB", font=ctk.CTkFont(size=16, weight="bold"), text_color="#00ff00").pack(pady=10)
        
        self.cloud_status_label = ctk.CTkLabel(self.right_panel, text="Statut: EN ATTENTE...", font=ctk.CTkFont(size=14))
        self.cloud_status_label.pack(pady=5)

        self.gpu_cloud_label = ctk.CTkLabel(self.right_panel, text="Utilisation GPU Cloud: 0%")
        self.gpu_cloud_label.pack()
        self.gpu_cloud_bar = ctk.CTkProgressBar(self.right_panel, width=300, progress_color="#00ff00")
        self.gpu_cloud_bar.pack(pady=5)
        self.gpu_cloud_bar.set(0)

        self.improvement_label = ctk.CTkLabel(self.right_panel, text="Amélioration Réelle: N/A", font=ctk.CTkFont(size=20, weight="bold"), text_color="#ffff00")
        self.improvement_label.pack(pady=15)

        ctk.CTkLabel(self.right_panel, text="4. LIMITES GOOGLE DRIVE", font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffcc00").pack(pady=(15, 5))
        
        # Quota Journalier (750Go)
        self.quota_label = ctk.CTkLabel(self.right_panel, text="Transfert Journalier: 0 / 750 Go")
        self.quota_label.pack()
        self.quota_bar = ctk.CTkProgressBar(self.right_panel, width=300, progress_color="orange")
        self.quota_bar.pack(pady=2)
        self.quota_bar.set(0)
        
        # Requêtes API (Approx 10k par jour)
        self.api_label = ctk.CTkLabel(self.right_panel, text="Requêtes API Sécurisées: 0 / 10000")
        self.api_label.pack()
        self.api_bar = ctk.CTkProgressBar(self.right_panel, width=300, progress_color="red")
        self.api_bar.pack(pady=2)
        self.api_bar.set(0)
        
        # Total Espace Disque
        self.disk_label = ctk.CTkLabel(self.right_panel, text="Espace Drive Restant: Calcul...", font=ctk.CTkFont(size=13, slant="italic"))
        self.disk_label.pack(pady=10)

        # --- NOUVELLE SECTION : COMPARAISON ET VALIDATION ---
        ctk.CTkLabel(self.right_panel, text="5. COMPARAISON ET RÉSULTATS", font=ctk.CTkFont(size=16, weight="bold"), text_color="#00ffff").pack(pady=(15, 5))
        
        self.training_progress_label = ctk.CTkLabel(self.right_panel, text="Progression de l'entraînement : 0%")
        self.training_progress_label.pack()
        self.training_progress_bar = ctk.CTkProgressBar(self.right_panel, width=300, progress_color="#00ffff")
        self.training_progress_bar.pack(pady=5)
        self.training_progress_bar.set(0)
        
        self.compare_btn = ctk.CTkButton(self.right_panel, text="👁️ COMPARER AVANT / APRÈS", fg_color="#0055ff", hover_color="#0033aa", state="disabled", command=self.open_comparison)
        self.compare_btn.pack(pady=10)
        
        self.validation_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.validation_frame.pack(pady=5)
        
        self.accept_btn = ctk.CTkButton(self.validation_frame, text="✅ VALIDER", fg_color="green", hover_color="darkgreen", width=140, state="disabled", command=self.accept_model)
        self.accept_btn.grid(row=0, column=0, padx=5)
        
        self.reject_btn = ctk.CTkButton(self.validation_frame, text="❌ REJETER", fg_color="red", hover_color="darkred", width=140, state="disabled", command=self.reject_model)
        self.reject_btn.grid(row=0, column=1, padx=5)

    def open_comparison(self):
        import subprocess
        # Lecture des fichiers depuis status.json
        if os.path.exists(self.cloud_status_file):
            try:
                with open(self.cloud_status_file, "r") as f:
                    data = json.load(f)
                    file_base = data.get("file_base", "")
                    file_new = data.get("file_new", "")
                    if file_base and file_new:
                        if file_base.endswith(".glb"):
                            # Lancer f3d sur les deux fichiers
                            subprocess.Popen(["/home/juan/.local/bin/f3d", file_base])
                            subprocess.Popen(["/home/juan/.local/bin/f3d", file_new])
                        else:
                            # Pour les images ou textes, on ouvrira avec l'outil par défaut
                            subprocess.Popen(["xdg-open", file_base])
                            subprocess.Popen(["xdg-open", file_new])
            except Exception as e:
                print("Erreur ouverture", e)

    def accept_model(self):
        self.cloud_status_label.configure(text="Validation manuelle: Modèle remplacé !", text_color="green")
        # Logique pour dire au script de remplacer
        with open("/home/juan/cloud_ia/validation_signal.txt", "w") as f:
            f.write("ACCEPT")
        self.accept_btn.configure(state="disabled")
        self.reject_btn.configure(state="disabled")

    def reject_model(self):
        self.cloud_status_label.configure(text="Validation manuelle: Modèle rejeté.", text_color="red")
        with open("/home/juan/cloud_ia/validation_signal.txt", "w") as f:
            f.write("REJECT")
        self.accept_btn.configure(state="disabled")
        self.reject_btn.configure(state="disabled")
    def update_version_dropdown(self, choice=None):
        selected = self.module_var.get()
        safe_name = selected.split(' ')[0].lower()
        metadata_path = "/home/juan/AuroraIA/models/metadata.json"
        
        base_val = "Base (Sécurité maximale)"
        renf_val = "Renforcé (Aucun entraînement existant)"
        
        import os, json
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    meta = json.load(f)
                    if f"{safe_name}_base" in meta:
                        base_val = meta[f"{safe_name}_base"]
                    if f"{safe_name}_renforce" in meta:
                        renf_val = meta[f"{safe_name}_renforce"]
            except: pass
            
        self.version_selector.configure(values=[base_val, renf_val])
        self.version_var.set(renf_val if "Aucun" not in renf_val else base_val)

    def toggle_cycle(self):
        if not self.is_running:
            self.is_running = True
            self.start_btn.configure(text="🛑 STOPPER PROPREMENT", fg_color="red", hover_color="darkred")
            self.module_selector.configure(state="disabled")
            self.version_selector.configure(state="disabled")
            
            selected = self.module_var.get()
            selected_version = self.version_var.get()
            self.cloud_status_label.configure(text=f"Statut: Génération Locale ({selected_version})...", text_color="yellow")
            
            import subprocess
            self.process = subprocess.Popen(
                ["/home/juan/AuroraIA/cycle_app_venv/bin/python", "/home/juan/AuroraIA/cycle_generator_universal.py", selected, selected_version],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.check_process_status()

        else:
            if hasattr(self, 'process') and self.process:
                import signal
                try:
                    self.process.send_signal(signal.SIGINT)
                    self.cloud_status_label.configure(text="Statut: Enregistrement et Arrêt (fin du cycle)...", text_color="orange")
                except: pass

    def check_process_status(self):
        if self.is_running and hasattr(self, 'process'):
            if self.process.poll() is not None:
                # Le processus est mort (arrêté proprement)
                self.is_running = False
                self.start_btn.configure(text="🚀 LANCER LE CYCLE", fg_color="green", hover_color="darkgreen")
                self.module_selector.configure(state="normal")
                self.version_selector.configure(state="normal")
                self.cloud_status_label.configure(text="Statut: ARRÊTÉ PROPREMENT", text_color="white")
                self.time_switch_label.configure(text="Rotation dans : 00:00 (Inactif)")
                self.update_version_dropdown()
            else:
                self.after(1000, self.check_process_status)

    def update_local_stats(self):
        # Update CPU / RAM
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        self.cpu_label.configure(text=f"CPU Local: {cpu}%")
        self.cpu_bar.set(cpu / 100.0)
        
        self.ram_label.configure(text=f"RAM Locale: {ram}%")
        self.ram_bar.set(ram / 100.0)
        
        # Check Total Disk Space
        try:
            total, used, free = shutil.disk_usage("/home/juan/cloud_ia")
            free_gb = free // (2**30)
            total_gb = total // (2**30)
            self.disk_label.configure(text=f"Espace Drive Restant: {free_gb} Go / {total_gb} Go")
        except Exception:
            self.disk_label.configure(text="Espace Drive Restant: Non monté / Erreur")

        self.after(2000, self.update_local_stats)

    def update_cloud_stats(self):
        if self.is_running:
            # Mode Manuel strict pour le moment, pas d'automatisation
            self.time_switch_label.configure(text="Mode Manuel - En attente de vos actions")
            
            # Read stats
            if os.path.exists(self.cloud_status_file):
                try:
                    with open(self.cloud_status_file, "r") as f:
                        data = json.load(f)
                        self.cloud_status_label.configure(text=f"Statut: {data.get('status', 'En cours')}")
                        gpu = data.get("gpu_percent", 0)
                        self.gpu_cloud_label.configure(text=f"Utilisation GPU Cloud: {gpu}%")
                        self.gpu_cloud_bar.set(gpu / 100.0)
                        self.improvement_label.configure(text=f"Amélioration Réelle: +{data.get('improvement', '0')}%")
                        
                        upload_gb = data.get("upload_gb", 0)
                        self.quota_label.configure(text=f"Transfert Journalier: {upload_gb} / 750 Go")
                        self.quota_bar.set(min(upload_gb / 750.0, 1.0))
                        
                        api_req = data.get("api_req", 0)
                        self.api_label.configure(text=f"Requêtes API Sécurisées: {api_req} / 10000")
                        self.api_bar.set(min(api_req / 10000.0, 1.0))
                        
                        # Nouvelles stats
                        progress = data.get("progress_percent", 0)
                        self.training_progress_label.configure(text=f"Progression de l'entraînement : {progress}%")
                        self.training_progress_bar.set(progress / 100.0)
                        
                        file_base = data.get("file_base", "")
                        file_new = data.get("file_new", "")
                        if file_base and file_new:
                            self.compare_btn.configure(state="normal")
                        else:
                            self.compare_btn.configure(state="disabled")
                            
                        waiting = data.get("waiting_validation", False)
                        if waiting:
                            self.accept_btn.configure(state="normal")
                            self.reject_btn.configure(state="normal")
                            self.cloud_status_label.configure(text="Statut: EN ATTENTE DE VALIDATION MANUELLE", text_color="yellow")
                        else:
                            self.accept_btn.configure(state="disabled")
                            self.reject_btn.configure(state="disabled")
                except Exception as e:
                    pass
            else:
                self.cloud_status_label.configure(text="Statut: En attente de données réelles...")
        
        self.after(5000, self.update_cloud_stats)

if __name__ == "__main__":
    app = AuroraCycleApp()
    app.mainloop()
