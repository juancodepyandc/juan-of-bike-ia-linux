"""Navigation hints from explicit domain words; never substitute a project goal."""
import re
import unicodedata

MODULES={'conversation','image','code','video','drawing','3d','learning','cyber','voice'}

def mission_module(payload):
    explicit=payload.get('module')
    if explicit in MODULES:return explicit
    if payload.get('project_kind')=='engineering':return '3d'
    text=payload.get('project_title') or payload.get('request','')
    text=unicodedata.normalize('NFKD',text.casefold()).encode('ascii','ignore').decode()
    if re.search(r'\b(?:3d|stl|glb|gltf|figurine|figurines|maillage|impression tridimensionnelle)\b',text):return '3d'
    return None

def direct_3d_generation(text):
    normalized=unicodedata.normalize('NFKD',text.casefold()).encode('ascii','ignore').decode().strip()
    return mission_module({'request':text})=='3d' and bool(re.match(r'(?:generer|genere|creer|cree|generate|create)\b',normalized)) and not re.search(r'\b[\w-]+\.py\b|\b(?:blender|openscad|freecad|cadquery|viewer|visualiseur|application|script|code)\b',normalized)
