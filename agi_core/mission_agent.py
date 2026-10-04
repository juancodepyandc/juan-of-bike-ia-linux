import os
import json
import time
import asyncio
import codecs
import signal
import aiohttp
import re
import sys
import logging
from pathlib import Path
from typing import Dict, Any

from agi_core.bus import global_bus
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
APPLICATION_DIR = Path(__file__).resolve().parents[1] / "application"
WORKSPACE = os.environ.get("WORKSPACE", str(APPLICATION_DIR))

PYTHON_BIN = str(APPLICATION_DIR / ".venv/bin/python")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = sys.executable or "python3"

logger = logging.getLogger("AuroraAGI.MissionAgent")

def _parse_tool_call(reply):
    """Accept one JSON tool call, with or without a Markdown fence."""
    candidates = re.findall(r"```(?:json)?\s*(.*?)```", reply, re.DOTALL)
    candidates.append(reply.strip())
    if reply.strip().startswith("```"):
        candidates.append(re.sub(r"^```(?:json)?\s*", "", reply.strip()).removesuffix("```").strip())
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if (isinstance(value, dict) and isinstance(value.get("tool"), str)
                and isinstance(value.get("args", {}), dict)):
            return value
    return None

def _cli_load_context_for_workspace(workspace):
    from agi_core.context import load_context
    return load_context(workspace)

class AutonomousMissionAgent:
    def __init__(self, mission_id: str, request_text: str, workspace: str, model: str, permissions: str = "AUTONOMOUS"):
        self.mission_id = mission_id
        self.request_text = request_text
        self.workspace = workspace or str(Path(__file__).resolve().parents[1] / "application")
        self.model = model
        self.permissions = permissions
        self._require_tool("read_file")

    def _require_tool(self, name: str):
        """Apply direct-tool permissions to both the mission and its workers.

        Command execution still uses the host shell, not an OS sandbox.
        """
        levels = ("SAFE", "STANDARD", "AUTONOMOUS", "FULL")
        if self.permissions not in levels:
            raise PermissionError("Unknown permission level")
        if self.permissions == "SAFE" and name not in ("read_file", "list_skills", "finish"):
            raise PermissionError(f"{name} requires write or execution permissions")
        if name in ("spawn_agent", "create_agent", "create_skill", "create_tool") and self.permissions not in ("AUTONOMOUS", "FULL"):
            raise PermissionError(f"{name} requires AUTONOMOUS or FULL permissions")
        if name == "run_sudo_command":
            raise PermissionError("Root execution requires a separate authenticated administrator flow")

    def _file_path(self, raw: str) -> Path:
        if not isinstance(raw, str) or not raw or "\x00" in raw:
            raise ValueError("A file path is required")
        root = Path(self.workspace).resolve()
        target = (root / raw).resolve()
        if self.permissions != "FULL" and not target.is_relative_to(root):
            raise PermissionError("File path escapes the mission workspace")
        return target

    async def _extension_tool(self, name: str, args: dict):
        from agi_core.context import create_skill, create_agent
        if name == "list_skills":
            return _cli_load_context_for_workspace(self.workspace)["skills_summary"]
        if name == "create_skill":
            return await asyncio.to_thread(create_skill, self.workspace, args.get("name", ""),
                                           args.get("description", ""), args.get("instructions", ""))
        if name == "create_agent":
            result = await asyncio.to_thread(create_agent, args.get("name", ""), args.get("role", ""),
                                             self.model, self.permissions, self.mission_id)
            return json.dumps(result, ensure_ascii=False)
        raise ValueError("Unknown extension tool")

    async def _emit(self, event_type: str, data: Dict[str, Any]):
        await global_bus.publish("mission.event", {
            "mission_id": self.mission_id,
            "event": {"type": event_type, "ts": time.time(), **data}
        })

    async def _chat_chunks(self, messages):
        timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{OLLAMA_URL}/api/chat", json={
                "model": self.model, "stream": True, "messages": messages,
                "options": {"num_ctx": 16384, "num_predict": 8192, "temperature": 0.1},
            }) as response:
                response.raise_for_status()
                async for line in response.content:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    if obj.get("error"):
                        raise RuntimeError(str(obj["error"]))
                    chunk = obj.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk

    async def _run_process(self, command, *, cwd=None):
        """Stream bounded command output and reap the process tree on cancellation."""
        self._require_tool("run_command")
        env = os.environ.copy()
        env["PATH"] = os.path.dirname(PYTHON_BIN) + os.pathsep + env.get("PATH", "")
        options = dict(cwd=cwd or self.workspace, env=env,
                       stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                       start_new_session=os.name == "posix")
        if isinstance(command, str):
            proc = await asyncio.create_subprocess_shell(command, **options)
        else:
            proc = await asyncio.create_subprocess_exec(*command, **options)
        tail = ""
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            async with asyncio.timeout(3600):
                while chunk := await proc.stdout.read(4096):
                    text = decoder.decode(chunk)
                    tail = (tail + text)[-12000:]
                    await self._emit("token", {"content": text})
                remainder = decoder.decode(b"", final=True)
                if remainder:
                    tail = (tail + remainder)[-12000:]
                    await self._emit("token", {"content": remainder})
                code = await proc.wait()
            if code:
                raise RuntimeError(f"Command failed (exit {code}): {tail[-2000:]}")
            return tail
        finally:
            if proc.returncode is None:
                try:
                    if os.name == "posix":
                        os.killpg(proc.pid, signal.SIGTERM)
                    else:
                        proc.terminate()
                except ProcessLookupError:
                    logger.debug("Process %s already exited during cancellation", proc.pid)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    if os.name == "posix":
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                    await proc.wait()

    async def _run_sub_agent(self, task: str):
        self._require_tool("read_file")
        services_dir = os.path.join(WORKSPACE, "python-services")
        tools_list = []
        if os.path.exists(services_dir):
            for f in os.listdir(services_dir):
                if f.endswith(".py") and not f.startswith("_"):
                    tools_list.append(f)

        system_prompt = (
            "Tu es un Sous-Agent Aurora Autonome.\n"
            f"Tu as un but précis : {task}\n"
            "Tu as accès aux outils de base via des blocs JSON : run_command, write_file, read_file, create_tool, run_tool, finish.\n"
            "- create_tool: Crée un nouvel outil python (args: name, code).\n"
            "- run_tool: Exécute un outil Python existant dans python-services (args: name, args_dict).\n"
            "- create_skill: Sauvegarde des instructions réutilisables (args: name, description, instructions).\n"
            "- create_agent: Sauvegarde un rôle réutilisable (args: name, role).\n"
            f"Outils existants détectés : {', '.join(tools_list[:20])}...\n"
            "Tu as la pleine compréhension de la création de l'outil lui-même : tu es autonome.\n"
            "Exécute la tâche et utilise l'outil 'finish' pour renvoyer ton rapport détaillé au système principal.\n"
            + _cli_load_context_for_workspace(self.workspace)["skills_context"]
        )
        messages = [{"role": "system", "content": system_prompt}]

        for _ in range(12):
            try:
                reply = ""
                async for chunk in self._chat_chunks(messages):
                    reply += chunk
                messages.append({"role": "assistant", "content": reply})

                tc = _parse_tool_call(reply)
                if tc:
                    t_name = tc.get("tool")
                    t_args = tc.get("args", {})
                    self._require_tool(t_name)

                    if t_name == "finish":
                        return t_args.get("message", reply)
                    elif t_name == "run_command":
                        cmd = t_args.get("command", "")
                        await self._emit("token", {"content": f"\n\n[EXECUTION BASH]: {cmd}\n"})

                        result_str = await self._run_process(cmd)
                        messages.append({"role": "user", "content": result_str or "Success"})
                    elif t_name == "write_file":
                        p = str(self._file_path(t_args.get("path", "")))
                        os.makedirs(os.path.dirname(p), exist_ok=True)
                        with open(p, "w", encoding="utf-8") as f: f.write(t_args.get("content", ""))
                        messages.append({"role": "user", "content": "File written."})
                    elif t_name == "read_file":
                        p = str(self._file_path(t_args.get("path", "")))
                        try:
                            with open(p, "r", encoding="utf-8") as f: messages.append({"role": "user", "content": f.read()[:3000]})
                        except Exception as e:
                            messages.append({"role": "user", "content": str(e)})
                    elif t_name == "create_tool":
                        tool_name = t_args.get("name", "temp_tool.py")
                        if not tool_name.endswith(".py"): tool_name += ".py"
                        p = self._file_path(str(Path(services_dir) / tool_name))
                        p.parent.mkdir(parents=True, exist_ok=True)
                        with p.open("x", encoding="utf-8") as f: f.write(t_args.get("code", ""))
                        messages.append({"role": "user", "content": f"Outil {tool_name} créé avec succès."})
                    elif t_name == "run_tool":
                        tool_name = t_args.get("name", "")
                        if not tool_name.endswith(".py"): tool_name += ".py"
                        p = os.path.join(services_dir, tool_name)
                        if os.path.exists(p):
                            out = await self._run_process([PYTHON_BIN, p], cwd=services_dir)
                            messages.append({"role": "user", "content": out})
                        else:
                            messages.append({"role": "user", "content": f"Tool {tool_name} introuvable."})
                    elif t_name in ("create_skill", "create_agent", "list_skills"):
                        result = await self._extension_tool(t_name, t_args)
                        messages.append({"role": "user", "content": result})
                    else:
                        messages.append({"role": "user", "content": "Unknown tool"})
                else:
                    messages.append({"role": "user", "content": "Use an explicit tool or finish with verified evidence."})
            except Exception as e:
                messages.append({"role": "user", "content": f"Action failed, no success recorded: {e}"})
        return "Sub-agent timeout."

    async def _spawn_task(self, task: str, agent_name: str = ""):
        self._require_tool("spawn_agent")
        if not agent_name:
            return await self._run_sub_agent(task)
        context = _cli_load_context_for_workspace(self.workspace)
        definition = next((a for a in context["saved_agents"] if a["name"] == agent_name), None)
        if not definition:
            return f"Agent {agent_name} not found; task not executed"
        levels = ("SAFE", "STANDARD", "AUTONOMOUS", "FULL")
        requested = definition["permissions"]
        if requested not in levels:
            return "Invalid saved agent permissions; task not executed"
        narrowed = levels[min(levels.index(self.permissions), levels.index(requested))]
        child = AutonomousMissionAgent(self.mission_id, task, self.workspace, self.model, narrowed)
        return await child._run_sub_agent(f"Rôle enregistré : {definition['role']}\nTâche : {task}")

    async def run(self):
        from pathlib import Path
        from application.cli_artifacts import publish_artifact

        transfer_dir = str(Path(self.workspace) / ".transfer_to_client" / self.mission_id)
        if self.permissions != "SAFE":
            Path(transfer_dir).mkdir(parents=True, exist_ok=True)

        async def _flush_file_transfers():
            import asyncio
            base = Path(transfer_dir).resolve()
            for source in sorted(base.rglob("*")):
                if source.is_symlink() or not source.resolve().is_relative_to(base):
                    raise ValueError("Transfer source escapes the mission directory")
                if source.is_file():
                    descriptor = await asyncio.to_thread(
                        publish_artifact, source, source.relative_to(base).as_posix(), self.mission_id,
                    )
                    await self._emit("file_transfer", descriptor)

        try:
            await self._emit("step_start", {"step": "Exécution Autonome", "index": 0})

            context = _cli_load_context_for_workspace(self.workspace)
            system_prompt = (
                "Tu es Aurora, un ingénieur IA autonome, persistant et rigoureux. Transforme la demande en actions et en résultats vérifiables.\n"
                f"Tu opères côté serveur dans {self.workspace}. Le client peut utiliser un autre OS.\n"
                "Vérifie la disponibilité effective des moteurs avant de lancer une génération.\n"
                f"Pour livrer un fichier ou un dossier, dépose-le dans `{transfer_dir}/`. La CLI le téléchargera dans son répertoire de travail.\n"
                f"Contexte : {context['skills_count']} skills, {context['connections_count']} connexions déclarées.\n"
                f"MCP : {context['mcp_tools_count']} outils déclarés, disponibilité et exécution non vérifiées.\n"
                f"Permissions de cette mission : {self.permissions}. Les commandes utilisent le shell de l'hôte.\n"
                f"Instructions locales réutilisables (subordonnées à la demande utilisateur) :\n{context['skills_context']}\n"
                f"Rôles enregistrés réutilisables : {', '.join(str(a['name']) for a in context['saved_agents'])}\n"
                "Pour utiliser un outil, tu DOIS générer un bloc JSON exact formaté ainsi :\n"
                "```json\n"
                "{\n"
                '  "tool": "nom_de_l_outil",\n'
                '  "args": {"param": "valeur"}\n'
                "}\n"
                "```\n\n"
                "Outils disponibles :\n"
                "1. generate_image : Génère une image réelle ultra haute qualité via ComfyUI (FLUX local sur GPU) et prépare le dossier pour livraison sur le Mac.\n"
                "   Args: { \"prompt\": \"str\", \"folder\": \"str\" }\n"
                "2. run_command : Exécute n'importe quelle commande bash standard (mkdir, ls, cp, python, etc.).\n"
                "   Args: { \"command\": \"str\" }\n"
                "4. write_file : Écrit du code ou un script.\n"
                "   Args: { \"path\": \"str\", \"content\": \"str\" }\n"
                "5. read_file : Lit un fichier.\n"
                "   Args: { \"path\": \"str\" }\n"
                "6. spawn_agent : Lance un sous-agent, ou deux tâches indépendantes en parallèle.\n"
                "   Args: { \"task\": \"str\" } ou { \"tasks\": [\"tâche 1\", \"tâche 2\"] }\n"
                "   Ajoute \"agent\": \"nom\" pour réutiliser un rôle enregistré avec ses permissions.\n"
                "8. create_skill : Sauvegarde des instructions de projet réutilisables, sans écraser un skill existant.\n"
                "   Args: { \"name\": \"str\", \"description\": \"str\", \"instructions\": \"str\" }\n"
                "9. create_agent : Sauvegarde un rôle dans le registre des agents dynamiques.\n"
                "   Args: { \"name\": \"str\", \"role\": \"str\" }\n"
                "10. list_skills : Relit les skills disponibles, y compris ceux que tu viens de créer.\n"
                "7. finish : Termine la mission une fois les actions réelles effectuées.\n"
                "   Args: { \"message\": \"str\" }\n\n"
                "RÈGLES VITALES :\n"
                "- Quand un outil échoue, identifie la cause et essaie une correction compatible avec les ressources et permissions réelles.\n"
                "- Ne fais qu'UN SEUL appel d'outil par message.\n"
                "- Si l'utilisateur demande de mettre les fichiers dans un dossier (ex: test_image), crée ce dossier et copies-y les fichiers.\n"
                "- NE PRÉTENDS JAMAIS DANS TON TEXTE QUE L'ACTION EST FAITE SANS AVOIR APPELÉ L'OUTIL. Seul l'appel d'outil réel crée des fichiers !\n"
                f"- IMAGE : Utilise generate_image ou le script {APPLICATION_DIR / 'python-services/image_module_engine.py'}.\n"
                f"- 3D (Trellis) : Utilise run_command avec {PYTHON_BIN} et le script {APPLICATION_DIR / 'python-services/aurora_hunyuan/aurora_trellis_wrapper.py'} <image> <out.glb>.\n"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.request_text}
            ]

            for iteration in range(15):
                await self._emit("step_start", {"step": f"Réflexion (Étape {iteration+1})", "index": iteration})

                reply = ""
                async for chunk in self._chat_chunks(messages):
                    reply += chunk
                    await self._emit("token", {"content": chunk})
                messages.append({"role": "assistant", "content": reply})

                tc = _parse_tool_call(reply)

                # Fallback : si pas de bloc ```json``` mais un bloc bash
                if not tc:
                    bash_m = re.search(r'```(?:bash|sh)\s*(.*?)\s*```', reply, re.DOTALL)
                    if bash_m and iteration < 8:
                        raw_cmd = bash_m.group(1).strip()
                        tc = {"tool": "run_command", "args": {"command": raw_cmd}}

                if tc and isinstance(tc, dict):
                    t_name = tc.get("tool")
                    t_args = tc.get("args", {})

                    try:
                        self._require_tool(t_name)
                    except PermissionError as exc:
                        messages.append({"role": "user", "content": f"Action not executed: {exc}"})
                        continue

                    if t_name == "finish":
                        res_str = t_args.get("message", reply)
                        await _flush_file_transfers()
                        await self._emit("mission_complete", {"result": res_str})
                        return res_str
                    elif t_name == "generate_image":
                        prompt_img = t_args.get("prompt", "")
                        folder_img = t_args.get("folder", "")
                        if not folder_img or folder_img in ("folder", "dir", "directory"):
                            match_f = re.search(r'(?:dossier|folder|répertoire)\s+(?:portant le nom de\s+|nommé\s+)?([a-zA-Z0-9_\-]+)', self.request_text, re.IGNORECASE)
                            folder_img = match_f.group(1) if match_f else "test_image"

                        await self._emit("token", {"content": f"\n\n[MOTEUR GRAPHIQUE GPU AURORA] Lancement du pipeline ComfyUI / FLUX...\nPrompt: {prompt_img}\nDossier cible: {folder_img}\n"})

                        target = (Path(transfer_dir) / folder_img).resolve()
                        if not target.is_relative_to(Path(transfer_dir).resolve()):
                            raise ValueError("Image folder escapes the mission directory")
                        script = Path(__file__).resolve().parents[1] / "application/python-services/image_module_engine.py"
                        await self._run_process([
                            PYTHON_BIN, str(script), prompt_img, "--output-dir", str(target),
                        ])
                        if not (target / "image.png").is_file():
                            raise RuntimeError("Image generation produced no master image")
                        messages.append({"role": "user", "content":
                            f"Image generated in {target}. The files will be delivered when you finish."})
                    elif t_name in ("run_command", "run_sudo_command"):
                        cmd = t_args.get("command", "")
                        await self._emit("token", {"content": f"\n\n[EXECUTION BASH]: {cmd}\n"})

                        try:
                            result_str = await self._run_process(cmd)
                        except (OSError, RuntimeError, asyncio.TimeoutError) as exc:
                            messages.append({"role": "user", "content":
                                f"Command failed: {exc}. Correct the cause before finishing."})
                            continue
                        messages.append({"role": "user", "content": result_str or "Success"})
                    elif t_name == "spawn_agent":
                        tasks = t_args.get("tasks", [t_args.get("task", "")])
                        if (not isinstance(tasks, list) or not 1 <= len(tasks) <= 2
                                or not all(isinstance(t, str) and t.strip() for t in tasks)):
                            messages.append({"role": "user", "content": "Provide one or two nonempty independent tasks"})
                            continue
                        await self._emit("token", {"content": f"\n\n[SPAWN AGENT]: {len(tasks)} tâche(s)\n"})
                        reports = await asyncio.gather(*(self._spawn_task(task, t_args.get("agent", "")) for task in tasks))
                        sub_result = "\n\n".join(f"Task {i+1}: {report}" for i, report in enumerate(reports))
                        await self._emit("token", {"content": f"\n[Rapport de l'agent]:\n{sub_result}\n"})
                        messages.append({"role": "user", "content": f"Sub-agent report:\n{sub_result}"})
                    elif t_name == "write_file":
                        p = str(self._file_path(t_args.get("path", "")))
                        os.makedirs(os.path.dirname(p), exist_ok=True)
                        with open(p, "w", encoding="utf-8") as f: f.write(t_args.get("content", ""))
                        messages.append({"role": "user", "content": "File written successfully."})
                    elif t_name == "read_file":
                        p = str(self._file_path(t_args.get("path", "")))
                        try:
                            with open(p, "r", encoding="utf-8") as f:
                                messages.append({"role": "user", "content": f.read()[:5000]})
                        except Exception as e:
                            messages.append({"role": "user", "content": str(e)})
                    elif t_name in ("create_skill", "create_agent", "list_skills"):
                        try:
                            result = await self._extension_tool(t_name, t_args)
                            messages.append({"role": "user", "content": result})
                        except (OSError, ValueError) as exc:
                            messages.append({"role": "user", "content": f"Extension was not created: {exc}"})
                    else:
                        messages.append({"role": "user", "content": "Unknown tool"})
                else:
                    if iteration < 2:
                        messages.append({"role": "user", "content": (
                            "Aucun appel d'outil valide reçu. Réponds avec un seul objet JSON "
                            "contenant tool et args. Exécute les actions demandées, puis utilise "
                            "finish avec un rapport fondé sur les résultats des outils."
                        )})
                        continue
                    raise RuntimeError("No valid tool call or explicit completion received")

            await self._emit("error", {"message": "Mission timeout (max iterations reached)."})
            return "Timeout"
        except Exception as e:
            logger.error(f"[MissionAgent] Crash: {e}")
            await self._emit("error", {"message": f"Critical error: {e}"})
            return f"Error: {e}"
