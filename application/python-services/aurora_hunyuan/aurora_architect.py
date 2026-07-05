"""
Aurora Scene Architect (Layer 1)
Analyzes a complex scene prompt (e.g. "alleyway with streetlights and trash cans")
and outputs a compositional Level Design JSON (scene_manifest.json).
"""
import json
import logging
from pathlib import Path
from aurora_vision_research import _ask_ollama

log = logging.getLogger("AuroraArchitect")
log.setLevel(logging.INFO)

def design_scene(prompt: str, output_dir: Path) -> dict:
    """
    Acts as a Level Designer. Takes a prompt and outputs a JSON manifest.
    """
    sys_prompt = (
        "You are an expert 3D Level Designer. The user wants a 3D scene. "
        "Break the scene down into distinct objects to generate. "
        "Output ONLY valid JSON matching this schema:\n"
        "{\n"
        "  \"mood\": \"dramatic_night | studio_clean | cyberpunk | golden_hour | neutral\",\n"
        "  \"objects\": [\n"
        "    {\n"
        "      \"id\": \"unique_name\",\n"
        "      \"prompt\": \"detailed description of the object to generate\",\n"
        "      \"position\": [x, y, z],\n"
        "      \"scale\": [x, y, z],\n"
        "      \"animation\": \"hover_float | rotate_y | emission_pulse | walk_cycle | none\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Keep the number of objects reasonable (max 3-4) to save generation time."
    )
    
    user_prompt = f"Design this scene: {prompt}"
    
    log.info(f"Asking LLM Architect to design scene for: {prompt}")
    resp = _ask_ollama(user_prompt, [], sys_prompt, model="qwen2.5:7b")
    
    try:
        if "```json" in resp:
            resp = resp.split("```json")[1].split("```")[0].strip()
        elif "```" in resp:
            resp = resp.split("```")[1].strip()
            
        manifest = json.loads(resp)
        
        # Save manifest
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "scene_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            
        log.info(f"Scene designed! {len(manifest.get('objects', []))} objects planned. Saved to {manifest_path}")
        return manifest
        
    except Exception as e:
        log.error(f"Architect failed to generate valid JSON: {e}\nRaw: {resp}")
        # Fallback manifest
        return {
            "mood": "neutral",
            "objects": [{"id": "main_object", "prompt": prompt, "position": [0,0,0], "scale": [1,1,1], "animation": "rotate_y"}]
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    design_scene("A dark cyberpunk alleyway with a glowing vending machine and a futuristic trash can", Path("test_scene"))
