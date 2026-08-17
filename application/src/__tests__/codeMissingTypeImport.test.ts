/**
 * Run 1171 — neuf passes de modele autour d un import de deux mots.
 *
 * Extraits du flux archive (output/code/audit_v118/stream.ndjson):
 *
 *   passe 3  AdminPage.tsx  TS2339 Property 'clearOrders' does not exist on type 'OrderState'
 *            AdminPage.tsx  TS2339 Property 'coffeeName' does not exist on type 'Order'
 *   passe 5  AdminPage.tsx  TS2304 Cannot find name 'Order'
 *
 * Le modele alignait l usage sur le type, puis le type sur l usage. Le livrable
 * final ecrit `Order['status']` ligne 146 et n importe que `useOrderStore` —
 * alors que `Order` est exporte par ce module-la meme.
 *
 * Mesure sur le projet reel (output/code/audit_v119/): TS2304 1 -> 0.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  collectExportedSymbols,
  describeMissingTypeImportFixes,
  repairMissingTypeImports,
} from '../services/codeMissingTypeImport.ts'

const ORDER_STORE = `import { create } from 'zustand';

export interface Order {
  id: string;
  status: 'pending' | 'preparing' | 'sent';
}

interface OrderState {
  orders: Order[];
  clearOrders: () => void;
}

export const useOrderStore = create<OrderState>((set) => ({ orders: [], clearOrders: () => set({ orders: [] }) }));`

const ADMIN_PAGE = `import React, { useState } from 'react';
import { useOrderStore } from '../store/orderStore';
import { motion } from 'framer-motion';

export default function AdminPage() {
  const { orders, updateOrderStatus } = useOrderStore();
  return <select onChange={(e) => updateOrderStatus(order.id, e.target.value as Order['status'])} />;
}`

// Le projet reel declare Order DEUX fois — c est ce qui nourrissait l oscillation.
const TYPES_INDEX = `export interface Order {
  id: string;
  status: 'pending' | 'preparing' | 'sent';
}`

const FILES = [
  { name: 'src/store/orderStore.ts', language: 'ts', content: ORDER_STORE },
  { name: 'src/pages/AdminPage.tsx', language: 'tsx', content: ADMIN_PAGE },
  { name: 'src/types/index.ts', language: 'ts', content: TYPES_INDEX },
]

const TSC_OUTPUT = "src/pages/AdminPage.tsx(146,86): error TS2304: Cannot find name 'Order'."

describe('un type manquant se recolle sans modele', () => {
  test('le cas reel du run 1171: Order rejoint l import existant', () => {
    const r = repairMissingTypeImports(FILES, TSC_OUTPUT)
    assert.equal(r.fixes.length, 1)
    assert.deepEqual(r.fixes[0], {
      file: 'src/pages/AdminPage.tsx',
      symbol: 'Order',
      fromModule: 'src/store/orderStore',
      kind: 'type',
    })
    const admin = r.files.find((f) => f.name === 'src/pages/AdminPage.tsx')!
    assert.match(admin.content, /import \{ useOrderStore, type Order \} from '\.\.\/store\/orderStore';/)
    // Rien d autre n a bouge.
    assert.equal(r.files.find((f) => f.name === 'src/store/orderStore.ts')!.content, ORDER_STORE)
    assert.equal(r.files.find((f) => f.name === 'src/types/index.ts')!.content, TYPES_INDEX)
  })

  test('l ambiguite ne se devine pas: sans import prealable, on ne touche a rien', () => {
    const orphan = [
      { name: 'src/store/orderStore.ts', language: 'ts', content: ORDER_STORE },
      { name: 'src/types/index.ts', language: 'ts', content: TYPES_INDEX },
      { name: 'src/pages/Solo.tsx', language: 'tsx', content: "export default function S() { return <b>{'' as Order['status']}</b>; }" },
    ]
    const r = repairMissingTypeImports(orphan, "src/pages/Solo.tsx(1,40): error TS2304: Cannot find name 'Order'.")
    assert.equal(r.fixes.length, 0)
    assert.equal(r.files, orphan)
  })

  test('un symbole que personne n exporte n est pas invente', () => {
    const r = repairMissingTypeImports(FILES, "src/pages/AdminPage.tsx(3,1): error TS2304: Cannot find name 'Fantome'.")
    assert.equal(r.fixes.length, 0)
  })

  test('une classe est importee comme VALEUR, pas comme type', () => {
    const files = [
      { name: 'src/lib/repo.ts', language: 'ts', content: 'export class Repo {}\nexport const helper = 1;' },
      { name: 'src/app.ts', language: 'ts', content: "import { helper } from './lib/repo';\nconst r = new Repo();" },
    ]
    const r = repairMissingTypeImports(files, "src/app.ts(2,15): error TS2304: Cannot find name 'Repo'.")
    assert.equal(r.fixes[0].kind, 'value')
    assert.match(r.files[1].content, /import \{ helper, Repo \} from '\.\/lib\/repo';/)
  })

  test('un symbole deja importe n est pas ajoute deux fois', () => {
    const files = [
      { name: 'src/store/orderStore.ts', language: 'ts', content: ORDER_STORE },
      { name: 'src/pages/A.tsx', language: 'tsx', content: "import { type Order, useOrderStore } from '../store/orderStore';\n" },
    ]
    const r = repairMissingTypeImports(files, "src/pages/A.tsx(2,1): error TS2304: Cannot find name 'Order'.")
    assert.equal(r.fixes.length, 0)
  })

  test('l index des exports distingue type et valeur', () => {
    const index = collectExportedSymbols(FILES)
    assert.equal(index.get('Order')!.length, 2, 'Order est declare deux fois dans le projet reel')
    assert.equal(index.get('Order')!.every((c) => c.kind === 'type'), true)
    assert.equal(index.has('OrderState'), false, 'OrderState n est pas exporte')
  })

  test('la reparation se raconte, elle ne se fait pas en silence', () => {
    const r = repairMissingTypeImports(FILES, TSC_OUTPUT)
    assert.match(describeMissingTypeImportFixes(r.fixes), /AdminPage\.tsx: import de Order depuis src\/store\/orderStore/)
  })
})
