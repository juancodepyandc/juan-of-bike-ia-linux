import { ollamaGenerate } from '../hooks/useTauri.ts'
import { getBridgeUrl } from '../utils/runtime.ts'
import { useAppStore } from '../stores/appStore.ts'

export interface WebActionGoal {
  objective: string;
  startUrl: string;
  maxSteps?: number;
  headless?: boolean;
}

export interface WebActionStep {
  stepIndex: number;
  thought: string;
  action: any;
  result: any;
}

async function callWebAction(actionDef: any, headless: boolean) {
  const bridgeUrl = getBridgeUrl().replace(/\/$/, '')
  const payload = { ...actionDef, headless }
  
  const response = await fetch(`${bridgeUrl}/api/web/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
  return await response.json();
}

export async function runAutonomousWebAction(
  goal: WebActionGoal,
  onEvent?: (event: any) => void
): Promise<WebActionStep[]> {
  const model = useAppStore.getState().mainModel || 'qwen2.5-coder'
  const maxSteps = goal.maxSteps || 10
  const history: WebActionStep[] = []
  
  const emit = (title: string, detail: string) => {
    if (onEvent) {
      onEvent({
        type: 'stage',
        stage: 'understand', // Utilise un stage existant pour la chatbox
        title,
        text: detail,
        progress: 50
      })
    }
  }

  emit('Planification', `Initialisation de l'agent web sur ${goal.startUrl}`)
  
  // 1. Initial navigation + DOM extraction
  let currentDomRes = await callWebAction({ action: 'extract_dom', url: goal.startUrl }, goal.headless ?? true);
  
  for (let i = 0; i < maxSteps; i++) {
    const elements = currentDomRes.interactive_elements?.join('\n') || 'Aucun élément interactif visible.';
    const currentUrl = currentDomRes.url || goal.startUrl;
    
    const prompt = `Tu es un agent web autonome local. 
Ton objectif : ${goal.objective}
URL actuelle : ${currentUrl}

Elements interactifs du DOM:
${elements}

Actions possibles:
- {"action": "click", "selector": "#id"}
- {"action": "fill", "selector": "#id", "value": "texte"}
- {"action": "extract_dom"}
- {"action": "done", "result": "Resume de l action accomplie"}

Reponds UNIQUEMENT en JSON avec "thought" (ton raisonnement) et "command" (l'action).`;

    emit('Réflexion', `Analyse de la page (${currentDomRes.interactive_elements?.length || 0} éléments)`)

    let llmResponse = '';
    try {
      const raw = await ollamaGenerate(model, prompt);
      llmResponse = String((raw as any)?.response || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim();
      llmResponse = llmResponse.replace(/^```json/m, '').replace(/^```/m, '').replace(/```$/m, '').trim();
      
      const parsed = JSON.parse(llmResponse);
      const actionDef = parsed.command;
      const thought = parsed.thought;
      
      if (actionDef.action === 'done') {
        emit('Terminé', `Action complétée : ${thought}`)
        history.push({ stepIndex: i, thought, action: actionDef, result: actionDef.result });
        break;
      }
      
      emit('Exécution', `Action: ${actionDef.action} sur ${actionDef.selector || 'la page'}`)
      
      // Execute the action
      const actionResult = await callWebAction(actionDef, goal.headless ?? true);
      history.push({ stepIndex: i, thought, action: actionDef, result: actionResult });
      
      if (['click', 'fill', 'navigate'].includes(actionDef.action)) {
        currentDomRes = await callWebAction({ action: 'extract_dom' }, goal.headless ?? true);
      } else {
        currentDomRes = actionResult;
      }
      
    } catch (e) {
      const errStr = e instanceof Error ? e.message : String(e);
      emit('Erreur', `Ajustement du plan : ${errStr}`)
      history.push({ stepIndex: i, thought: 'Erreur LLM ou exécution', action: null, result: errStr });
      currentDomRes = await callWebAction({ action: 'extract_dom' }, goal.headless ?? true);
    }
  }
  
  return history;
}

export async function interceptWebActionIntent(
  userInput: string,
  onEvent?: (event: any) => void
): Promise<string> {
  const urlMatch = userInput.match(/https?:\/\/[^\s]+/);
  if (!urlMatch) {
    if (onEvent) onEvent({ type: 'stage', stage: 'draft', title: 'Action requise', text: 'Veuillez fournir une URL pour que je puisse lancer mon agent web autonome.', progress: 100 });
    return "Veuillez me fournir une URL (ex: https://...) pour que je puisse accomplir cette action sur le Web pour vous.";
  }
  
  const isSandbox = userInput.toLowerCase().includes('sandbox') || userInput.toLowerCase().includes('montre');
  const goalModel = useAppStore.getState().mainModel || 'qwen2.5-coder';
  
  const promptExtract = `Extrait l'objectif de l'automatisation depuis: "${userInput}". Sois tres concis.`;
  let objective = "Automatiser";
  try {
      const raw = await ollamaGenerate(goalModel, promptExtract);
      objective = String((raw as any)?.response || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim();
  } catch(e) {}

  const goal: WebActionGoal = {
    objective,
    startUrl: urlMatch[0],
    headless: !isSandbox, 
    maxSteps: 8
  };
  
  const history = await runAutonomousWebAction(goal, onEvent);
  const lastStep = history[history.length - 1];
  
  return `✅ Action web completée par ton agent autonome (${goalModel}). Résultat : ${JSON.stringify(lastStep?.result || 'Mission accomplie')}.`;
}
