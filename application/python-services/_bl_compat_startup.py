"""Shim de compatibilité Blender 5.x — restaure `Action.fcurves`.

Blender 5.0+ a SUPPRIMÉ `Action.fcurves` (remplacé par l'API en couches
`action.layers[0].strips[0].channelbag(slot).fcurves`). Des CENTAINES de scripts
d'AuroraIA (105+ générateurs `proc_*.py` animés, motion_baker, aurora_animate, etc.)
bouclaient sur `obj.animation_data.action.fcurves` pour poser l'interpolation LINEAR
des rotations continues. Sur Blender 5.1 ces boucles lèvent AttributeError →
le script crashe AVANT l'export → objets animés livrés FIGÉS ou génération échouée.

Ce fichier, déposé dans `scripts/startup/` de la config Blender, s'exécute au démarrage
de CHAQUE invocation Blender (y compris `--background`, sauf `--factory-startup`) et
rend `Action.fcurves` de nouveau utilisable, sans toucher aux 190+ scripts appelants.

Installation : copié dans `~/.config/blender/<ver>/scripts/startup/`. Réinstallable via
`install_bl_compat.py`. Idempotent (ne patche que si l'attribut manque).
"""
import bpy


def _aurora_action_fcurves(self):
    try:
        layers = getattr(self, "layers", None)
        if not layers:
            return []
        strips = layers[0].strips
        if not strips:
            return []
        slots = getattr(self, "slots", None)
        slot = slots[0] if slots else None
        if slot is None:
            return []
        cb = strips[0].channelbag(slot)
        return cb.fcurves if cb else []
    except Exception:
        return []


try:
    if not hasattr(bpy.types.Action, "fcurves"):
        bpy.types.Action.fcurves = property(_aurora_action_fcurves)
except Exception:
    pass


def register():
    try:
        if not hasattr(bpy.types.Action, "fcurves"):
            bpy.types.Action.fcurves = property(_aurora_action_fcurves)
    except Exception:
        pass


def unregister():
    pass
