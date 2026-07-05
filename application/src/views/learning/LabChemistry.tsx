import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Atom, Beaker, FlaskConical, Search, Sparkles, Zap } from 'lucide-react'

// =====================================================================
// PERIODIC TABLE — 118 elements compact data
// =====================================================================

type Element = {
  z: number
  s: string // symbol
  n: string // name
  cat: string
  group: number
  period: number
  mass: number
  ec?: string // electron config short
  block: 's' | 'p' | 'd' | 'f'
}

// Compact table — every element 1..118 with grid position, category, mass, block
const ELEMENTS: Element[] = [
  { z: 1, s: 'H', n: 'Hydrogène', cat: 'reactive', group: 1, period: 1, mass: 1.008, ec: '1s¹', block: 's' },
  { z: 2, s: 'He', n: 'Hélium', cat: 'noble', group: 18, period: 1, mass: 4.0026, ec: '1s²', block: 's' },
  { z: 3, s: 'Li', n: 'Lithium', cat: 'alkali', group: 1, period: 2, mass: 6.94, ec: '[He] 2s¹', block: 's' },
  { z: 4, s: 'Be', n: 'Béryllium', cat: 'alkaline', group: 2, period: 2, mass: 9.0122, ec: '[He] 2s²', block: 's' },
  { z: 5, s: 'B', n: 'Bore', cat: 'metalloid', group: 13, period: 2, mass: 10.81, ec: '[He] 2s² 2p¹', block: 'p' },
  { z: 6, s: 'C', n: 'Carbone', cat: 'reactive', group: 14, period: 2, mass: 12.011, ec: '[He] 2s² 2p²', block: 'p' },
  { z: 7, s: 'N', n: 'Azote', cat: 'reactive', group: 15, period: 2, mass: 14.007, ec: '[He] 2s² 2p³', block: 'p' },
  { z: 8, s: 'O', n: 'Oxygène', cat: 'reactive', group: 16, period: 2, mass: 15.999, ec: '[He] 2s² 2p⁴', block: 'p' },
  { z: 9, s: 'F', n: 'Fluor', cat: 'halogen', group: 17, period: 2, mass: 18.998, ec: '[He] 2s² 2p⁵', block: 'p' },
  { z: 10, s: 'Ne', n: 'Néon', cat: 'noble', group: 18, period: 2, mass: 20.180, ec: '[He] 2s² 2p⁶', block: 'p' },
  { z: 11, s: 'Na', n: 'Sodium', cat: 'alkali', group: 1, period: 3, mass: 22.990, ec: '[Ne] 3s¹', block: 's' },
  { z: 12, s: 'Mg', n: 'Magnésium', cat: 'alkaline', group: 2, period: 3, mass: 24.305, ec: '[Ne] 3s²', block: 's' },
  { z: 13, s: 'Al', n: 'Aluminium', cat: 'metal', group: 13, period: 3, mass: 26.982, ec: '[Ne] 3s² 3p¹', block: 'p' },
  { z: 14, s: 'Si', n: 'Silicium', cat: 'metalloid', group: 14, period: 3, mass: 28.085, ec: '[Ne] 3s² 3p²', block: 'p' },
  { z: 15, s: 'P', n: 'Phosphore', cat: 'reactive', group: 15, period: 3, mass: 30.974, ec: '[Ne] 3s² 3p³', block: 'p' },
  { z: 16, s: 'S', n: 'Soufre', cat: 'reactive', group: 16, period: 3, mass: 32.06, ec: '[Ne] 3s² 3p⁴', block: 'p' },
  { z: 17, s: 'Cl', n: 'Chlore', cat: 'halogen', group: 17, period: 3, mass: 35.45, ec: '[Ne] 3s² 3p⁵', block: 'p' },
  { z: 18, s: 'Ar', n: 'Argon', cat: 'noble', group: 18, period: 3, mass: 39.948, ec: '[Ne] 3s² 3p⁶', block: 'p' },
  { z: 19, s: 'K', n: 'Potassium', cat: 'alkali', group: 1, period: 4, mass: 39.098, block: 's' },
  { z: 20, s: 'Ca', n: 'Calcium', cat: 'alkaline', group: 2, period: 4, mass: 40.078, block: 's' },
  { z: 21, s: 'Sc', n: 'Scandium', cat: 'transition', group: 3, period: 4, mass: 44.956, block: 'd' },
  { z: 22, s: 'Ti', n: 'Titane', cat: 'transition', group: 4, period: 4, mass: 47.867, block: 'd' },
  { z: 23, s: 'V', n: 'Vanadium', cat: 'transition', group: 5, period: 4, mass: 50.942, block: 'd' },
  { z: 24, s: 'Cr', n: 'Chrome', cat: 'transition', group: 6, period: 4, mass: 51.996, block: 'd' },
  { z: 25, s: 'Mn', n: 'Manganèse', cat: 'transition', group: 7, period: 4, mass: 54.938, block: 'd' },
  { z: 26, s: 'Fe', n: 'Fer', cat: 'transition', group: 8, period: 4, mass: 55.845, block: 'd' },
  { z: 27, s: 'Co', n: 'Cobalt', cat: 'transition', group: 9, period: 4, mass: 58.933, block: 'd' },
  { z: 28, s: 'Ni', n: 'Nickel', cat: 'transition', group: 10, period: 4, mass: 58.693, block: 'd' },
  { z: 29, s: 'Cu', n: 'Cuivre', cat: 'transition', group: 11, period: 4, mass: 63.546, block: 'd' },
  { z: 30, s: 'Zn', n: 'Zinc', cat: 'transition', group: 12, period: 4, mass: 65.38, block: 'd' },
  { z: 31, s: 'Ga', n: 'Gallium', cat: 'metal', group: 13, period: 4, mass: 69.723, block: 'p' },
  { z: 32, s: 'Ge', n: 'Germanium', cat: 'metalloid', group: 14, period: 4, mass: 72.630, block: 'p' },
  { z: 33, s: 'As', n: 'Arsenic', cat: 'metalloid', group: 15, period: 4, mass: 74.922, block: 'p' },
  { z: 34, s: 'Se', n: 'Sélénium', cat: 'reactive', group: 16, period: 4, mass: 78.971, block: 'p' },
  { z: 35, s: 'Br', n: 'Brome', cat: 'halogen', group: 17, period: 4, mass: 79.904, block: 'p' },
  { z: 36, s: 'Kr', n: 'Krypton', cat: 'noble', group: 18, period: 4, mass: 83.798, block: 'p' },
  { z: 37, s: 'Rb', n: 'Rubidium', cat: 'alkali', group: 1, period: 5, mass: 85.468, block: 's' },
  { z: 38, s: 'Sr', n: 'Strontium', cat: 'alkaline', group: 2, period: 5, mass: 87.62, block: 's' },
  { z: 39, s: 'Y', n: 'Yttrium', cat: 'transition', group: 3, period: 5, mass: 88.906, block: 'd' },
  { z: 40, s: 'Zr', n: 'Zirconium', cat: 'transition', group: 4, period: 5, mass: 91.224, block: 'd' },
  { z: 41, s: 'Nb', n: 'Niobium', cat: 'transition', group: 5, period: 5, mass: 92.906, block: 'd' },
  { z: 42, s: 'Mo', n: 'Molybdène', cat: 'transition', group: 6, period: 5, mass: 95.95, block: 'd' },
  { z: 43, s: 'Tc', n: 'Technétium', cat: 'transition', group: 7, period: 5, mass: 98, block: 'd' },
  { z: 44, s: 'Ru', n: 'Ruthénium', cat: 'transition', group: 8, period: 5, mass: 101.07, block: 'd' },
  { z: 45, s: 'Rh', n: 'Rhodium', cat: 'transition', group: 9, period: 5, mass: 102.91, block: 'd' },
  { z: 46, s: 'Pd', n: 'Palladium', cat: 'transition', group: 10, period: 5, mass: 106.42, block: 'd' },
  { z: 47, s: 'Ag', n: 'Argent', cat: 'transition', group: 11, period: 5, mass: 107.87, block: 'd' },
  { z: 48, s: 'Cd', n: 'Cadmium', cat: 'transition', group: 12, period: 5, mass: 112.41, block: 'd' },
  { z: 49, s: 'In', n: 'Indium', cat: 'metal', group: 13, period: 5, mass: 114.82, block: 'p' },
  { z: 50, s: 'Sn', n: 'Étain', cat: 'metal', group: 14, period: 5, mass: 118.71, block: 'p' },
  { z: 51, s: 'Sb', n: 'Antimoine', cat: 'metalloid', group: 15, period: 5, mass: 121.76, block: 'p' },
  { z: 52, s: 'Te', n: 'Tellure', cat: 'metalloid', group: 16, period: 5, mass: 127.60, block: 'p' },
  { z: 53, s: 'I', n: 'Iode', cat: 'halogen', group: 17, period: 5, mass: 126.90, block: 'p' },
  { z: 54, s: 'Xe', n: 'Xénon', cat: 'noble', group: 18, period: 5, mass: 131.29, block: 'p' },
  { z: 55, s: 'Cs', n: 'Césium', cat: 'alkali', group: 1, period: 6, mass: 132.91, block: 's' },
  { z: 56, s: 'Ba', n: 'Baryum', cat: 'alkaline', group: 2, period: 6, mass: 137.33, block: 's' },
  { z: 57, s: 'La', n: 'Lanthane', cat: 'lanthanide', group: 3, period: 6, mass: 138.91, block: 'f' },
  { z: 58, s: 'Ce', n: 'Cérium', cat: 'lanthanide', group: 0, period: 9, mass: 140.12, block: 'f' },
  { z: 59, s: 'Pr', n: 'Praséodyme', cat: 'lanthanide', group: 0, period: 9, mass: 140.91, block: 'f' },
  { z: 60, s: 'Nd', n: 'Néodyme', cat: 'lanthanide', group: 0, period: 9, mass: 144.24, block: 'f' },
  { z: 61, s: 'Pm', n: 'Prométhium', cat: 'lanthanide', group: 0, period: 9, mass: 145, block: 'f' },
  { z: 62, s: 'Sm', n: 'Samarium', cat: 'lanthanide', group: 0, period: 9, mass: 150.36, block: 'f' },
  { z: 63, s: 'Eu', n: 'Europium', cat: 'lanthanide', group: 0, period: 9, mass: 151.96, block: 'f' },
  { z: 64, s: 'Gd', n: 'Gadolinium', cat: 'lanthanide', group: 0, period: 9, mass: 157.25, block: 'f' },
  { z: 65, s: 'Tb', n: 'Terbium', cat: 'lanthanide', group: 0, period: 9, mass: 158.93, block: 'f' },
  { z: 66, s: 'Dy', n: 'Dysprosium', cat: 'lanthanide', group: 0, period: 9, mass: 162.50, block: 'f' },
  { z: 67, s: 'Ho', n: 'Holmium', cat: 'lanthanide', group: 0, period: 9, mass: 164.93, block: 'f' },
  { z: 68, s: 'Er', n: 'Erbium', cat: 'lanthanide', group: 0, period: 9, mass: 167.26, block: 'f' },
  { z: 69, s: 'Tm', n: 'Thulium', cat: 'lanthanide', group: 0, period: 9, mass: 168.93, block: 'f' },
  { z: 70, s: 'Yb', n: 'Ytterbium', cat: 'lanthanide', group: 0, period: 9, mass: 173.05, block: 'f' },
  { z: 71, s: 'Lu', n: 'Lutécium', cat: 'lanthanide', group: 0, period: 9, mass: 174.97, block: 'f' },
  { z: 72, s: 'Hf', n: 'Hafnium', cat: 'transition', group: 4, period: 6, mass: 178.49, block: 'd' },
  { z: 73, s: 'Ta', n: 'Tantale', cat: 'transition', group: 5, period: 6, mass: 180.95, block: 'd' },
  { z: 74, s: 'W', n: 'Tungstène', cat: 'transition', group: 6, period: 6, mass: 183.84, block: 'd' },
  { z: 75, s: 'Re', n: 'Rhénium', cat: 'transition', group: 7, period: 6, mass: 186.21, block: 'd' },
  { z: 76, s: 'Os', n: 'Osmium', cat: 'transition', group: 8, period: 6, mass: 190.23, block: 'd' },
  { z: 77, s: 'Ir', n: 'Iridium', cat: 'transition', group: 9, period: 6, mass: 192.22, block: 'd' },
  { z: 78, s: 'Pt', n: 'Platine', cat: 'transition', group: 10, period: 6, mass: 195.08, block: 'd' },
  { z: 79, s: 'Au', n: 'Or', cat: 'transition', group: 11, period: 6, mass: 196.97, block: 'd' },
  { z: 80, s: 'Hg', n: 'Mercure', cat: 'transition', group: 12, period: 6, mass: 200.59, block: 'd' },
  { z: 81, s: 'Tl', n: 'Thallium', cat: 'metal', group: 13, period: 6, mass: 204.38, block: 'p' },
  { z: 82, s: 'Pb', n: 'Plomb', cat: 'metal', group: 14, period: 6, mass: 207.2, block: 'p' },
  { z: 83, s: 'Bi', n: 'Bismuth', cat: 'metal', group: 15, period: 6, mass: 208.98, block: 'p' },
  { z: 84, s: 'Po', n: 'Polonium', cat: 'metalloid', group: 16, period: 6, mass: 209, block: 'p' },
  { z: 85, s: 'At', n: 'Astate', cat: 'halogen', group: 17, period: 6, mass: 210, block: 'p' },
  { z: 86, s: 'Rn', n: 'Radon', cat: 'noble', group: 18, period: 6, mass: 222, block: 'p' },
  { z: 87, s: 'Fr', n: 'Francium', cat: 'alkali', group: 1, period: 7, mass: 223, block: 's' },
  { z: 88, s: 'Ra', n: 'Radium', cat: 'alkaline', group: 2, period: 7, mass: 226, block: 's' },
  { z: 89, s: 'Ac', n: 'Actinium', cat: 'actinide', group: 3, period: 7, mass: 227, block: 'f' },
  { z: 90, s: 'Th', n: 'Thorium', cat: 'actinide', group: 0, period: 10, mass: 232.04, block: 'f' },
  { z: 91, s: 'Pa', n: 'Protactinium', cat: 'actinide', group: 0, period: 10, mass: 231.04, block: 'f' },
  { z: 92, s: 'U', n: 'Uranium', cat: 'actinide', group: 0, period: 10, mass: 238.03, block: 'f' },
  { z: 93, s: 'Np', n: 'Neptunium', cat: 'actinide', group: 0, period: 10, mass: 237, block: 'f' },
  { z: 94, s: 'Pu', n: 'Plutonium', cat: 'actinide', group: 0, period: 10, mass: 244, block: 'f' },
  { z: 95, s: 'Am', n: 'Américium', cat: 'actinide', group: 0, period: 10, mass: 243, block: 'f' },
  { z: 96, s: 'Cm', n: 'Curium', cat: 'actinide', group: 0, period: 10, mass: 247, block: 'f' },
  { z: 97, s: 'Bk', n: 'Berkélium', cat: 'actinide', group: 0, period: 10, mass: 247, block: 'f' },
  { z: 98, s: 'Cf', n: 'Californium', cat: 'actinide', group: 0, period: 10, mass: 251, block: 'f' },
  { z: 99, s: 'Es', n: 'Einsteinium', cat: 'actinide', group: 0, period: 10, mass: 252, block: 'f' },
  { z: 100, s: 'Fm', n: 'Fermium', cat: 'actinide', group: 0, period: 10, mass: 257, block: 'f' },
  { z: 101, s: 'Md', n: 'Mendelévium', cat: 'actinide', group: 0, period: 10, mass: 258, block: 'f' },
  { z: 102, s: 'No', n: 'Nobélium', cat: 'actinide', group: 0, period: 10, mass: 259, block: 'f' },
  { z: 103, s: 'Lr', n: 'Lawrencium', cat: 'actinide', group: 0, period: 10, mass: 266, block: 'f' },
  { z: 104, s: 'Rf', n: 'Rutherfordium', cat: 'transition', group: 4, period: 7, mass: 267, block: 'd' },
  { z: 105, s: 'Db', n: 'Dubnium', cat: 'transition', group: 5, period: 7, mass: 268, block: 'd' },
  { z: 106, s: 'Sg', n: 'Seaborgium', cat: 'transition', group: 6, period: 7, mass: 269, block: 'd' },
  { z: 107, s: 'Bh', n: 'Bohrium', cat: 'transition', group: 7, period: 7, mass: 270, block: 'd' },
  { z: 108, s: 'Hs', n: 'Hassium', cat: 'transition', group: 8, period: 7, mass: 277, block: 'd' },
  { z: 109, s: 'Mt', n: 'Meitnérium', cat: 'transition', group: 9, period: 7, mass: 278, block: 'd' },
  { z: 110, s: 'Ds', n: 'Darmstadtium', cat: 'transition', group: 10, period: 7, mass: 281, block: 'd' },
  { z: 111, s: 'Rg', n: 'Roentgenium', cat: 'transition', group: 11, period: 7, mass: 282, block: 'd' },
  { z: 112, s: 'Cn', n: 'Copernicium', cat: 'transition', group: 12, period: 7, mass: 285, block: 'd' },
  { z: 113, s: 'Nh', n: 'Nihonium', cat: 'metal', group: 13, period: 7, mass: 286, block: 'p' },
  { z: 114, s: 'Fl', n: 'Flérovium', cat: 'metal', group: 14, period: 7, mass: 289, block: 'p' },
  { z: 115, s: 'Mc', n: 'Moscovium', cat: 'metal', group: 15, period: 7, mass: 290, block: 'p' },
  { z: 116, s: 'Lv', n: 'Livermorium', cat: 'metal', group: 16, period: 7, mass: 293, block: 'p' },
  { z: 117, s: 'Ts', n: 'Tennesse', cat: 'halogen', group: 17, period: 7, mass: 294, block: 'p' },
  { z: 118, s: 'Og', n: 'Oganesson', cat: 'noble', group: 18, period: 7, mass: 294, block: 'p' },
]

const CAT_COLOR: Record<string, string> = {
  alkali: 'from-rose-400 to-rose-600',
  alkaline: 'from-orange-400 to-amber-500',
  transition: 'from-amber-400 to-yellow-500',
  metal: 'from-violet-400 to-violet-600',
  metalloid: 'from-teal-400 to-teal-600',
  reactive: 'from-emerald-400 to-emerald-600',
  halogen: 'from-cyan-400 to-blue-500',
  noble: 'from-fuchsia-400 to-pink-500',
  lanthanide: 'from-indigo-400 to-blue-600',
  actinide: 'from-pink-400 to-rose-600',
}

const CAT_LABEL: Record<string, string> = {
  alkali: 'Alcalin',
  alkaline: 'Alcalino-terreux',
  transition: 'Transition',
  metal: 'Métal',
  metalloid: 'Métalloïde',
  reactive: 'Non-métal',
  halogen: 'Halogène',
  noble: 'Gaz noble',
  lanthanide: 'Lanthanide',
  actinide: 'Actinide',
}

// =====================================================================
// MOLECULES library
// =====================================================================

type Molecule = {
  formula: string
  name: string
  atoms: Array<{ el: string; x: number; y: number; r?: number }>
  bonds: Array<{ a: number; b: number; order: 1 | 2 | 3 }>
  facts: string[]
}

const MOLECULES: Molecule[] = [
  {
    formula: 'H₂O',
    name: 'Eau',
    atoms: [
      { el: 'O', x: 0, y: 0, r: 16 },
      { el: 'H', x: -34, y: 22, r: 11 },
      { el: 'H', x: 34, y: 22, r: 11 },
    ],
    bonds: [{ a: 0, b: 1, order: 1 }, { a: 0, b: 2, order: 1 }],
    facts: ['Angle H-O-H ≈ 104,5°', 'Liaisons covalentes polaires', 'Solvant universel'],
  },
  {
    formula: 'CO₂',
    name: 'Dioxyde de carbone',
    atoms: [
      { el: 'C', x: 0, y: 0, r: 14 },
      { el: 'O', x: -44, y: 0, r: 16 },
      { el: 'O', x: 44, y: 0, r: 16 },
    ],
    bonds: [{ a: 0, b: 1, order: 2 }, { a: 0, b: 2, order: 2 }],
    facts: ['Molécule linéaire', 'Doubles liaisons C=O', 'Gaz à effet de serre'],
  },
  {
    formula: 'CH₄',
    name: 'Méthane',
    atoms: [
      { el: 'C', x: 0, y: 0, r: 14 },
      { el: 'H', x: -34, y: -28, r: 10 },
      { el: 'H', x: 34, y: -28, r: 10 },
      { el: 'H', x: -34, y: 32, r: 10 },
      { el: 'H', x: 34, y: 32, r: 10 },
    ],
    bonds: [{ a: 0, b: 1, order: 1 }, { a: 0, b: 2, order: 1 }, { a: 0, b: 3, order: 1 }, { a: 0, b: 4, order: 1 }],
    facts: ['Géométrie tétraédrique', 'Angle H-C-H ≈ 109,5°', 'Combustion : CH₄ + 2O₂ → CO₂ + 2H₂O'],
  },
  {
    formula: 'NH₃',
    name: 'Ammoniac',
    atoms: [
      { el: 'N', x: 0, y: 0, r: 14 },
      { el: 'H', x: -34, y: 28, r: 10 },
      { el: 'H', x: 34, y: 28, r: 10 },
      { el: 'H', x: 0, y: -34, r: 10 },
    ],
    bonds: [{ a: 0, b: 1, order: 1 }, { a: 0, b: 2, order: 1 }, { a: 0, b: 3, order: 1 }],
    facts: ['Pyramide trigonale', 'Doublet non-liant sur N', 'Base faible'],
  },
  {
    formula: 'C₂H₆O',
    name: 'Éthanol',
    atoms: [
      { el: 'C', x: -44, y: 0, r: 13 },
      { el: 'C', x: 0, y: 0, r: 13 },
      { el: 'O', x: 44, y: 0, r: 14 },
      { el: 'H', x: 70, y: -22, r: 9 },
    ],
    bonds: [{ a: 0, b: 1, order: 1 }, { a: 1, b: 2, order: 1 }, { a: 2, b: 3, order: 1 }],
    facts: ['Alcool primaire', 'Groupe -OH', 'Boisson, carburant, antiseptique'],
  },
  {
    formula: 'C₆H₆',
    name: 'Benzène',
    atoms: Array.from({ length: 6 }).map((_, i) => {
      const a = (i / 6) * Math.PI * 2 - Math.PI / 2
      return { el: 'C', x: Math.cos(a) * 36, y: Math.sin(a) * 36, r: 12 }
    }),
    bonds: Array.from({ length: 6 }).map((_, i) => ({ a: i, b: (i + 1) % 6, order: (i % 2 === 0 ? 2 : 1) as 1 | 2 })),
    facts: ['Cycle aromatique', 'Délocalisation électronique', 'Hydrocarbure aromatique'],
  },
]

const ATOM_COLOR: Record<string, string> = {
  H: '#e2e8f0',
  C: '#1f2937',
  O: '#ef4444',
  N: '#3b82f6',
  S: '#fde047',
  Cl: '#34d399',
  F: '#22d3ee',
  P: '#fb923c',
}

// =====================================================================
// REACTIONS library
// =====================================================================

const REACTIONS = [
  { id: 'comb', label: 'Combustion du méthane', eq: 'CH₄ + 2 O₂ → CO₂ + 2 H₂O', notes: 'Exothermique, ΔH = -890 kJ/mol' },
  { id: 'hcl', label: 'Acide-base', eq: 'HCl + NaOH → NaCl + H₂O', notes: 'Neutralisation, ΔH = -57 kJ/mol' },
  { id: 'photo', label: 'Photosynthèse', eq: '6 CO₂ + 6 H₂O → C₆H₁₂O₆ + 6 O₂', notes: 'Endothermique, énergie : photons' },
  { id: 'oxy', label: "Combustion de l'éthanol", eq: 'C₂H₆O + 3 O₂ → 2 CO₂ + 3 H₂O', notes: 'Exothermique' },
  { id: 'haber', label: 'Procédé Haber', eq: 'N₂ + 3 H₂ ⇌ 2 NH₃', notes: 'Catalyse Fe, équilibre' },
  { id: 'thermite', label: 'Thermite', eq: '2 Al + Fe₂O₃ → Al₂O₃ + 2 Fe', notes: 'Très exothermique' },
]

// =====================================================================
// MAIN COMPONENT
// =====================================================================

type SubTab = 'table' | 'molecule' | 'reaction'

export default function LabChemistry() {
  const [tab, setTab] = useState<SubTab>('table')
  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mono-kicker text-[10px] text-aurora-text-dim">Laboratoire de chimie</div>
          <h1 className="text-3xl font-black gradient-text-cosmic">Périodique · Molécules · Réactions</h1>
        </div>
        <div className="flex gap-1.5 p-1 rounded-2xl border border-white/10 bg-white/5 backdrop-blur">
          {(['table', 'molecule', 'reaction'] as SubTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`btn-pill ${tab === t ? 'is-active' : ''}`}
            >
              {t === 'table' && <Atom size={12} />}
              {t === 'molecule' && <FlaskConical size={12} />}
              {t === 'reaction' && <Beaker size={12} />}
              {t === 'table' ? 'Tableau' : t === 'molecule' ? 'Molécules' : 'Réactions'}
            </button>
          ))}
        </div>
      </div>

      {tab === 'table' && <PeriodicTable />}
      {tab === 'molecule' && <MoleculeViewer />}
      {tab === 'reaction' && <ReactionsLab />}
    </div>
  )
}

function PeriodicTable() {
  const [hover, setHover] = useState<Element | null>(null)
  const [search, setSearch] = useState('')
  const [pinned, setPinned] = useState<Element | null>(null)

  const matchSet = useMemo(() => {
    if (!search) return null
    const q = search.toLowerCase()
    return new Set(ELEMENTS.filter((e) => e.s.toLowerCase().includes(q) || e.n.toLowerCase().includes(q) || `${e.z}` === q).map((e) => e.z))
  }, [search])

  const cellSize = 'w-12 h-12 sm:w-[3.4rem] sm:h-[3.4rem]'
  const detail = pinned || hover

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-aurora-text-dim" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher (H, Hydrogène, 1)…"
            className="w-full rounded-xl border border-white/10 bg-white/5 pl-9 pr-3 py-2 text-sm text-aurora-text placeholder:text-aurora-text-dim focus:border-violet-400/40 outline-none"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(CAT_COLOR).map(([cat, gradient]) => (
            <span key={cat} className={`inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-aurora-text-muted`}>
              <span className={`h-2.5 w-2.5 rounded-full bg-gradient-to-br ${gradient}`} />
              {CAT_LABEL[cat]}
            </span>
          ))}
        </div>
      </div>

      <div className="holo-card p-3 sm:p-5 overflow-x-auto">
        <div className="min-w-[820px] inline-block">
          <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(18, minmax(0, 1fr))' }}>
            {Array.from({ length: 7 * 18 }).map((_, idx) => {
              const period = Math.floor(idx / 18) + 1
              const group = (idx % 18) + 1
              const el = ELEMENTS.find((e) => e.period === period && e.group === group)
              if (!el) return <div key={`empty-${idx}`} className={cellSize} />
              const dim = matchSet && !matchSet.has(el.z)
              const grad = CAT_COLOR[el.cat] || 'from-slate-500 to-slate-700'
              return (
                <ElementCell
                  key={`el-${el.z}`}
                  el={el}
                  grad={grad}
                  dim={!!dim}
                  cellSize={cellSize}
                  onHover={setHover}
                  onPin={setPinned}
                  isPinned={pinned?.z === el.z}
                />
              )
            })}
          </div>

          {/* Lanthanides + Actinides rows */}
          <div className="mt-3 space-y-1">
            <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(18, minmax(0, 1fr))' }}>
              <div className="col-span-3" key="lan-pad" />
              {ELEMENTS.filter((e) => e.cat === 'lanthanide' && e.z >= 58).map((el) => (
                <ElementCell key={`lan-${el.z}`} el={el} grad={CAT_COLOR[el.cat]} dim={!!matchSet && !matchSet.has(el.z)} cellSize={cellSize} onHover={setHover} onPin={setPinned} isPinned={pinned?.z === el.z} />
              ))}
            </div>
            <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(18, minmax(0, 1fr))' }}>
              <div className="col-span-3" key="act-pad" />
              {ELEMENTS.filter((e) => e.cat === 'actinide' && e.z >= 90).map((el) => (
                <ElementCell key={`act-${el.z}`} el={el} grad={CAT_COLOR[el.cat]} dim={!!matchSet && !matchSet.has(el.z)} cellSize={cellSize} onHover={setHover} onPin={setPinned} isPinned={pinned?.z === el.z} />
              ))}
            </div>
          </div>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {detail && (
          <motion.div
            key={detail.z}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="holo-card holo-card-cyan p-5"
          >
            <div className="flex flex-wrap items-center gap-4">
              <div className={`flex h-20 w-20 flex-col items-center justify-center rounded-2xl bg-gradient-to-br ${CAT_COLOR[detail.cat]} text-white shadow-2xl`}>
                <div className="text-[10px] mono-kicker">{detail.z}</div>
                <div className="text-2xl font-black">{detail.s}</div>
              </div>
              <div className="flex-1">
                <h3 className="text-2xl font-bold gradient-text">{detail.n}</h3>
                <p className="text-xs text-aurora-text-dim">{CAT_LABEL[detail.cat]} · Bloc {detail.block.toUpperCase()} · Masse {detail.mass}</p>
                {detail.ec && <p className="text-xs font-mono text-cyan-300 mt-1">Configuration : {detail.ec}</p>}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function ElementCell({
  el, grad, dim, cellSize, onHover, onPin, isPinned,
}: {
  el: Element; grad: string; dim: boolean; cellSize: string;
  onHover: (e: Element | null) => void; onPin: (e: Element | null) => void; isPinned: boolean
}) {
  return (
    <button
      onMouseEnter={() => onHover(el)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onPin(isPinned ? null : el)}
      className={`relative ${cellSize} rounded-md p-1 text-center transition-all hover:scale-110 hover:z-10 ${dim ? 'opacity-25' : ''} ${isPinned ? 'ring-2 ring-white scale-110 z-10' : ''}`}
      style={{ background: `linear-gradient(135deg, ${grad})` }}
    >
      <div className={`absolute inset-0.5 rounded-[5px] bg-gradient-to-br ${grad} shadow-inner`} />
      <div className="relative flex h-full w-full flex-col items-center justify-center text-white">
        <div className="text-[8px] leading-none opacity-80">{el.z}</div>
        <div className="text-sm sm:text-base font-bold leading-none">{el.s}</div>
      </div>
    </button>
  )
}

function MoleculeViewer() {
  const [idx, setIdx] = useState(0)
  const mol = MOLECULES[idx]
  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[380px] flex items-center justify-center">
        <svg viewBox="-100 -80 200 160" className="w-full h-full max-w-[420px]">
          {mol.bonds.map((b, i) => {
            const a1 = mol.atoms[b.a]
            const a2 = mol.atoms[b.b]
            return (
              <g key={i}>
                {b.order >= 1 && <line x1={a1.x} y1={a1.y} x2={a2.x} y2={a2.y} stroke="#94a3b8" strokeWidth={b.order === 3 ? 1.4 : 2} />}
                {b.order >= 2 && (
                  <line
                    x1={a1.x} y1={a1.y} x2={a2.x} y2={a2.y}
                    stroke="#94a3b8" strokeWidth={2}
                    transform={`translate(0, 5)`}
                  />
                )}
              </g>
            )
          })}
          {mol.atoms.map((a, i) => (
            <g key={i} className="molecule-atom" style={{ color: ATOM_COLOR[a.el] || '#a78bfa' }}>
              <motion.circle
                cx={a.x} cy={a.y} r={a.r || 12}
                fill={ATOM_COLOR[a.el] || '#a78bfa'}
                animate={{ y: [0, -2, 0] }}
                transition={{ repeat: Infinity, duration: 2 + i * 0.3, ease: 'easeInOut' }}
              />
              <text x={a.x} y={a.y + 4} textAnchor="middle" className="fill-white text-[10px] font-bold pointer-events-none">{a.el}</text>
            </g>
          ))}
        </svg>
      </div>

      <div className="space-y-4">
        <div className="holo-card p-5">
          <h3 className="text-2xl font-black gradient-text-cosmic">{mol.name}</h3>
          <p className="font-mono text-xl text-aurora-text mt-1">{mol.formula}</p>
          <div className="mt-3 space-y-1.5">
            {mol.facts.map((f, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-aurora-text-muted">
                <Sparkles size={12} className="mt-0.5 shrink-0 text-violet-300" />
                <span>{f}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="holo-card p-3">
          <div className="grid grid-cols-3 gap-2">
            {MOLECULES.map((m, i) => (
              <button
                key={m.formula}
                onClick={() => setIdx(i)}
                className={`rounded-lg border px-2 py-2 text-center transition-all ${i === idx ? 'border-cyan-400/60 bg-cyan-500/15 text-cyan-100' : 'border-white/10 bg-white/5 text-aurora-text hover:border-violet-400/40'}`}
              >
                <div className="font-mono text-sm font-bold">{m.formula}</div>
                <div className="text-[10px] text-aurora-text-dim mt-0.5">{m.name}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function ReactionsLab() {
  const [reactionId, setReactionId] = useState(REACTIONS[0].id)
  const [progress, setProgress] = useState(0)
  const [running, setRunning] = useState(false)
  const reaction = REACTIONS.find((r) => r.id === reactionId)!

  const trigger = () => {
    setProgress(0)
    setRunning(true)
    const start = performance.now()
    const tick = (now: number) => {
      const elapsed = now - start
      const p = Math.min(1, elapsed / 1800)
      setProgress(p)
      if (p < 1) requestAnimationFrame(tick)
      else setRunning(false)
    }
    requestAnimationFrame(tick)
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
      <div className="holo-card p-3">
        <p className="text-[11px] mono-kicker text-aurora-text-dim mb-3 px-2">Choisis</p>
        <div className="space-y-1.5">
          {REACTIONS.map((r) => (
            <button
              key={r.id}
              onClick={() => { setReactionId(r.id); setProgress(0) }}
              className={`w-full rounded-xl border px-3 py-3 text-left text-sm transition-all ${
                r.id === reactionId
                  ? 'border-violet-400/50 bg-violet-500/15 text-violet-100'
                  : 'border-white/10 bg-white/5 text-aurora-text hover:border-violet-400/30'
              }`}
            >
              <div className="font-semibold">{r.label}</div>
              <div className="text-[10px] text-aurora-text-dim mt-0.5">{r.notes}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <div className="holo-card holo-card-warm p-6 text-center relative overflow-hidden">
          <div className="absolute inset-0 dot-grid opacity-30" />
          <div className="relative">
            <p className="text-[10px] mono-kicker text-orange-300/80">Équation</p>
            <div className="mt-3 font-mono text-2xl font-bold gradient-text-fire">{reaction.eq}</div>
            <p className="mt-2 text-xs text-aurora-text-dim">{reaction.notes}</p>
            <button onClick={trigger} disabled={running} className="btn-aurora mt-5 disabled:opacity-50">
              <Zap size={14} /> Lancer la réaction
            </button>
          </div>
        </div>
        <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[200px]">
          <svg viewBox="0 0 400 180" className="w-full h-full">
            {/* Beaker */}
            <path d="M 80 30 L 80 150 Q 80 165 95 165 L 305 165 Q 320 165 320 150 L 320 30" fill="none" stroke="#94a3b8" strokeWidth="2" />
            {/* Liquid */}
            <rect
              x="82" y={150 - 80 * progress} width="236" height={80 * progress}
              fill={`hsl(${20 + progress * 220}, 80%, 55%)`}
              opacity="0.7"
            />
            {/* Bubbles */}
            {progress > 0.3 && Array.from({ length: 6 }).map((_, i) => (
              <motion.circle
                key={i}
                cx={120 + i * 40}
                cy={150 - 30}
                r={3 + Math.random() * 2}
                fill="rgba(255,255,255,0.6)"
                animate={{ cy: [150 - 30, 150 - 80 * progress + 5] }}
                transition={{ repeat: Infinity, duration: 1.4 + i * 0.2, delay: i * 0.1 }}
              />
            ))}
            {progress > 0.6 && Array.from({ length: 4 }).map((_, i) => (
              <motion.circle
                key={`heat-${i}`}
                cx={140 + i * 50}
                cy={140}
                r="2"
                fill="#fb923c"
                animate={{ cy: [140, 60], opacity: [1, 0] }}
                transition={{ repeat: Infinity, duration: 2, delay: i * 0.3 }}
              />
            ))}
          </svg>
        </div>
      </div>
    </div>
  )
}
