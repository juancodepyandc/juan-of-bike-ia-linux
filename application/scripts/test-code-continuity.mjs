#!/usr/bin/env node
// Module Code : « je reçois souvent une note de 0/100 … et je ne peux pas continuer les modifications ».
// Une phrase d'erreur en français dans un programme (« je ne peux pas diviser par zéro ») faisait
// classer le fichier comme une EXCUSE du modèle : score du projet entier forcé à 0, validation en
// échec, boucle de correction qui « réparait » un refus inexistant. Vraies sources TypeScript.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { findRefusalFile, isLLMRefusal } from '../src/services/codeLLMRefusal.ts'
import { computeContentQualityScore } from '../src/services/codeQualityGates.ts'
import { validateOutputMatchesIntent } from '../src/services/codeProjectValidation.ts'

const CALCULATRICE = [
  'a = float(input("a : "))',
  'b = float(input("b : "))',
  'if b == 0:',
  '    print("Erreur : je ne peux pas diviser par zéro, désolé.")',
  'else:',
  '    print(a / b)',
].join('\n')
const PY_INTENT = { projectType: 'script', complexity: 'simple', frameworks: [] }
const WEB_INTENT = { projectType: 'static_web', complexity: 'simple', frameworks: [] }

test('an error message printed by a program is code, not a model refusal', () => {
  const files = [{ name: 'calculatrice.py', language: 'python', content: CALCULATRICE }]
  assert.equal(findRefusalFile(files), undefined)
  assert.ok(computeContentQualityScore(files, PY_INTENT) > 0)
  assert.doesNotMatch(String(validateOutputMatchesIntent(files, PY_INTENT) ?? ''), /refus/i)
})

test('raw code without fences that prints a French apology is not a refusal either', () => {
  assert.equal(isLLMRefusal(CALCULATRICE), false)
})

test('a README that explains a limitation does not zero the project it documents', () => {
  const files = [
    { name: 'index.html', language: 'html', content: '<!DOCTYPE html><html><body><h1>Jeu</h1><script src="jeu.js"></script></body></html>' },
    { name: 'jeu.js', language: 'javascript', content: 'const canvas = document.querySelector("canvas")\nfunction boucle() { requestAnimationFrame(boucle) }\nboucle()' },
    { name: 'README.md', language: 'markdown', content: "Je suis désolé : ce jeu ne peut pas être lancé sans navigateur récent. Ouvrez index.html." },
  ]
  assert.equal(findRefusalFile(files), undefined)
  assert.ok(computeContentQualityScore(files, WEB_INTENT) > 0)
})

test('a real refusal is still caught', () => {
  const refusal = "Je suis désolé, mais je ne peux pas générer ce code. Je vous suggère plutôt de consulter la documentation."
  assert.equal(isLLMRefusal(refusal), true)
  assert.equal(isLLMRefusal("I'm sorry, but I can't help with generating that application."), true)
  const files = [{ name: 'reponse.txt', language: 'text', content: refusal }]
  assert.equal(findRefusalFile(files)?.name, 'reponse.txt')
  assert.equal(computeContentQualityScore(files, PY_INTENT), 0)
  assert.match(String(validateOutputMatchesIntent(files, PY_INTENT)), /refus/i)
})

test('an apology buried deep in a long text is content, not a refusal', () => {
  const longText = `${'Ce guide décrit l\'installation pas à pas. '.repeat(20)}\nRemarque : je ne peux pas garantir la compatibilité Windows XP.`
  assert.ok(longText.indexOf('je ne peux pas') > 400)
  assert.equal(isLLMRefusal(longText), false)
})
