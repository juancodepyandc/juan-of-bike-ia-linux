import os
import time
import json
import torch
import torch.nn as nn
import torch.optim as optim
import trimesh

print("=== INITIALISATION DU MOTEUR D'ENTRAÎNEMENT 3D AURORA (LOCAL) ===")
OUTPUT_DIR = "/home/juan/AuroraIA_Outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Matériel détecté : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")

# 1. Cible : Un modèle 3D très complexe (Tore haute résolution)
# (Ceci simule la réalité parfaite que l'IA essaie d'atteindre)
target_mesh = trimesh.creation.torus(major_radius=2.0, minor_radius=0.7, major_sections=128, minor_sections=64)
target_points, _ = trimesh.sample.sample_surface(target_mesh, 5000)
target_points = torch.tensor(target_points, dtype=torch.float32).to(device)

# 2. Modèle d'IA Générative 3D
class Aurora3DGenerator(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, 1024),
            nn.GELU(),
            nn.Linear(1024, 2048),
            nn.GELU(),
            nn.Linear(2048, 1024),
            nn.GELU(),
            nn.Linear(1024, 3)
        )
    def forward(self, x):
        return self.net(x)

model = Aurora3DGenerator().to(device)
optimizer = optim.AdamW(model.parameters(), lr=1e-3)

def chamfer_distance(p1, p2):
    dist = torch.cdist(p1, p2)
    return torch.min(dist, dim=1)[0].mean() + torch.min(dist, dim=0)[0].mean()

base_mesh = trimesh.creation.icosphere(subdivisions=4)
base_vertices = torch.tensor(base_mesh.vertices, dtype=torch.float32).to(device)

weights_path = os.path.join(OUTPUT_DIR, "aurora_3d_weights.pth")
is_first_run = not os.path.exists(weights_path)

if is_first_run:
    print("\n--- Phase 1 : Chargement du Modèle de Base (Simulé) ---")
    print("Le modèle part de zéro. Pour éviter un chaos total (comme Trellis de base qui est 'assez bien mais pas parfait'),")
    print("nous allons pré-entraîner rapidement l'IA pour qu'elle ait une forme décente mais imparfaite.")
    model.train()
    for i in range(100): # Pré-entraînement rapide pour dégrossir la forme
        optimizer.zero_grad()
        loss = chamfer_distance(model(base_vertices), target_points)
        loss.backward()
        optimizer.step()
else:
    print("\n--- Phase 1 : Chargement du Dernier Modèle Renforcé ---")
    model.load_state_dict(torch.load(weights_path))
    print("Poids précédents chargés avec succès. L'IA reprend là où elle s'était arrêtée.")

# --- EXPORT DU MODÈLE AVANT LE NOUVEAU CYCLE ---
model.eval()
with torch.no_grad():
    initial_vertices = model(base_vertices).cpu().numpy()
initial_glb = os.path.join(OUTPUT_DIR, "01_modele_de_base.glb")
trimesh.Trimesh(vertices=initial_vertices, faces=base_mesh.faces).export(initial_glb)
print(f"-> EXPORTÉ : {initial_glb} (C'est ton point de départ pour ce cycle)")

# --- CYCLE DE RENFORCEMENT (FINE-TUNING) ---
print("\n--- Phase 2 : Cycle de Renforcement (Amélioration de la précision) ---")
epochs_reinforcement = 1500
model.train()
for epoch in range(1, epochs_reinforcement + 1):
    optimizer.zero_grad()
    predicted_vertices = model(base_vertices)
    loss = chamfer_distance(predicted_vertices, target_points)
    loss.backward()
    optimizer.step()
    
    if epoch % 300 == 0 or epoch == epochs_reinforcement:
        print(f"Renforcement en cours... [{epoch}/{epochs_reinforcement}] - Erreur spatiale : {loss.item():.6f}")

# --- EXPORT DU MODÈLE APRÈS LE CYCLE ---
print("\n--- Phase 3 : Export du Résultat Renforcé ---")
model.eval()
with torch.no_grad():
    final_vertices = model(base_vertices).cpu().numpy()
final_glb = os.path.join(OUTPUT_DIR, "02_modele_renforce.glb")
trimesh.Trimesh(vertices=final_vertices, faces=base_mesh.faces).export(final_glb)
print(f"-> EXPORTÉ : {final_glb} (C'est le résultat après renforcement !)")

# Sauvegarde de l'état pour le prochain cycle
torch.save(model.state_dict(), weights_path)
print(f"\nPoids de l'IA sauvegardés dans {weights_path}.")
print(f"SUCCÈS ! Tu peux maintenant ouvrir les fichiers .glb dans {OUTPUT_DIR} pour comparer l'amélioration.")
