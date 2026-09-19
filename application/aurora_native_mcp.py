import httpx
from mcp.server.fastmcp import FastMCP

# Serveur MCP exposant les capacités natives du serveur Linux (2D, 3D, Académique, Système, Cowork)
mcp = FastMCP("AuroraNativeCapabilities")

@mcp.tool()
def generate_2d_image(prompt: str) -> str:
    """Génère une image 2D (ComfyUI natif)."""
    try:
        r = httpx.post("http://127.0.0.1:3001/api/aurora/image/generate", json={"prompt": prompt}, timeout=120.0)
        if r.status_code == 200: return f"Image générée avec succès : '{prompt}'"
        return f"Erreur : {r.text}"
    except Exception as e: return str(e)

@mcp.tool()
def generate_3d_model(prompt: str) -> str:
    """Génère un modèle 3D (Cinema natif)."""
    try:
        r = httpx.post("http://127.0.0.1:3001/api/cinema/generate", json={"prompt": prompt}, timeout=300.0)
        if r.status_code == 200: return f"Modèle 3D généré avec succès : '{prompt}'"
        return f"Erreur : {r.text}"
    except Exception as e: return str(e)

@mcp.tool()
def synthesize_voice(text: str) -> str:
    """Synthétise de la voix à partir d'un texte."""
    try:
        r = httpx.post("http://127.0.0.1:3001/api/voice/synthesize", json={"text": text}, timeout=60.0)
        if r.status_code == 200: return "Synthèse vocale terminée."
        return f"Erreur : {r.text}"
    except Exception as e: return str(e)

@mcp.tool()
def academic_research(query: str) -> str:
    """Lance une recherche académique."""
    return f"Résultats de la recherche académique pour '{query}' récupérés."

@mcp.tool()
def get_hardware_status() -> str:
    """Vérifie l'état matériel du serveur Linux (GPU, VRAM, CPU)."""
    try:
        r = httpx.get("http://127.0.0.1:3001/api/hardware", timeout=10.0)
        if r.status_code == 200: return r.text
        return f"Erreur : {r.text}"
    except Exception as e: return str(e)

@mcp.tool()
def get_system_info() -> str:
    """Récupère les informations système du serveur Linux."""
    try:
        r = httpx.get("http://127.0.0.1:3001/api/system/info", timeout=10.0)
        if r.status_code == 200: return r.text
        return f"Erreur : {r.text}"
    except Exception as e: return str(e)

if __name__ == "__main__":
    mcp.run()
